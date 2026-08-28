"""Phase 2 acceptance checks from handoffs/phase2.md.

Does NOT edit TASKLIST.md. Reports pass/fail to stdout.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import httpx

from researchgpt.core.models import Chunk, Paper, RetrievalConfig
from researchgpt.data.bm25_index import BM25Index
from researchgpt.data.chunker import chunk_paper
from researchgpt.data.embeddings import Embedder
from researchgpt.data.metadata_db import MetadataDB, dedup_papers
from researchgpt.data.vectorstore import VectorStore
from researchgpt.tools import search_sources as _ss
from researchgpt.tools.hybrid_retriever import HybridRetriever, rrf_fuse
from researchgpt.tools.pdf_loader import load_paper_text, parse_pdf
from researchgpt.tools.reranker import Reranker
from researchgpt.tools.search_sources import (
    arxiv_id_to_doi,
    deinvert_abstract,
    infer_venue_tier,
    normalise_doi,
    search_arxiv,
    search_openalex,
    search_semantic_scholar,
)


def test_t201_openalex() -> None:
    papers = search_openalex(
        "agentic retrieval augmented generation",
        year_min=2023,
        max_results=20,
    )
    assert len(papers) >= 20, f"got {len(papers)}"
    for p in papers:
        assert p.title
        assert p.doi is None or ("/" in p.doi and p.doi == p.doi.lower() and not p.doi.startswith("http"))
        if p.doi:
            assert p.doi == normalise_doi(p.doi)
        if p.abstract:
            assert len(p.abstract) > 40
    # At least some abstracts de-inverted
    with_abs = [p for p in papers if p.abstract and len(p.abstract) > 40]
    assert len(with_abs) >= 5, f"only {len(with_abs)} long abstracts"
    print(f"T-201 OK ({len(papers)} papers, {len(with_abs)} with abstract)")


def test_t202_arxiv() -> None:
    assert arxiv_id_to_doi("2506.21931v2") == "10.48550/arxiv.2506.21931"
    papers = search_arxiv("agentic retrieval augmented generation", max_results=10)
    assert len(papers) == 10, f"got {len(papers)}"
    for p in papers:
        assert "\n" not in p.title
        assert p.doi and p.doi.startswith("10.48550/arxiv.")
        # (An earlier assertion here referenced an undefined name inside a
        #  short-circuited generator, so it never ran. Removed 2026-08-26; the
        #  two checks below cover the same intent and actually execute.)
        # version stripped: no trailing vN
        assert not p.doi.rstrip("0123456789").endswith("v")
        assert p.url and ("pdf" in p.url or "arxiv.org" in p.url)
        assert p.venue_tier == "preprint"
        assert p.is_preprint
    # Explicit version strip check
    for p in papers:
        suffix = p.doi.split("arxiv.")[-1]
        assert "v" not in suffix, suffix
    print(f"T-202 OK ({len(papers)} papers)")


def test_t203_dedup() -> None:
    oa = search_openalex("retrieval augmented generation", year_min=2023, max_results=15)
    arx = search_arxiv("retrieval augmented generation", max_results=10)
    merged = dedup_papers(oa + arx)
    dois = [p.doi for p in merged if p.doi]
    assert len(dois) == len(set(dois)), "duplicate DOIs after dedup"

    # Force a known synthetic-DOI collision if present
    arxiv_dois = {p.doi for p in arx if p.doi}
    oa_overlap = [p for p in oa if p.doi in arxiv_dois]
    if oa_overlap:
        sample_doi = oa_overlap[0].doi
        pair = [p for p in oa + arx if p.doi == sample_doi]
        one = dedup_papers(pair)
        assert len(one) == 1
        survivor = one[0]
        assert survivor.doi == sample_doi
        # Prefer richer: should have abstract and ideally pdf-ish url
        assert survivor.abstract or survivor.url
        print(f"T-203 OK (overlap doi={sample_doi}, n={len(merged)})")
    else:
        # Synthetic merge test
        a = Paper(
            paper_id="W1",
            doi="10.48550/arxiv.2501.00001",
            title="T",
            source="openalex",
            venue="Some Venue",
            citation_count=10,
            abstract="long abstract text here",
            url=None,
        )
        b = Paper(
            paper_id="2501.00001v1",
            doi="10.48550/arxiv.2501.00001",
            title="T",
            source="arxiv",
            venue="arXiv",
            abstract=None,
            url="https://arxiv.org/pdf/2501.00001.pdf",
            is_preprint=True,
            venue_tier="preprint",
        )
        one = dedup_papers([a, b])
        assert len(one) == 1
        assert one[0].abstract
        assert one[0].url and "arxiv" in one[0].url
        assert one[0].venue == "Some Venue" or one[0].citation_count == 10
        print(f"T-203 OK (synthetic merge, live n={len(merged)})")

    with tempfile.TemporaryDirectory() as tmp:
        db = MetadataDB(path=str(Path(tmp) / "m.db"))
        try:
            n = db.upsert_papers(merged[:5])
            assert n == 5
            assert db.count() == 5
            assert db.get(merged[0].paper_id) is not None
        finally:
            db.close()


def test_t204_pdf() -> None:
    papers = search_arxiv("retrieval augmented generation", max_results=12)
    with tempfile.TemporaryDirectory() as tmp:
        ok = 0
        for p in papers:
            text, avail = load_paper_text(p, dest_dir=tmp)
            if avail == "full" and len(text) > 500:
                # Confirm at least one section detected on a saved PDF
                pdfs = list(Path(tmp).glob("*.pdf"))
                assert pdfs
                _t, sections = parse_pdf(str(pdfs[-1]))
                if _t.strip() and sections:
                    ok += 1
            if ok >= 10:
                break
        assert ok >= 10, f"only {ok}/10 OA PDFs parsed with sections"

        # Paywalled-style: DOI url that is not a PDF
        paywalled = Paper(
            paper_id="paywall1",
            title="Paywalled",
            source="openalex",
            url="https://doi.org/10.1016/j.nlp.2025.100179",
            abstract="This is an abstract only fallback text for the paper.",
        )
        text, avail = load_paper_text(paywalled, dest_dir=tmp)
        assert avail == "abstract_only"
        assert text.startswith("This is an abstract")

        # Corrupted PDF
        bad = Path(tmp) / "corrupt.pdf"
        bad.write_bytes(b"not a pdf")
        t, secs = parse_pdf(str(bad))
        assert t == "" and secs == []
    print(f"T-204 OK (parsed {ok} OA PDFs)")


def test_t205_chunker() -> None:
    text = (
        "Abstract\n" + ("This paper studies retrieval. " * 40)
        + "\n\n1. Introduction\n" + ("We introduce agentic RAG systems. " * 40)
        + "\n\n2. Methods\n" + ("Our method uses hybrid search. " * 40)
        + "\n\nReferences\n[1] Someone. A paper. 2024.\n"
    )
    # Use offsets from a simple section list covering the whole text
    sections = [
        ("abstract", 0, text.index("1. Introduction")),
        ("introduction", text.index("1. Introduction"), text.index("2. Methods")),
        ("methods", text.index("2. Methods"), text.index("References")),
        ("references", text.index("References"), len(text)),
    ]
    # Simulate pdf_loader truncation: drop references content from text
    cut = text.index("References")
    text2 = text[:cut]
    sections2 = [(n, s, min(e, len(text2))) for n, s, e in sections if s < len(text2)]
    chunks = chunk_paper("p1", text2, sections2, chunk_size=200, chunk_overlap=40)
    assert chunks, "no chunks produced"
    for c in chunks:
        assert text2[c.start_char : c.end_char] == c.text, (
            c.chunk_id,
            c.start_char,
            c.end_char,
            repr(c.text[:40]),
            repr(text2[c.start_char : c.end_char][:40]),
        )
    print(f"T-205 OK ({len(chunks)} chunks, offsets exact)")


def test_t206_embeddings() -> None:
    emb = Embedder()
    assert emb.dim == 384
    q = emb.encode_query("agentic rag")
    assert len(q) == 384
    # 3000 short chunks — wall time printed
    texts = [f"Chunk number {i} about retrieval augmented generation and agents." for i in range(3000)]
    t0 = time.perf_counter()
    vecs = emb.encode(texts, show_progress=False)
    elapsed = time.perf_counter() - t0
    assert len(vecs) == 3000
    assert len(vecs[0]) == 384
    print(f"T-206 OK (dim=384, 3000 chunks in {elapsed:.1f}s)")


def test_t207_vectorstore() -> None:
    emb = Embedder()
    chunks = [
        Chunk(
            chunk_id=f"p:{i:04d}",
            paper_id="p",
            text=f"Document chunk {i} about hybrid retrieval and ranking.",
            section="methods",
            start_char=i * 10,
            end_char=i * 10 + 50,
        )
        for i in range(100)
    ]
    vectors = emb.encode([c.text for c in chunks])
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = VectorStore(path=tmp, collection="t207")
        store.add(chunks, vectors)
        assert store.count() == 100
        q = emb.encode_query("hybrid retrieval ranking")
        hits = store.query(q, k=30)
        assert len(hits) == 30
        scores = [s for _, s in hits]
        assert scores == sorted(scores, reverse=True), "must be descending similarity"
        c0 = store.get_chunk(chunks[0].chunk_id)
        assert c0 is not None
        assert c0.start_char == chunks[0].start_char
        assert c0.end_char == chunks[0].end_char
        assert c0.text == chunks[0].text
        store.reset()
    print("T-207 OK (similarity descending + get_chunk round-trip)")


def test_t208_bm25() -> None:
    chunks = [
        Chunk(
            chunk_id=f"p:{i:04d}",
            paper_id="p",
            text=f"Chunk {i} discusses retrieval ranking bm25 sparse lexical search.",
            section="body",
            start_char=0,
            end_char=60,
        )
        for i in range(100)
    ]
    idx = BM25Index()
    idx.build(chunks)
    hits = idx.query("bm25 sparse retrieval", k=30)
    assert len(hits) == 30
    scores = [s for _, s in hits]
    assert scores == sorted(scores, reverse=True)
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "bm25.pkl")
        idx.save(path)
        idx2 = BM25Index.load(path)
        hits2 = idx2.query("bm25 sparse retrieval", k=30)
        assert [c for c, _ in hits] == [c for c, _ in hits2]
    print("T-208 OK")


def test_t209_rrf() -> None:
    fused = rrf_fuse([["a", "b"], ["b", "a"]], rrf_k=60)
    # a: 1/61 + 1/62 ; b: 1/62 + 1/61 — tied; order stable by insertion of max
    scores = dict(fused)
    assert abs(scores["a"] - scores["b"]) < 1e-12
    # Different rankings case
    fused2 = rrf_fuse([["a", "b", "c"], ["c", "b"]], rrf_k=60)
    ids = [i for i, _ in fused2]
    assert ids != ["a", "b", "c"]
    assert ids != ["c", "b"]
    assert fused2 == rrf_fuse([["a", "b", "c"], ["c", "b"]], rrf_k=60)

    emb = Embedder()
    chunks = [
        Chunk(
            chunk_id=f"p:{i:04d}",
            paper_id="p",
            text=f"Passage {i} on agentic RAG planning and critique loops.",
            section="body",
            start_char=0,
            end_char=50,
        )
        for i in range(50)
    ]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = VectorStore(path=tmp, collection="t209")
        store.add(chunks, emb.encode([c.text for c in chunks]))
        bm25 = BM25Index()
        bm25.build(chunks)
        retr = HybridRetriever(store, bm25, emb, RetrievalConfig(dense_k=20, sparse_k=20))
        results = retr.retrieve("agentic RAG critique")
        assert results
        dense_ids = [c for c, _ in store.query(emb.encode_query("agentic RAG critique"), k=20)]
        sparse_ids = [c for c, _ in bm25.query("agentic RAG critique", k=20)]
        fused_ids = [c.chunk_id for c, _ in results]
        assert fused_ids != dense_ids or fused_ids != sparse_ids
        store.reset()
    print("T-209 OK")


def test_t210_reranker() -> None:
    rr = Reranker()
    chunks = [
        Chunk(
            chunk_id=f"p:{i:04d}",
            paper_id="p",
            text=(
                "Cross-encoder reranking improves precision for retrieval "
                f"augmented generation systems number {i}."
                if i < 5
                else f"Unrelated cooking recipe number {i} with pasta and sauce."
            ),
            section="body",
            start_char=0,
            end_char=80,
        )
        for i in range(60)
    ]
    out = rr.rerank("retrieval augmented generation reranking", chunks, top_k=12)
    assert len(out) == 12
    scores = [s for _, s in out]
    assert scores == sorted(scores, reverse=True)
    assert rr.last_latency_ms > 0
    # Top results should prefer RAG-related chunks
    top_ids = [c.chunk_id for c, _ in out[:5]]
    assert any(int(cid.split(":")[1]) < 5 for cid in top_ids)
    print(f"T-210 OK (latency={rr.last_latency_ms}ms)")


def test_t211_venue_tier() -> None:
    papers = search_openalex(
        "large language model survey", year_min=2023, max_results=20
    )
    tiers = {p.venue_tier for p in papers}
    assert len(tiers) >= 2, tiers  # at least some diversity; 3 preferred
    # Force arxiv search for preprint
    arx = search_arxiv("large language models", max_results=5)
    assert all(p.venue_tier == "preprint" for p in arx)
    # infer_venue_tier guards
    assert infer_venue_tier({"type": "preprint"}) == "preprint"
    assert infer_venue_tier({}) == "unknown"
    if len(tiers) >= 3:
        print(f"T-211 OK (tiers={tiers})")
    else:
        print(f"T-211 OK soft (tiers={tiers}; arXiv all preprint)")


def test_helpers() -> None:
    assert normalise_doi("https://doi.org/10.1016/Foo") == "10.1016/foo"
    assert deinvert_abstract({"hello": [0], "world": [1]}) == "hello world"
    assert deinvert_abstract(None) is None
    print("helpers OK")


# ---------------------------------------------------------------------------
# T-214 - Semantic Scholar connector (handoffs/phase2.md, added 2026-08-25)
# ---------------------------------------------------------------------------

#: One real-shaped result from GET /graph/v1/paper/search.
_S2_JOURNAL_RESULT = {
    "paperId": "b1e2c3d4",
    "externalIds": {
        "DOI": "https://doi.org/10.18653/v1/2023.EMNLP-main.398",
        "ArXiv": "2305.14627",
        "CorpusId": 258841283,
    },
    "title": "Enabling Large Language Models to Generate Text with Citations",
    "abstract": (
        "Large language models (LLMs) have emerged as a widely-used tool for "
        "information seeking, but their generated outputs are prone to hallucination."
    ),
    "year": 2023,
    "venue": "Conference on Empirical Methods in Natural Language Processing",
    "authors": [{"authorId": "1", "name": "Tianyu Gao"}, {"authorId": "2", "name": "Howard Yen"}],
    "citationCount": 412,
    "isOpenAccess": True,
    "openAccessPdf": {"url": "https://aclanthology.org/2023.emnlp-main.398.pdf"},
    "publicationTypes": ["JournalArticle", "Conference"],
}

_S2_PREPRINT_RESULT = {
    "paperId": "f9f9f9f9",
    "externalIds": {"ArXiv": "2506.21931"},
    "title": "A Survey of Agentic Retrieval-Augmented Generation",
    "abstract": "We survey agentic RAG systems and their evaluation.",
    "year": 2026,
    "venue": "",
    "authors": [{"authorId": "3", "name": "A. Researcher"}],
    "citationCount": 0,
    "isOpenAccess": True,
    "openAccessPdf": None,
    "publicationTypes": None,
}


def _s2_transport(pages, status=200, capture=None):
    """httpx.MockTransport serving canned S2 payloads. Real connector code,
    fake socket - nothing inside researchgpt is mocked."""
    seq = list(pages)

    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture.append(request)
        body = seq.pop(0) if seq else {"total": 0, "data": []}
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handler)


def test_t214_maps_s2_result_to_paper() -> None:
    """Field-by-field mapping from handoffs/phase2.md T-214."""
    transport = _s2_transport([{"total": 2, "data": [_S2_JOURNAL_RESULT, _S2_PREPRINT_RESULT]}])
    papers = search_semantic_scholar("citations", max_results=2, _transport=transport)

    assert len(papers) == 2, f"got {len(papers)}"
    journal, preprint = papers

    assert journal.paper_id == "b1e2c3d4"
    # DOI arrives as a mixed-case URL -> bare lowercase, via T-201's helper.
    assert journal.doi == "10.18653/v1/2023.emnlp-main.398", journal.doi
    assert journal.title.startswith("Enabling Large Language Models")
    assert journal.authors == ["Tianyu Gao", "Howard Yen"]
    assert journal.year == 2023
    assert journal.venue == "Conference on Empirical Methods in Natural Language Processing"
    # Abstracts are plain text here - no de-inversion, unlike OpenAlex.
    assert journal.abstract and "hallucination" in journal.abstract
    assert journal.url == "https://aclanthology.org/2023.emnlp-main.398.pdf"
    assert journal.source == "semantic_scholar"
    assert journal.citation_count == 412
    assert journal.is_preprint is False, "JournalArticle in publicationTypes"

    # No DOI, no publicationTypes, empty venue, no OA pdf.
    assert preprint.doi is None
    assert preprint.venue is None, "empty-string venue must normalise to None"
    assert preprint.url is None
    assert preprint.is_preprint is True, "no JournalArticle -> preprint"
    print("T-214 mapping OK")


def test_t214_request_shape_and_api_key_header() -> None:
    """year window, fields list, limit cap; x-api-key ONLY when a key is given."""
    seen: list[httpx.Request] = []
    transport = _s2_transport([{"total": 1, "data": [_S2_JOURNAL_RESULT]}], capture=seen)
    search_semantic_scholar("rag", year_min=2019, max_results=1, _transport=transport)

    req = seen[0]
    assert req.url.path == "/graph/v1/paper/search", req.url
    params = dict(req.url.params)
    assert params["query"] == "rag"
    assert params["year"] == "2019-", params["year"]
    assert int(params["limit"]) <= 100
    for field in ("paperId", "externalIds", "abstract", "openAccessPdf", "publicationTypes"):
        assert field in params["fields"], f"{field} missing from fields="
    assert "x-api-key" not in req.headers, "no key configured -> no header"

    seen.clear()
    transport = _s2_transport([{"total": 1, "data": [_S2_JOURNAL_RESULT]}], capture=seen)
    search_semantic_scholar("rag", max_results=1, api_key="secret-key", _transport=transport)
    assert seen[0].headers.get("x-api-key") == "secret-key"
    print("T-214 request shape OK")


def test_t214_sustained_429_returns_empty_list() -> None:
    """THE point of the task: a throttled supplementary source degrades, it does
    not kill the run. Sustained 429 -> [] + logged warning, never an exception."""
    import logging

    orig = (_ss._BACKOFF_SCHEDULE, _ss._POLITE_SLEEP_S)
    _ss._BACKOFF_SCHEDULE, _ss._POLITE_SLEEP_S = (0.0,) * 6, 0.0
    attempts: list[httpx.Request] = []
    records: list[logging.LogRecord] = []
    try:
        transport = _s2_transport([], status=429, capture=attempts)
        logger = logging.getLogger("researchgpt.tools.search_sources")
        handler = logging.Handler()
        handler.emit = records.append  # type: ignore[method-assign]
        logger.addHandler(handler)
        try:
            out = search_semantic_scholar("rag", max_results=10, _transport=transport)
        finally:
            logger.removeHandler(handler)
    finally:
        _ss._BACKOFF_SCHEDULE, _ss._POLITE_SLEEP_S = orig

    assert out == [], f"expected [] on sustained 429, got {len(out)} papers"
    assert len(attempts) == 6, f"spec says max 6 attempts, made {len(attempts)}"
    assert any(r.levelno >= logging.WARNING for r in records), "no warning logged"
    print("T-214 degradability OK (6 attempts, returned [], warned)")


def test_t214_recovers_when_429_then_200() -> None:
    """Backoff must actually retry, not merely count down to []."""
    orig = (_ss._BACKOFF_SCHEDULE, _ss._POLITE_SLEEP_S)
    _ss._BACKOFF_SCHEDULE, _ss._POLITE_SLEEP_S = (0.0,) * 6, 0.0
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429)
        return httpx.Response(200, json={"total": 1, "data": [_S2_JOURNAL_RESULT]})

    try:
        out = search_semantic_scholar(
            "rag", max_results=1, _transport=httpx.MockTransport(handler)
        )
    finally:
        _ss._BACKOFF_SCHEDULE, _ss._POLITE_SLEEP_S = orig

    assert calls["n"] == 3, calls
    assert len(out) == 1 and out[0].paper_id == "b1e2c3d4"
    print("T-214 retry-then-succeed OK")


def test_t214_live() -> None:
    """DONE WHEN: >=5 Papers with populated abstracts and normalised DOIs.

    Keyless S2 is measured-unreliable (1 of 4 rapid requests succeeded,
    2026-08-25), so a total throttle-out reports DEGRADED rather than failing.
    That is the documented expected case, and returning [] under it is exactly
    the behaviour this task specifies.
    """
    papers = search_semantic_scholar(
        "retrieval augmented generation", year_min=2019, max_results=20
    )
    if not papers:
        print("T-214 live DEGRADED (throttled keyless - expected; see T-215)")
        return
    for p in papers:
        assert p.source == "semantic_scholar"
        assert p.title
        if p.doi:
            assert p.doi == normalise_doi(p.doi), p.doi
            assert not p.doi.startswith("http")
    with_abs = [p for p in papers if p.abstract and len(p.abstract) > 40]
    assert len(papers) >= 5, f"got {len(papers)}"
    assert len(with_abs) >= 5, f"only {len(with_abs)} populated abstracts"
    print(f"T-214 live OK ({len(papers)} papers, {len(with_abs)} with abstract)")


def test_t213_first_stage_survives_a_large_pool() -> None:
    """T-213(2) regression: pool size must not change what gets ranked.

    ``HybridRetriever`` is configured with dense_k/sparse_k = 30 in production.
    The T-212 harness ranks a pool of up to ~2000 pooled papers, so a fixed
    top-60 first stage returns a *global* shortlist; intersecting that with one
    sub-question's own candidates discards more of them the bigger the pool
    gets. Measured 2026-08-26: raising max_per_source 25 -> 100 nearly doubled
    union recall (0.371 -> 0.714) while the Recall@60 gate *fell*
    (0.057 -> 0.029) — an artefact of this narrowing, not of retrieval.

    Fails if the first stage is ever narrowed back below the pool size.
    """
    from researchgpt.core.config import load_config
    from researchgpt.eval import retrieval_eval as ev

    cfg = load_config("configs/default.yaml")
    n_pool, n_per_query = 220, 45
    assert n_per_query > cfg.retrieval.dense_k, "pool must exceed the production first stage"

    pool = {
        f"p{i}": Paper(
            paper_id=f"p{i}",
            doi=f"10.1234/p{i}",
            title=f"Paper {i} on retrieval augmented generation and agents",
            abstract=f"Study number {i} of hybrid retrieval, reranking and citation grounding.",
            source="openalex",
        )
        for i in range(n_pool)
    }
    queries = ["hybrid retrieval reranking", "citation grounding agents"]
    # Scatter each sub-question's candidates across the whole pool. If they sit
    # in a contiguous block at the front, the unranked tail (which walks the
    # pool in insertion order) supplies them by accident and the test passes
    # even when the first stage dropped everything — verified 2026-08-26.
    per_query = {
        queries[0]: [f"p{i}" for i in range(0, n_pool, 5)][:n_per_query],
        queries[1]: [f"p{i}" for i in range(2, n_pool, 5)][:n_per_query],
    }
    expected = {k for keys in per_query.values() for k in keys}

    original = ev.QUERIES
    ev.QUERIES = queries
    try:
        ordered = ev.rank_corpus(per_query, pool, cfg)
    finally:
        ev.QUERIES = original

    assert len(ordered) == n_pool, "every pooled paper must still appear"
    assert len(set(ordered)) == n_pool, "ranking must not duplicate"
    head = set(ordered[: len(expected)])
    missing = expected - head
    assert not missing, (
        f"{len(missing)} of {len(expected)} live candidates were dropped by the "
        f"first stage before the reranker saw them — the pool-size confound is back"
    )
    print(f"T-213 first-stage OK ({len(expected)} candidates ranked from a {n_pool} pool)")


if __name__ == "__main__":
    test_helpers()
    test_t205_chunker()
    test_t201_openalex()
    test_t202_arxiv()
    test_t203_dedup()
    test_t204_pdf()
    test_t208_bm25()
    test_t209_rrf()
    # Heavy model loads last
    test_t207_vectorstore()
    test_t206_embeddings()
    test_t210_reranker()
    test_t211_venue_tier()
    test_t214_maps_s2_result_to_paper()
    test_t214_request_shape_and_api_key_header()
    test_t214_sustained_429_returns_empty_list()
    test_t214_recovers_when_429_then_200()
    test_t214_live()
    test_t213_first_stage_survives_a_large_pool()
    print("ALL PHASE-2 ACCEPTANCE CHECKS PASSED")


def test_arxiv_throttling_degrades_instead_of_raising() -> None:
    """arXiv was the only source without backoff, and it showed.

    🔴 2026-08-28: test_t203_dedup and test_t204_pdf both died on
    httpx.HTTPStatusError while OpenAlex sat at 83% of its daily budget - the
    wrong host got the blame. arXiv asks for <= 1 request / 3 s and throttles
    bursts; a bare raise_for_status() turned that into a hard failure.

    arXiv is a SECONDARY source (OpenAlex is mandatory under TASKLIST §0.2), so
    a throttle must cost coverage, never the run.
    """
    from unittest.mock import MagicMock, patch

    from researchgpt.tools.search_sources import search_arxiv

    throttled = MagicMock()
    throttled.status_code = 403

    with patch("httpx.Client") as ClientCls:
        ClientCls.return_value.__enter__.return_value.get.return_value = throttled
        with patch("time.sleep"):            # do not actually wait
            papers = search_arxiv("anything", max_results=5)

    assert papers == [], "a throttled arXiv must return empty, not raise"
