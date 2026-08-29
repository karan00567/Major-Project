"""T-410 acceptance — query widening, and the cap that was never applied.

Offline. These test the *mechanism* that T-409's recall failure exposed; the
recall number itself is measured by a live run (``eval/flagship_recall.py``).

WHY THIS EXISTS (measured 2026-08-29, against the 34 gold papers whose
title+abstract OpenAlex actually holds):

    query set                                   gold papers the AND filter
                                                can reach, at ANY cap
    the flagship's 12 Planner queries                    3 / 34
    the same 12, plus every 2-term subset               31 / 34

``filter=title_and_abstract.search:<q>`` ANDs every term, so a paper missing
one term is excluded at the source - before ranking, fusion or the per-query
cap can see it. The flagship run scored union recall 2/35 against a ceiling of
3/34: it was not underperforming, it was *at* its ceiling. Widening the query
is therefore the only change that can raise the ceiling, and raising the cap is
the only change that can then collect what the wider query reaches. Neither
works alone, which is what these tests pin.
"""

from __future__ import annotations

import pathlib
from unittest.mock import patch

import pytest

from researchgpt.agents.planner import Planner
from researchgpt.agents.retriever import Retriever, expand_query
from researchgpt.core.config import load_config
from researchgpt.core.models import Paper, SearchTask

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cfg():
    return load_config(str(REPO / "configs" / "default.yaml"))


def make_paper(pid):
    return Paper(
        paper_id=pid, doi=f"10.1/{pid}",
        title=f"A sufficiently long distinctive title number {pid}",
        source="openalex", abstract="An abstract. " * 30,
    )


# --------------------------------------------------------------------------
# expand_query — the widening itself
# --------------------------------------------------------------------------


def test_t410_expansion_leads_with_the_original_query():
    """The Planner's own query is still asked first. Widening ADDS reach; it
    must never replace the specific query the plan asked for."""
    out = expand_query("prompt design retrieval agents")
    assert out[0] == "prompt design retrieval agents"


def test_t410_expansion_emits_every_two_term_subset():
    """Measured: the best-reaching pair is not predictable from position. For
    'multi agent retrieval architecture' it is 'multi retrieval'; for
    'benchmark dataset literature review' it is 'benchmark dataset'. A
    head-pair heuristic reaches 25/34, all pairs reach 31/34, so we issue all
    of them."""
    out = expand_query("prompt design retrieval agents")
    pairs = set(out[1:])
    assert pairs == {
        "prompt design", "prompt retrieval", "prompt agents",
        "design retrieval", "design agents", "retrieval agents",
    }


def test_t410_expansion_drops_stopwords_before_pairing():
    """'hallucination in scientific summarization' is 4 tokens but 3 TERMS.
    Pairing on the raw tokens would spend searches on 'hallucination in'."""
    out = expand_query("hallucination in scientific summarization")
    assert all(" in" not in q and "in " not in q for q in out[1:])
    assert set(out[1:]) == {
        "hallucination scientific", "hallucination summarization",
        "scientific summarization",
    }


def test_t410_a_two_term_query_expands_to_itself_alone():
    """Its only pair IS itself. Issuing it twice would pay for the same search
    twice against a metered daily budget."""
    assert expand_query("RAG survey") == ["RAG survey"]


def test_t410_expansion_is_deduplicated_and_order_stable():
    """The retrieval log and the trace are read by a human comparing runs."""
    q = "retrieval augmented retrieval review"
    out = expand_query(q)
    assert len(out) == len(set(out)), out
    assert out == expand_query(q)


# --------------------------------------------------------------------------
# The cap that was never applied
# --------------------------------------------------------------------------


def test_t410_planner_does_not_pin_the_per_query_cap(cfg):
    """🔴 REGRESSION. The retriever caps at ``min(task.max_results,
    max_per_source)`` and the Planner used to hardcode ``max_results or 25`` -
    a value its own prompt puts in every few-shot example. Raising
    ``max_per_source`` to 100 in the config was therefore a NO-OP: min(25, 100)
    is 25. The retrieval budget is an operator decision, not a model one, so
    the model's number is ignored and the field is left unset."""
    payload = {
        "sub_questions": [
            {"id": f"SQ{i}", "text": f"What is X{i}?", "facet": facet}
            for i, facet in enumerate(
                ["method", "evaluation", "limitation", "application"], 1
            )
        ],
        "search_plan": [
            {"sq_id": f"SQ{i}", "query": "retrieval augmented generation",
             "sources": ["openalex"], "max_results": 25}
            for i in range(1, 5)
        ],
        "assumptions": [],
    }
    _, plan, _ = Planner._validate(payload)
    assert plan[0].max_results is None, (
        "the model's max_results must not become the cap; leave it unset so "
        "sources.max_per_source governs"
    )


def test_t410_retriever_asks_every_source_for_the_configured_cap(cfg):
    """The end of the same regression: with the field unset, the retriever must
    ask for the operator's ``max_per_source``, not 25."""
    seen: list[tuple[str, int]] = []

    def spy(self, source, query, year_min, limit):
        seen.append((query, limit))
        return [make_paper(f"{query}-{limit}")]

    with patch.object(Retriever, "_search", spy):
        Retriever(cfg)({"iteration": 0, "papers": [],
                        "search_plan": [SearchTask(sq_id="SQ1", query="a b",
                                                   sources=["openalex"])]})
    assert seen, "no search was issued"
    assert {limit for _, limit in seen} == {cfg.sources.max_per_source}


def test_t410_retriever_issues_the_widened_queries(cfg):
    """One 4-term task becomes 7 searches: the original plus 6 pairs."""
    seen: list[str] = []

    def spy(self, source, query, year_min, limit):
        seen.append(query)
        return [make_paper(query)]

    with patch.object(Retriever, "_search", spy):
        out = Retriever(cfg)({"iteration": 0, "papers": [],
                              "search_plan": [
                                  SearchTask(sq_id="SQ1",
                                             query="prompt design retrieval agents",
                                             sources=["openalex"])]})
    assert seen == expand_query("prompt design retrieval agents")
    assert len(out["papers"]) == 7


def test_t410_the_widened_queries_are_traceable_to_their_parent(cfg):
    """A run is diagnosed from ``retrieval_log`` months later. A log that says
    only 'prompt retrieval' loses which planned task asked for it - and every
    comparison of a widened run against the flagship needs that link."""
    with patch.object(Retriever, "_search",
                      lambda self, s, q, y, limit: [make_paper(q)]):
        out = Retriever(cfg)({"iteration": 0, "papers": [],
                              "search_plan": [
                                  SearchTask(sq_id="SQ1",
                                             query="prompt design retrieval agents",
                                             sources=["openalex"])]})
    log = out["retrieval_log"]
    assert {row["query"] for row in log} == set(expand_query("prompt design retrieval agents"))
    assert {row["planned_query"] for row in log} == {"prompt design retrieval agents"}
    assert {row["sq_id"] for row in log} == {"SQ1"}


# --------------------------------------------------------------------------
# The connector bug the investigation turned up
# --------------------------------------------------------------------------


def test_t410_openalex_query_escapes_filter_metacharacters():
    """🔴 A comma or a question mark in a query returns HTTP 400 from OpenAlex:
    both are filter-syntax metacharacters (`,` separates filters, `?` ends the
    query string) and neither was escaped. Measured 2026-08-29 - it killed 3 of
    21 title probes. `:`, `|`, apostrophes and unicode hyphens are all fine.

    The main path survives today only because the Planner happens to emit bare
    keywords; nothing stops an LLM emitting a comma."""
    from researchgpt.tools.search_sources import sanitise_openalex_query as clean

    assert "," not in clean("natural language processing, machine learning")
    assert "?" not in clean("can large language models replace humans?")
    # Legitimate characters survive: stripping them would change the query.
    assert clean("hallucination: a survey") == "hallucination: a survey"
    assert clean("gpt-4's efficacy") == "gpt-4's efficacy"


# --------------------------------------------------------------------------
# The metrics harness (eval/run_metrics.py)
# --------------------------------------------------------------------------


def _fake_run(tmp_path, *, gold_at, n=10, extracted=3, ranked=True):
    """A run directory with gold papers planted at known RANK positions."""
    import json

    papers = []
    for i in range(1, n + 1):
        doi = gold_at.get(i) or f"10.9999/filler{i}"
        papers.append({"paper_id": f"W{i}", "doi": doi,
                       "title": f"A sufficiently long distinctive filler title {i}",
                       "source": "openalex"})
    run_dir = tmp_path / "fake"
    run_dir.mkdir()
    (run_dir / "corpus.json").write_text(json.dumps({
        "papers": papers,
        "extracted_paper_ids": [f"W{i}" for i in range(1, extracted + 1)],
        "retrieval_log": [
            {"sq_id": "SQ1", "query": "a b", "planned_query": "a b c",
             "source": "openalex", "returned": 5, "new": 5, "error": None},
            {"sq_id": "SQ1", "query": "a c", "planned_query": "a b c",
             "source": "arxiv", "returned": 0, "new": 0, "error": None},
        ],
    }), encoding="utf-8")
    trace = [
        {"ts": "2026-08-29T10:00:00Z", "agent": "graph", "event": "run_start",
         "iteration": 0, "payload": {}},
        {"ts": "2026-08-29T10:00:10Z", "agent": "verifier",
         "event": "verification_summary", "iteration": 0,
         "payload": {"claims": 20, "supported": 4, "partial": 12, "dropped": 4,
                     "contradicted": 0, "grounding_score": 0.8}},
        {"ts": "2026-08-29T10:05:00Z", "agent": "graph", "event": "run_end",
         "iteration": 0, "payload": {}},
    ]
    if ranked:
        trace.insert(1, {"ts": "2026-08-29T10:00:05Z", "agent": "ranker",
                         "event": "rank_summary", "iteration": 0,
                         "payload": {"ranked": n}})
    (run_dir / "trace.jsonl").write_text(
        "\n".join(json.dumps(r) for r in trace), encoding="utf-8")
    return run_dir


def test_t410_metrics_read_precision_and_recall_off_the_RANK_position(tmp_path):
    """@k is only meaningful if corpus.json is in ranked order. Two gold papers
    planted at ranks 2 and 8 must show up at k=10 and not before k=2."""
    from researchgpt.eval.run_metrics import load_run, retrieval_metrics

    run_dir = _fake_run(tmp_path, gold_at={2: "10.1162/tacl_a_00530",
                                           8: "10.1145/3703155"})
    corpus, _ = load_run(run_dir)
    m = retrieval_metrics(corpus)

    assert m["best_rank"] == 2
    assert m["union_recall"] == 2 / m["gold_papers"]
    assert m["at_k"][10] == {"hits": 2, "recall": 2 / m["gold_papers"],
                             "precision": 0.2}


def test_t410_corpus_recall_counts_only_what_the_extractor_read(tmp_path):
    """A gold paper at rank 8 is retrieved but NOT extracted when the corpus is
    the top 3 - the distinction the whole 'union vs corpus' split exists for."""
    from researchgpt.eval.run_metrics import load_run, retrieval_metrics

    run_dir = _fake_run(tmp_path, gold_at={2: "10.1162/tacl_a_00530",
                                           8: "10.1145/3703155"}, extracted=3)
    corpus, _ = load_run(run_dir)
    m = retrieval_metrics(corpus)
    assert m["union_recall"] == 2 / m["gold_papers"]
    assert m["corpus_recall"] == 1 / m["gold_papers"]


def test_t410_metrics_flag_a_run_whose_corpus_is_insertion_order(tmp_path):
    """Without a rank_summary the file is whichever query ran first, and every
    @k number is a fiction. Say so rather than printing it."""
    from researchgpt.eval.run_metrics import collect

    _fake_run(tmp_path, gold_at={}, ranked=False)
    m = collect("fake", tmp_path, tmp_path)
    assert m["ranking_order_verified"] is False


def test_t410_the_two_precisions_are_not_the_same_number(tmp_path):
    """grounding precision keeps PARTIAL claims; strict precision does not.
    Conflating them is how 'zero SUPPORTED claims' gets reported as 0.82."""
    from researchgpt.eval.run_metrics import collect

    _fake_run(tmp_path, gold_at={})
    v = collect("fake", tmp_path, tmp_path)["quality"]["verification"]
    assert v["grounding_precision"] == 16 / 20   # 20 claims, 4 dropped
    assert v["strict_precision"] == 4 / 20       # only the SUPPORTED ones


# --------------------------------------------------------------------------
# The failure the bigger pool exposed
# --------------------------------------------------------------------------


def _chunks(n):
    from researchgpt.core.models import Chunk

    return [Chunk(chunk_id=f"c{i}", paper_id=f"p{i}", text=f"chunk {i}",
                  section="abstract", start_char=0, end_char=7) for i in range(n)]


def test_t410_vectorstore_batches_writes_beyond_chromas_limit(tmp_path):
    """🔴 REGRESSION - this killed the first T-410 run at 31 minutes, after
    retrieval and most of the embedding had already been paid for:

        chromadb.errors.InternalError: ValueError: Batch size of 15166 is
        greater than max batch size of 5461

    ``VectorStore.add`` upserted every chunk in ONE call. Chroma's local
    backend caps a batch at 5,461 (SQLite's variable limit divided by the
    bindings per row). The flagship's 640 chunks never came close; a
    max_per_source of 100 produces 15,166 and the write dies - so the cap is a
    function of pool size, and any future widening walks back into it.

    The limit is read from the client, never hardcoded, because it is a
    property of Chroma's build and not of this project.
    """
    from researchgpt.data.vectorstore import VectorStore

    store = VectorStore(path=str(tmp_path / "vs"), collection="t410", max_batch=10)
    seen: list[int] = []
    real = store._collection.upsert

    def guarded(**kwargs):
        seen.append(len(kwargs["ids"]))
        if len(kwargs["ids"]) > 10:  # Chroma's own guard, at a testable size
            raise RuntimeError(
                f"Batch size of {len(kwargs['ids'])} is greater than max batch size of 10"
            )
        return real(**kwargs)

    store._collection.upsert = guarded
    store.add(_chunks(25), [[float(i)] * 8 for i in range(25)])

    assert max(seen) <= 10, f"a batch exceeded the limit: {seen}"
    assert sum(seen) == 25, f"chunks were dropped, not batched: {seen}"
    assert store.count() == 25


def test_t410_batch_limit_comes_from_the_client_not_a_constant(tmp_path):
    """Hardcoding 5461 would silently break on a Chroma build with a different
    limit - and the number is derived from SQLite's variable cap, not chosen."""
    from researchgpt.data.vectorstore import VectorStore

    store = VectorStore(path=str(tmp_path / "vs2"), collection="t410b")
    assert store.max_batch == store._client.get_max_batch_size()


def test_t410_retriever_dedups_on_paper_id_when_doi_and_title_cannot(cfg):
    """🔴 REGRESSION - this killed the second T-410 run.

        PartialStateViolation: retriever returned 1 papers that are ALREADY in
        state (e.g. ['W3167518830'])

    Two dedup identities disagreed. The retriever keys on DOI, then on a title
    of >=25 alphanumeric characters. ``W3167518830`` is titled "JBI evidence
    synthesis" - 20 characters - and carries no DOI, so BOTH keys are empty and
    it can never be recognised on a second pass. ``base.py::_check_partial``
    then compares by ``paper_id``, finds it already in state, and raises.

    ⚠️ This is not only a resume problem. Any second retrieval pass hits it,
    including the Critic's RETRIEVE loop, which is the path T-509 exists to
    prove. paper_id is the identity the contract is enforced on, so it has to
    be the last-resort key here too.
    """
    ghost = Paper(paper_id="W3167518830", doi=None, title="JBI evidence synthesis",
                  source="openalex", abstract="An abstract. " * 30)

    with patch.object(Retriever, "_search", lambda self, s, q, y, limit: [ghost]):
        out = Retriever(cfg)({"iteration": 1, "papers": [ghost],
                              "search_plan": [SearchTask(sq_id="SQ1", query="a b",
                                                         sources=["openalex"])]})
    assert out["papers"] == [], (
        "a paper already in state was returned again; the `add` reducer would "
        "duplicate it and _check_partial rejects the whole update"
    )


def test_t410_resume_passes_none_when_the_thread_has_checkpoints():
    """🔴 REGRESSION - T-508's resume was inert. LangGraph resumes only when
    invoked with None; given an input it starts the graph over from START,
    which is what re-paid a 9-minute retrieval and then crashed the retriever
    against its own accumulated state."""
    from researchgpt.graph.checkpoint import resume_input

    state = {"run_id": "r", "iteration": 0}
    config = {"configurable": {"thread_id": "r"}}

    class Fresh:
        def get_tuple(self, cfg):
            return None

    class Resumable:
        def get_tuple(self, cfg):
            return object()

    class Broken:
        def get_tuple(self, cfg):
            raise RuntimeError("checkpoint db unreadable")

    assert resume_input(Fresh(), config, state) is state, "a new thread runs normally"
    assert resume_input(Resumable(), config, state) is None, "an existing thread resumes"
    # A checkpointer that cannot be read must not stop the run: start over
    # rather than raise. Resume is an optimisation, never a dependency.
    assert resume_input(Broken(), config, state) is state
