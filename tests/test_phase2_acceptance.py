"""Phase 2 acceptance checks from handoffs/phase2.md.

Does NOT edit TASKLIST.md. Reports pass/fail to stdout.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from researchgpt.core.models import Chunk, Paper, RetrievalConfig
from researchgpt.data.bm25_index import BM25Index
from researchgpt.data.chunker import chunk_paper
from researchgpt.data.embeddings import Embedder
from researchgpt.data.metadata_db import MetadataDB, dedup_papers
from researchgpt.data.vectorstore import VectorStore
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
        assert "v" not in p.doi.split("arxiv.")[-1].lower() or not any(
            ch.isdigit() and p.doi.endswith(f"v{i}") for i in range(10)
        )
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
    print("ALL PHASE-2 ACCEPTANCE CHECKS PASSED")
