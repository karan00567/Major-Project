"""Phase 4 acceptance tests — the agent graph (T-401..T-407).

Offline. The LLM is replaced by a stub, so these test the *contracts* — partial
state, deduplication, citation integrity, fail-soft behaviour — rather than
model quality, which is what a live run measures.
"""

from __future__ import annotations

import json
import pathlib
from unittest.mock import patch

import pytest

from researchgpt.agents.base import Agent, PartialStateViolation
from researchgpt.agents.extractor import Extractor, field_coverage
from researchgpt.agents.planner import Planner, PlanValidationError
from researchgpt.agents.retriever import Retriever, looks_like_author_list, title_key
from researchgpt.agents.writer import Writer
from researchgpt.core.config import load_config
from researchgpt.core.models import Paper, PaperInsight, SearchTask, SubQuestion

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cfg():
    return load_config(str(REPO / "configs" / "default.yaml"))


def make_paper(pid, doi=None, title=None, abstract="An abstract. " * 30):
    return Paper(
        paper_id=pid, doi=doi,
        title=title or f"A sufficiently long distinctive title number {pid}",
        source="openalex", abstract=abstract,
    )


class StubLLM:
    """Returns canned responses in order; counts calls."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, prompt, **kwargs):
        self.calls += 1
        if not self._responses:
            raise RuntimeError("StubLLM exhausted")
        value = self._responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


# --------------------------------------------------------------------------
# T-401 — the partial-state contract
# --------------------------------------------------------------------------


def test_t401_agent_returning_whole_state_is_rejected():
    """The duplication bug the `add` reducers make possible. An agent that
    returns the state it was handed re-adds every paper, silently doubling the
    corpus on iteration 2 of the Critic loop."""

    class Sloppy(Agent):
        name = "sloppy"

        def run(self, state):
            return dict(state)

    with pytest.raises(PartialStateViolation, match="ALREADY in state"):
        Sloppy()({"papers": [make_paper("p1")], "iteration": 0})


def test_t401_unknown_state_key_is_rejected():
    """LangGraph keeps an unknown key and nothing ever reads it."""

    class Typo(Agent):
        name = "typo"

        def run(self, state):
            return {"sub_question": []}

    with pytest.raises(PartialStateViolation, match="unknown state key"):
        Typo()({"iteration": 0})


def test_t401_fail_soft_contains_the_error_and_returns_nothing():
    class Boom(Agent):
        name = "boom"
        fail_soft = True

        def run(self, state):
            raise ValueError("kaboom")

    assert Boom()({"iteration": 0}) == {}


def test_t401_hard_failure_propagates_with_its_original_type():
    """Not wrapped: callers need to catch OpenAlexBudgetExhausted and
    PlanValidationError specifically, and a generic wrapper would discard
    that. The trace already records which agent failed."""

    class Boom(Agent):
        name = "boom"

        def run(self, state):
            raise ValueError("kaboom")

    with pytest.raises(ValueError, match="kaboom"):
        Boom()({"iteration": 0})


def test_t401_returning_new_items_is_allowed():
    class Fine(Agent):
        name = "fine"

        def run(self, state):
            return {"papers": [make_paper("p2")]}

    out = Fine()({"papers": [make_paper("p1")], "iteration": 0})
    assert [p.paper_id for p in out["papers"]] == ["p2"]


# --------------------------------------------------------------------------
# T-402 — the Planner
# --------------------------------------------------------------------------


def _plan(**over):
    base = {
        "sub_questions": [
            {"sq_id": "SQ1", "text": "a", "facet": "method"},
            {"sq_id": "SQ2", "text": "b", "facet": "evaluation"},
            {"sq_id": "SQ3", "text": "c", "facet": "limitation"},
            {"sq_id": "SQ4", "text": "d", "facet": "application"},
        ],
        "search_plan": [
            {"sq_id": f"SQ{i}", "query": "dense passage retrieval"} for i in range(1, 5)
        ],
        "inclusion_criteria": ["2019 or later"],
    }
    base.update(over)
    return base


def test_t402_rejects_queries_openalex_would_return_nothing_for():
    """OpenAlex ANDs every term. Measured: a 6-term query returns 0 results
    where a 3-term one returns thousands - the T-212 failure in miniature."""
    with pytest.raises(PlanValidationError, match="ANDs every term"):
        Planner._validate(_plan(search_plan=[
            {"sq_id": "SQ1", "query": "a b c d e f g"}]))


def test_t402_requires_three_of_four_facets():
    same = [{"sq_id": f"SQ{i}", "text": "x", "facet": "method"} for i in range(1, 5)]
    with pytest.raises(PlanValidationError, match="at least 3"):
        Planner._validate(_plan(sub_questions=same))


def test_t402_every_sub_question_needs_a_query():
    with pytest.raises(PlanValidationError, match="have no search task"):
        Planner._validate(_plan(search_plan=[
            {"sq_id": "SQ1", "query": "dense passage retrieval"}]))


def test_t402_rejects_a_query_pointing_at_no_sub_question():
    with pytest.raises(PlanValidationError, match="not one of"):
        Planner._validate(_plan(search_plan=[
            {"sq_id": "SQ9", "query": "dense passage retrieval"}]))


def test_t402_accepts_a_well_formed_plan():
    sqs, tasks, criteria = Planner._validate(_plan())
    assert len(sqs) == 4 and len(tasks) == 4 and criteria == ["2019 or later"]
    assert {s.facet for s in sqs} == {"method", "evaluation", "limitation", "application"}


def test_t402_repairs_a_malformed_first_response(cfg):
    """The repair pass sends the model its own broken output plus the error.
    A plain retry would resend the same prompt and usually fail identically."""
    llm = StubLLM("not json at all", json.dumps(_plan()))
    out = Planner(llm, cfg)({"research_question": "q", "iteration": 0})
    assert llm.calls == 2
    assert len(out["sub_questions"]) == 4


def test_t402_gives_up_loudly_rather_than_planning_nothing(cfg):
    """A run with no plan retrieves nothing and writes a survey about nothing,
    so the Planner is deliberately NOT fail-soft."""
    llm = StubLLM("junk", "junk", "junk")
    with pytest.raises(PlanValidationError, match="no usable plan"):
        Planner(llm, cfg)({"research_question": "q", "iteration": 0})


# --------------------------------------------------------------------------
# T-403 — the Retriever
# --------------------------------------------------------------------------


def test_t403_deduplicates_by_doi_ignoring_url_and_case(cfg):
    batch = [make_paper("a", doi="10.1/x"), make_paper("b", doi="https://doi.org/10.1/X")]
    with patch.object(Retriever, "_search", lambda *a, **k: batch):
        out = Retriever(cfg)({"iteration": 0, "papers": [],
                              "search_plan": [SearchTask(sq_id="SQ1", query="a b",
                                                         sources=["openalex"])]})
    assert len(out["papers"]) == 1


def test_t403_bridges_an_arxiv_preprint_to_its_published_version(cfg):
    """Different DOIs, same title. Without the title key the corpus carries the
    same paper twice and the Extractor pays for it twice."""
    shared = "A sufficiently long and distinctive shared paper title"
    batch = [make_paper("a", doi="10.48550/arxiv.1", title=shared),
             make_paper("b", doi="10.1145/real", title=shared)]
    with patch.object(Retriever, "_search", lambda *a, **k: batch):
        out = Retriever(cfg)({"iteration": 0, "papers": [],
                              "search_plan": [SearchTask(sq_id="SQ1", query="a b",
                                                         sources=["openalex"])]})
    assert len(out["papers"]) == 1


def test_t403_returns_nothing_already_in_state(cfg):
    """The accumulate contract: iteration 2 must add coverage, not duplicates."""
    existing = make_paper("a", doi="10.1/x")
    with patch.object(Retriever, "_search", lambda *a, **k: [existing]):
        out = Retriever(cfg)({"iteration": 1, "papers": [existing],
                              "search_plan": [SearchTask(sq_id="SQ1", query="a b",
                                                         sources=["openalex"])]})
    assert out["papers"] == []


def test_t403_one_failing_source_does_not_sink_the_plan(cfg):
    def flaky(self, source, query, year_min, limit):
        if source == "openalex":
            raise RuntimeError("503")
        return [make_paper("ok")]

    with patch.object(Retriever, "_search", flaky):
        out = Retriever(cfg)({"iteration": 0, "papers": [],
                              "search_plan": [SearchTask(
                                  sq_id="SQ1", query="a b",
                                  sources=["openalex", "arxiv"])]})
    assert len(out["papers"]) == 1
    assert any(row["error"] for row in out["retrieval_log"])


def test_t403_empty_corpus_stops_the_run(cfg):
    with patch.object(Retriever, "_search", lambda *a, **k: []):
        with pytest.raises(ValueError, match="empty corpus"):
            Retriever(cfg)({"iteration": 0, "papers": [],
                            "search_plan": [SearchTask(sq_id="SQ1", query="a b",
                                                       sources=["openalex"])]})


@pytest.mark.parametrize("text,expected", [
    ("David Wadden, Shanchuan Lin, Kyle Lo, Lucy Lu Wang, Madeleine van Zuylen. "
     "Proceedings of EMNLP 2020.", True),
    ("While Large Language Models have shown promise, we propose a method that "
     "improves accuracy across three benchmarks and report ablations.", False),
])
def test_t403_detects_metadata_masquerading_as_an_abstract(text, expected):
    """~1.9% of OpenAlex records carry an author list where the abstract should
    be. Left in, each costs a wasted extraction call and an empty insight row."""
    assert looks_like_author_list(text) is expected


def test_t403_short_titles_do_not_collide():
    assert title_key("Short") == ""


# --------------------------------------------------------------------------
# T-404 — the Extractor
# --------------------------------------------------------------------------


def test_t404_strips_echoed_schema_placeholders(cfg):
    """T-004 measured one model echoing the literal placeholder "string" into
    datasets/metrics on 2 of 5 papers - output that parses, validates, and
    injects fabricated content into a hallucination-graded pipeline."""
    llm = StubLLM(json.dumps({"methodology": "A real method",
                              "datasets": ["string", "SciFact"],
                              "metrics": ["string"]}))
    insight, stats = Extractor(llm, cfg).extract_one(make_paper("p"), "text")
    assert insight.datasets == ["SciFact"]
    assert insight.metrics == []
    assert stats["placeholder_echoes"] == 2


def test_t404_never_aborts_the_run_on_an_unparseable_paper(cfg):
    """SPEC 14.2. With ~60 papers a single bad response would otherwise destroy
    a 30-minute pipeline at paper 47."""
    llm = StubLLM("junk", "junk", "junk")
    insight, stats = Extractor(llm, cfg).extract_one(make_paper("p"), "text")
    assert stats["failed"] is True
    assert insight.paper_id == "p"
    assert "extraction failed" in (insight.extraction_note or "")
    assert field_coverage(insight) == 0


def test_t404_is_fail_soft():
    assert Extractor.fail_soft is True


def test_t404_skips_papers_with_no_text_without_calling_the_model(cfg):
    llm = StubLLM()
    out = Extractor(llm, cfg)({"iteration": 0,
                               "papers": [make_paper("p", abstract=None)]})
    assert llm.calls == 0
    assert "citable as existing only" in out["paper_insights"][0].extraction_note


def test_t404_takes_the_ranked_prefix_not_insertion_order(cfg):
    """Extractor reads papers[:max_papers]. Without the Ranker's order that
    prefix is 'whichever query ran first' - the exact defect that made the
    T-212 harness read 0.029 instead of 0.057."""
    papers = [make_paper(f"p{i}") for i in range(5)]
    llm = StubLLM(*[json.dumps({"methodology": "m"})] * 5)
    small = cfg.model_copy(
        update={"review": cfg.review.model_copy(update={"max_papers": 2})})
    out = Extractor(llm, small)({
        "iteration": 0, "papers": papers,
        "artefacts": {"ranked_paper_ids": ["p4", "p3", "p0", "p1", "p2"]},
    })
    assert [i.paper_id for i in out["paper_insights"]] == ["p4", "p3"]


def test_field_coverage_counts_the_eight_content_fields():
    assert field_coverage(PaperInsight(paper_id="p")) == 0
    assert field_coverage(PaperInsight(paper_id="p", methodology="m",
                                       datasets=["d"])) == 2


# --------------------------------------------------------------------------
# T-406 — the Writer
# --------------------------------------------------------------------------


def test_t406_drops_citations_that_resolve_to_nothing():
    """An unresolvable [n] in a survey about citation accuracy is the most
    embarrassing possible defect, so markers are verified, not trusted."""
    text, dropped, used = Writer._resolve_citations(
        "A claim [1]. Another [2]. A bogus one [9].", 2)
    assert dropped == 1
    assert used == {1, 2}
    assert "[9]" not in text


def test_t406_marks_abstract_only_papers_in_the_evidence_block():
    """T-505: they may be cited as existing but not as the sole support for a
    specific technical claim. The model has to be told which ones they are."""
    paper = make_paper("p")
    block, cited = Writer._evidence_block([paper], {})
    assert "ABSTRACT ONLY" in block
    assert cited == [paper]


def test_t406_evidence_block_numbers_are_the_citation_keys():
    papers = [make_paper(f"p{i}") for i in range(3)]
    block, _ = Writer._evidence_block(papers, {})
    assert "[1]" in block and "[2]" in block and "[3]" in block


# --------------------------------------------------------------------------
# T-405 / T-407 — graph wiring and artefacts
# --------------------------------------------------------------------------


def test_t405_pipeline_order_is_the_documented_one(cfg):
    from researchgpt.graph.build import make_agents

    names = [a.name for a in make_agents(cfg, StubLLM(), None)]
    assert names == ["planner", "retriever", "ranker", "extractor", "writer"]


def test_t405_sequential_runner_applies_the_same_reducers_as_langgraph():
    """If _merge replaced instead of accumulating, the Critic loop would lose
    papers; if it accumulated the replace-fields, insights would pile up."""
    from researchgpt.graph.build import _merge

    state = {"papers": [make_paper("a")], "paper_insights": [PaperInsight(paper_id="x")],
             "artefacts": {"k": 1}}
    _merge(state, {"papers": [make_paper("b")],
                   "paper_insights": [PaperInsight(paper_id="y")],
                   "artefacts": {"j": 2}})
    assert [p.paper_id for p in state["papers"]] == ["a", "b"]      # accumulate
    assert [i.paper_id for i in state["paper_insights"]] == ["y"]   # replace
    assert state["artefacts"] == {"k": 1, "j": 2}                   # merge


def test_t407_artefact_writers_never_raise_into_the_pipeline(tmp_path):
    """A 30-minute run that completes and then dies formatting a CSV has lost
    everything for no reason."""
    from researchgpt.output.writers import write_bibtex, write_insight_table

    # A paper whose fields are wrong types: the writer must cope or return None.
    assert write_bibtex(tmp_path, [make_paper("p")]) is not None
    assert write_insight_table(tmp_path, [], [PaperInsight(paper_id="orphan")]) is not None


def test_t407_bibtex_uses_misc_when_there_is_no_venue(tmp_path):
    """Claiming @article for something we only know the title of is a small
    fabrication in a project whose subject is citation accuracy."""
    from researchgpt.output.writers import write_bibtex

    path = write_bibtex(tmp_path, [make_paper("p")])
    assert "@misc{" in path.read_text(encoding="utf-8")


def test_t407_insight_csv_has_the_four_graded_fields(tmp_path):
    from researchgpt.output.writers import write_insight_table

    path = write_insight_table(tmp_path, [make_paper("p")],
                               [PaperInsight(paper_id="p", methodology="m")])
    header = path.read_text(encoding="utf-8").splitlines()[0]
    for field in ("methodology", "advantages", "disadvantages", "critique"):
        assert field in header


def test_prompts_all_render_with_their_placeholders():
    """A prompt that fails to render is discovered at the first live call,
    mid-run. A bare '$' in prose is enough to break Template.substitute."""
    from researchgpt.core.prompts import load

    assert load("planner_v1", research_question="q", constraints="{}")
    assert load("extractor_v1", title="t", text_availability="full", text="x")
    assert load("writer_v1", theme="t", evidence="e")


# --------------------------------------------------------------------------
# T-406 — the uncited-section defect found by the first M1 run
# --------------------------------------------------------------------------


def test_t406_retries_a_section_that_forgot_to_cite_anything(cfg):
    """First M1 run: "Methods and Architectures" came back as 6,751 characters
    with ZERO [n] markers. Nothing caught it, because zero markers means zero
    DROPPED markers, so every integrity counter read clean."""
    uncited = "This is a long uncited essay about methods. " * 20
    cited = "A grounded claim [1]. " * 20
    llm = StubLLM(uncited, cited, cited, cited, cited)
    out = Writer(llm, cfg)({
        "iteration": 0, "papers": [make_paper("p")],
        "paper_insights": [PaperInsight(paper_id="p", methodology="m")],
        "sub_questions": [SubQuestion(sq_id="SQ1", text="t", facet="method")],
        "research_question": "q",
    })
    assert llm.calls >= 2, "the uncited section should have been retried"
    assert "[1]" in out["final_review"]


def test_t406_rejects_a_section_still_uncited_after_the_retry(cfg):
    """Unverifiable prose is worse than a missing section - the Verifier drops
    unsupported claims, so the Writer must not emit unsupported sections."""
    uncited = "This is a long uncited essay about methods. " * 20
    llm = StubLLM(uncited, uncited)
    # .run() directly: __call__ adds fail_soft, which correctly contains the
    # error so one bad section cannot kill a 30-minute run. The pipeline-level
    # guard in graph/build.py is what turns "no review at all" into a failure.
    with pytest.raises(ValueError, match="no cited section"):
        Writer(llm, cfg).run({
            "iteration": 0, "papers": [make_paper("p")],
            "paper_insights": [PaperInsight(paper_id="p", methodology="m")],
            "sub_questions": [SubQuestion(sq_id="SQ1", text="t", facet="method")],
            "research_question": "q",
        })


def test_t405_pipeline_refuses_to_report_success_with_no_review(cfg, tmp_path):
    """The Writer is fail_soft, so a total failure would otherwise exit 0 with
    an empty review.md - success by silence."""
    import researchgpt.graph.build as build

    class DeadWriter(Writer):
        def run(self, state):
            raise ValueError("no cited section survived")

    def agents(cfg_, llm_, trace_):
        return [DeadWriter(llm_, cfg_, trace=trace_)]

    with patch.object(build, "make_agents", agents):
        with patch.object(build, "TraceLogger") as tl:
            tl.return_value.run_dir = tmp_path
            with pytest.raises(RuntimeError, match="produced no review"):
                build.run_pipeline("q", cfg, run_id="dead", write_artefacts=False)


def test_t406_a_short_uncited_fragment_is_not_rejected(cfg):
    """A one-line transitional sentence carrying no citation is not the defect;
    a 6,751-character uncited essay is. The threshold has to tell them apart."""
    from researchgpt.agents.writer import MIN_CITED_SECTION_CHARS

    assert 200 <= MIN_CITED_SECTION_CHARS <= 1000


def test_config_names_the_retrained_reranker_after_t332r():
    """T-335 was reverted on M1 evidence - the tuned model put an IoT paper
    above the most relevant paper in a real Planner-generated pool - and then
    re-adopted on 2026-08-28 once T-332R retrained it with mixed negatives and
    the relevance control came back clean (0/15, from 11/15).

    Phase 4 cares because the graph builds its Ranker from this value.
    """
    import pathlib as _p

    cfg_text = (_p.Path("configs/default.yaml")).read_text(encoding="utf-8")
    assert "reranker: data/models/reranker-mixed-onnx" in cfg_text
    assert "T-335 RE-ADOPTED" in cfg_text
    assert "REVERTED" in cfg_text, "the reversal is why the retrain exists; keep it"


# --------------------------------------------------------------------------
# T-404 — the zero-cost tier's prompt budget
# --------------------------------------------------------------------------


def test_t404_prompt_stays_inside_the_free_tier_body_limit(cfg):
    """Measured 2026-08-27: Groq rejects a request body over ~20 KB with HTTP
    413. Because extract_one is fail-soft, an over-budget prompt was absorbed
    as a parse failure and reported as 0/8 fields on every paper - a hard
    infrastructure limit wearing the costume of a quality collapse."""
    from researchgpt.agents.extractor import MAX_PROMPT_CHARS

    long_paper = make_paper("p", abstract="word " * 3000)  # 15k chars of source
    prompt, truncated = Extractor(StubLLM(), cfg)._fit_prompt(long_paper,
                                                              long_paper.abstract)
    assert len(prompt) <= MAX_PROMPT_CHARS
    assert truncated > 0, "an oversized source should have been trimmed"
    assert "[truncated to fit the prompt budget]" in prompt


def test_t404_trims_the_source_not_the_examples(cfg):
    """The examples are what make the output well-formed; a truncated abstract
    still extracts most of its content because abstracts front-load method and
    result."""
    long_paper = make_paper("p", abstract="word " * 3000)
    prompt, _ = Extractor(StubLLM(), cfg)._fit_prompt(long_paper, long_paper.abstract)
    assert prompt.count("### Example") == 6, "few-shot examples must survive trimming"


def test_t404_short_papers_are_not_truncated(cfg):
    paper = make_paper("p", abstract="A normal length abstract. " * 20)
    prompt, truncated = Extractor(StubLLM(), cfg)._fit_prompt(paper, paper.abstract)
    assert truncated == 0
    assert "[truncated" not in prompt


def test_prompt_loader_names_a_stray_dollar_sign(tmp_path, monkeypatch):
    """string.Template's own error is just "Invalid placeholder at line N, col
    M", which does not say what is wrong. A bare '$' in prose has broken three
    prompts now, so the loader names the offending line."""
    import researchgpt.core.prompts as prompts

    bad = tmp_path / "broken_v1.md"
    bad.write_text("A prompt mentioning $0 cost.\n\nBODY: $body\n", encoding="utf-8")
    monkeypatch.setattr(prompts, "PROMPT_DIR", tmp_path)
    with pytest.raises(ValueError, match="bare '\$'"):
        prompts.load("broken_v1", body="x")
