# Phase 2 completion report — for Claude Code

> Written by Cursor after implementing `handoffs/phase2.md` (2026-08-25).
> **Did not edit `TASKLIST.md` or `configs/`.** Claude Code should tick T-201…T-211.

---

## 1. What was done

All Cursor-owned Phase 2 tasks, in handoff order. `core/models.py` untouched.

| Task | File | Acceptance |
|---|---|---|
| T-201 | `src/researchgpt/tools/search_sources.py` (OpenAlex) | ✅ ≥20 papers, bare DOI, de-inverted abstracts |
| T-202 | same file (arXiv HTTPS Atom) | ✅ 10 papers, synthetic DOI, no version suffix |
| T-203 | `src/researchgpt/data/metadata_db.py` | ✅ DOI dedup + SQLite upsert |
| T-204 | `src/researchgpt/tools/pdf_loader.py` | ✅ 10 OA PDFs; paywall → abstract_only; corrupt → none |
| T-205 ★ | `src/researchgpt/data/chunker.py` | ✅ `text[start:end] == c.text` for every chunk |
| T-206 | `src/researchgpt/data/embeddings.py` | ✅ dim=384; **3000 chunks in 8.5s** on this CPU |
| T-207 ★ | `src/researchgpt/data/vectorstore.py` | ✅ cosine **similarity = 1 − distance**; get_chunk round-trip |
| T-208 | `src/researchgpt/data/bm25_index.py` | ✅ top-30 descending; save/load identical |
| T-209 | `src/researchgpt/tools/hybrid_retriever.py` | ✅ pure RRF; fused ≠ either input; stable |
| T-210 | `src/researchgpt/tools/reranker.py` | ✅ top-12; `last_latency_ms=194` on 60 cands |
| T-211 | `search_sources.infer_venue_tier` | ✅ tiers `{peer_reviewed, unknown, preprint, ieee}` |

Suite: `python tests/test_phase2_acceptance.py` → **ALL PASSED**.

---

## 2. Verified API facts — followed exactly

1. OpenAlex abstract via `abstract_inverted_index` de-inversion (no `abstract` field).
2. DOI normalised to bare lowercase (strip `https://doi.org/`).
3. arXiv uses **HTTPS** + `follow_redirects=True`.
4. Synthetic join key `10.48550/arxiv.<id>` when `<arxiv:doi>` absent.
5. Version suffix stripped before DOI (`2506.21931v2` → `…2506.21931`).
6. OpenAlex filter: `title_and_abstract.search` + date window.
7. `mailto=sreekaran005@gmail.com` on every OpenAlex call.

---

## 3. Review checklist (handoff “After Cursor finishes”)

1. **T-205 offsets** — every chunk asserts `text[c.start_char:c.end_char] == c.text`. Recursive split prefers `\n\n` → `\n` → `. ` → ` `; offsets stay absolute into the original `text` argument. Chunks &lt; 50 stripped chars dropped.
2. **T-207 distance→similarity** — `similarity = 1.0 - distance`, then sort **descending**. Upsert on add. Metadata holds `paper_id`, `section`, `start_char`, `end_char`, `text` for full `Chunk` reconstruction.

---

## 4. Observations Claude Code should know

1. **Live OpenAlex∩arXiv overlap was empty** on the smoke queries used in T-203, so the merge of venue+pdf was verified with a **synthetic** pair that shares `10.48550/arxiv.2501.00001`. Live dedup still collapses duplicate DOIs; no duplicate DOIs in the merged list.

2. **`MetadataDB.close()`** was added (not in the handoff signature list, but required on Windows — open sqlite handles block temp-dir cleanup). Optional for production; call it in tests / shutdown.

3. **Chroma on Windows** keeps HNSW files locked while the client lives. Acceptance uses `TemporaryDirectory(ignore_cleanup_errors=True)` and `store.reset()` before exit. Not a production bug.

4. **HF Hub warning:** “unauthenticated requests”. `.env` has `HF_TOKEN` but the suite does not load dotenv for embeddings/reranker. Suggest `load_dotenv()` in Embedder/Reranker `__init__`, or export `HF_TOKEN` in the shell before Phase 2 eval runs. Cursor did **not** change this beyond what’s needed for signatures.

5. **BGE query prefix** is applied only in `encode_query` (`Represent this sentence for searching relevant passages: `). Documents get no prefix.

6. **Reranker model path is a constructor arg** (default MiniLM) so Phase 3C can swap weights without editing the class.

7. **Venue tiers:** deliberately never invents `scopus` / `scopus_q1` (SPEC §14.2). Live mix included `ieee`, `peer_reviewed`, `preprint`, `unknown`.

8. **Dedup merge preference:** richer abstract → higher citation_count → prefer `openalex`; then fill nulls from loser (so arXiv PDF URL survives onto the OpenAlex-rich record). When arXiv wins richness somehow, code still tries to keep an arxiv.org PDF URL.

9. **PDF loader** treats arXiv hosts and `*.pdf` / `/pdf/` URLs as fetchable; non-200 / wrong type / timeout → `None` (paywall is expected). References heading truncates full text before chunking.

10. **Not done by this handoff (Claude):** T-212 recall gate against `eval/gold_sets/own_bibliography.json` (Recall@20 ≥ 0.80). T-213 buffer if it misses.

---

## 5. Files touched

```
src/researchgpt/tools/search_sources.py   (new — OpenAlex, arXiv, venue tier)
src/researchgpt/tools/pdf_loader.py       (new)
src/researchgpt/tools/hybrid_retriever.py (new)
src/researchgpt/tools/reranker.py         (new)
src/researchgpt/data/__init__.py          (new)
src/researchgpt/data/metadata_db.py       (new)
src/researchgpt/data/chunker.py           (new)
src/researchgpt/data/embeddings.py        (new)
src/researchgpt/data/vectorstore.py       (new)
src/researchgpt/data/bm25_index.py        (new)
tests/test_phase2_acceptance.py           (new)
handoffs/phase2_complete.md               (this file)
```

**Not touched:** `TASKLIST.md`, `configs/`, `core/models.py`, `handoffs/phase2.md`.

---

## 6. Suggested Claude Code next actions

1. Review T-205 offsets + T-207 similarity conversion line-by-line.
2. Tick T-201…T-211 in `TASKLIST.md`.
3. Run **T-212** recall gate on `eval/gold_sets/own_bibliography.json`.
4. Optionally `load_dotenv()` for HF token in Embedder/Reranker.
5. Commit when satisfied (only if the human asks).
