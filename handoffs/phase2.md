# Cursor (Groq) handoffs — Phase 2 (Retrieval)

Paste each block into Cursor **as its own prompt**, one at a time, in order.
Attach the files named under CONTEXT.

`core/models.py` is done and **must not be edited**. Every module here imports
its shapes from it.

> **Rule 8 reminder:** Cursor must not edit `TASKLIST.md`, `configs/`, or
> anything under `handoffs/`. Report what you finished; Claude Code ticks boxes.

**Order:** T-201 → T-202 → **T-214** → T-203 → T-204 → T-205 → T-206 → T-207 →
T-208 → T-209 → T-210 → T-211.

T-214 (Semantic Scholar) comes before T-203 because its `externalIds` are the
richest dedup signal and T-203 should be written knowing they exist. T-209
needs T-207 and T-208; everything else is linear.

---

## Verified API facts — pin these, they were measured on 2026-08-25

Do not let the model guess any of the following. Each one was confirmed against
the live API, and each is a trap that produces silently wrong data:

1. **OpenAlex has no `abstract` field.** It returns `abstract_inverted_index`,
   a `{word: [positions]}` map that must be de-inverted. Reconstruction:
   `" ".join(w for _, w in sorted((p, w) for w, ps in idx.items() for p in ps))`
2. **OpenAlex `doi` is a full URL** — `https://doi.org/10.1016/...`. Normalise
   to bare lowercase before using it as a key.
3. **arXiv requires HTTPS.** `http://export.arxiv.org/api/query` returns
   **HTTP 301** and an empty body. Use `https://` with `follow_redirects=True`.
4. **arXiv entries usually have no `<arxiv:doi>`.** Do not rely on it for
   dedup. OpenAlex indexes preprints under a synthetic DOI
   `10.48550/arxiv.<id>`, so that is the join key.
5. **arXiv ids carry a version suffix** (`2506.21931v2`). Strip `v\d+` before
   forming the dedup key: `2506.21931v2` → `10.48550/arxiv.2506.21931`.
6. **OpenAlex filter syntax that works** (`SESSION_CONTEXT.md §9` — plain
   `search=` returns irrelevant high-citation medical papers):
   `filter=title_and_abstract.search:<q>,from_publication_date:YYYY-MM-DD,to_publication_date:YYYY-MM-DD`
7. **Always send `mailto=`** to OpenAlex (polite pool, avoids throttling).

---

## T-201 — OpenAlex connector

```
FILE: src/researchgpt/tools/search_sources.py
CONTEXT (attach): src/researchgpt/core/models.py

WRITE: The OpenAlex connector. Returns validated Paper objects. Read the
"Verified API facts" section of handoffs/phase2.md and follow items 1, 2, 6
and 7 exactly - they are measured behaviour, not guesses.

SIGNATURES (exact):
    def deinvert_abstract(index: dict[str, list[int]] | None) -> str | None
    def normalise_doi(doi: str | None) -> str | None
    def search_openalex(query: str, *, year_min: int | None = None,
                        max_results: int = 25,
                        mailto: str = "sreekaran005@gmail.com") -> list[Paper]

MAPPING (OpenAlex work -> Paper):
    paper_id       = work["id"].rsplit("/", 1)[-1]        # e.g. "W4406542750"
    doi            = normalise_doi(work.get("doi"))
    title          = work.get("title") or work.get("display_name")
    authors        = [a["author"]["display_name"] for a in work["authorships"]]
    year           = work.get("publication_year")
    venue          = work["primary_location"]["source"]["display_name"]  # guard None
    abstract       = deinvert_abstract(work.get("abstract_inverted_index"))
    url            = work.get("open_access", {}).get("oa_url")
    source         = "openalex"
    citation_count = work.get("cited_by_count")
    is_preprint    = work.get("type") == "preprint"

CONSTRAINTS:
  - Python 3.11+, type-hinted. Dependency: httpx only.
  - primary_location and its nested source can both be null. Guard every
    nesting level; an unresolvable venue is None, never "" and never invented
    (SPEC §14.2).
  - Paginate with per-page (max 200) until max_results is reached.
  - Skip works where title is falsy.

DONE WHEN: search_openalex("agentic retrieval augmented generation",
year_min=2023, max_results=20) returns >= 20 Papers, each with a non-null
title, a normalised bare-lowercase doi, and a de-inverted abstract of
non-trivial length.

DO NOT: add other providers to this function, cache, or change signatures.
```

---

## T-202 — arXiv connector

```
FILE: src/researchgpt/tools/search_sources.py   (add to the existing file)
CONTEXT (attach): src/researchgpt/core/models.py

WRITE: The arXiv Atom connector, alongside the OpenAlex one. Follow "Verified
API facts" items 3, 4 and 5 exactly - HTTPS is mandatory and the dedup key is
synthetic.

SIGNATURES (exact):
    def arxiv_id_to_doi(arxiv_id: str) -> str
        # "2506.21931v2" -> "10.48550/arxiv.2506.21931"  (strip version)
    def search_arxiv(query: str, *, max_results: int = 25) -> list[Paper]

ENDPOINT:
    GET https://export.arxiv.org/api/query
        search_query=all:"<query>"   start=0   max_results=<n>
    httpx.get(..., follow_redirects=True)     # http:// 301s to nothing

PARSE (xml.etree.ElementTree), namespaces:
    atom  = http://www.w3.org/2005/Atom
    arxiv = http://arxiv.org/schemas/atom

MAPPING (entry -> Paper):
    paper_id = arxiv id with version, e.g. "2506.21931v2"
    doi      = arxiv_id_to_doi(paper_id)     # synthetic; enables T-203 dedup
    title    = " ".join(title.text.split())  # arXiv wraps titles across lines
    authors  = [author/name ...]
    year     = int(published[:4])
    venue    = "arXiv"
    abstract = summary.text.strip()
    url      = the <link title="pdf"> href
    source   = "arxiv"
    is_preprint = True
    venue_tier  = "preprint"

CONSTRAINTS:
  - Python 3.11+, type-hinted. Stdlib xml.etree + httpx only.
  - arXiv asks for <=1 request every 3 seconds. Sleep between pages.
  - A missing <arxiv:doi> is normal, not an error.

DONE WHEN: search_arxiv("agentic retrieval augmented generation",
max_results=10) returns 10 Papers with single-line titles, a synthetic
10.48550/arxiv.* doi with no version suffix, and a working pdf URL.

DO NOT: change the OpenAlex function, or change signatures.
```

---

## T-203 — dedup + metadata DB

```
FILE: src/researchgpt/data/metadata_db.py
CONTEXT (attach): src/researchgpt/core/models.py,
                  src/researchgpt/tools/search_sources.py

WRITE: DOI-based deduplication plus a SQLite metadata store.

SIGNATURES (exact):
    def dedup_papers(papers: list[Paper]) -> list[Paper]
    class MetadataDB:
        def __init__(self, path: str = "data/metadata.db") -> None
        def upsert_papers(self, papers: list[Paper]) -> int   # rows written
        def get(self, paper_id: str) -> Paper | None
        def get_by_doi(self, doi: str) -> Paper | None
        def all(self) -> list[Paper]
        def set_text_availability(self, paper_id: str, value: str) -> None
        def set_pdf_path(self, paper_id: str, path: str) -> None
        def count(self) -> int

DEDUP RULES (in this order):
  1. Key on normalised doi when present.
  2. On collision, PREFER the record with the richer metadata: non-null
     abstract wins, then higher citation_count, then source == "openalex"
     (it carries venue and OA metadata that arXiv does not).
  3. Merge rather than discard: fill null fields on the winner from the loser.
     An arXiv record often has a pdf url that the OpenAlex record lacks.
  4. Papers with no doi fall back to a normalised-title key
     (lowercase, strip non-alphanumerics, collapse whitespace).

CONSTRAINTS:
  - Python 3.11+, type-hinted. Stdlib sqlite3 only.
  - One table `papers`; store list fields (authors) as JSON text.
  - upsert on paper_id; never raise on a duplicate.
  - CREATE TABLE IF NOT EXISTS on init; safe to construct repeatedly.

DONE WHEN: feeding the same paper from both connectors (an arXiv preprint and
its OpenAlex record, which share the synthetic 10.48550/arxiv.* doi) yields
exactly ONE Paper, and that survivor has BOTH the OpenAlex venue/citation
data AND the arXiv pdf url.

DO NOT: add an ORM, add Postgres, or change signatures.
```

---

## T-204 — PDF fetch and parse

```
FILE: src/researchgpt/tools/pdf_loader.py
CONTEXT (attach): src/researchgpt/core/models.py

WRITE: Open-access PDF fetching and PyMuPDF text extraction with heuristic
section detection. Sets text_availability, which T-505 depends on to enforce
the abstract-only rule.

SIGNATURES (exact):
    def fetch_pdf(paper: Paper, dest_dir: str = "data/pdfs") -> str | None
    def parse_pdf(path: str) -> tuple[str, list[tuple[str, int, int]]]
        # returns (full_text, [(section_name, start_char, end_char), ...])
    def load_paper_text(paper: Paper,
                        dest_dir: str = "data/pdfs") -> tuple[str, str]
        # returns (text, text_availability) where availability is
        # "full" | "abstract_only" | "none"

BEHAVIOUR:
  - fetch_pdf: only if paper.url looks like a PDF or the host is a known OA
    host (arxiv.org). Save as <dest_dir>/<paper_id>.pdf. Return None on any
    non-200, wrong content-type, or timeout - a paywalled paper is an
    expected outcome, NOT an error.
  - load_paper_text: try the PDF; on failure fall back to paper.abstract and
    return "abstract_only"; if there is no abstract either, return ("", "none").
  - Section detection: regex for common headings at line start, case-insensitive
    (abstract, introduction, related work, background, method(s|ology),
    approach, experiment(s), evaluation, result(s), discussion, conclusion,
    limitations, references). Record char offsets into full_text.
  - Truncate everything from the "references" heading onward out of full_text -
    reference lists are pure noise for chunking and embed badly.

CONSTRAINTS:
  - Python 3.11+, type-hinted. Dependencies: pymupdf (import fitz), httpx.
  - Never raise on a malformed PDF; log and return None / "none".
  - Respect a 60s timeout and set a descriptive User-Agent.

DONE WHEN: 10 arXiv OA PDFs download and parse with non-empty text and at
least one detected section each; a paywalled DOI degrades to "abstract_only"
without raising; and a deliberately corrupted PDF returns "none".

DO NOT: add GROBID, add OCR, or change signatures.
```

---

## T-205 ★ — chunker

```
FILE: src/researchgpt/data/chunker.py
CONTEXT (attach): src/researchgpt/core/models.py

WRITE: Section-aware chunking that preserves exact character offsets. The
offsets are what make claim-to-span grounding possible, so they are the
correctness requirement of this file, not a detail.

SIGNATURES (exact):
    def chunk_paper(paper_id: str, text: str,
                    sections: list[tuple[str, int, int]] | None = None,
                    chunk_size: int = 1200,
                    chunk_overlap: int = 200) -> list[Chunk]

ALGORITHM:
  1. If sections are given, split on section boundaries FIRST; otherwise treat
     the whole text as one section.
  2. Within each section, recursive character split at chunk_size with
     chunk_overlap, preferring to break on "\n\n", then "\n", then ". ",
     then " ".
  3. Every Chunk carries the section name and start_char/end_char that index
     into the ORIGINAL `text` argument - not into the section substring.
  4. chunk_id = f"{paper_id}::{ordinal:04d}".
  5. NEVER merge text across papers.

CONSTRAINTS:
  - Python 3.11+, type-hinted. Stdlib only.
  - Drop chunks whose stripped text is < 50 characters.
  - Chunk is imported from core.models and validates end_char >= start_char.

DONE WHEN (this is the acceptance test, write it):
    for c in chunk_paper("p1", text, sections):
        assert text[c.start_char:c.end_char] == c.text
Every chunk's offsets must slice the original text back out EXACTLY. If that
assertion fails anywhere, the file is not done.

DO NOT: use langchain splitters, normalise whitespace inside chunks (it breaks
offsets), or change signatures.
```

---

## T-206 — embeddings

```
FILE: src/researchgpt/data/embeddings.py
CONTEXT (attach): src/researchgpt/core/models.py

WRITE: A CPU sentence-transformers wrapper for BAAI/bge-small-en-v1.5.

SIGNATURES (exact):
    class Embedder:
        def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5",
                     device: str = "cpu", batch_size: int = 32) -> None
        def encode(self, texts: list[str],
                   show_progress: bool = False) -> list[list[float]]
        def encode_query(self, text: str) -> list[float]
        @property
        def dim(self) -> int

CONSTRAINTS:
  - Python 3.11+, type-hinted. Dependency: sentence-transformers.
  - Load the model ONCE in __init__, never per call.
  - normalize_embeddings=True (Chroma uses cosine).
  - BGE models want a query prefix for retrieval: encode_query must prepend
    "Represent this sentence for searching relevant passages: ". Documents get
    NO prefix. Getting this backwards silently degrades retrieval quality.

DONE WHEN: encoding 3,000 chunks completes on this machine and the wall time
is printed; dim == 384; and encode_query returns a 384-vector.

DO NOT: add GPU logic, add a second model, or change signatures.
```

---

## T-207 — Chroma vector store

```
FILE: src/researchgpt/data/vectorstore.py
CONTEXT (attach): src/researchgpt/core/models.py

WRITE: A persistent Chroma collection over Chunk objects.

SIGNATURES (exact):
    class VectorStore:
        def __init__(self, path: str = "data/vectorstore",
                     collection: str = "chunks") -> None
        def add(self, chunks: list[Chunk],
                embeddings: list[list[float]]) -> None
        def query(self, embedding: list[float],
                  k: int = 30) -> list[tuple[str, float]]   # (chunk_id, score)
        def get_chunk(self, chunk_id: str) -> Chunk | None
        def count(self) -> int
        def reset(self) -> None

CONSTRAINTS:
  - Python 3.11+, type-hinted. Dependency: chromadb (PersistentClient).
  - Store paper_id, section, start_char, end_char and text in metadata so a
    Chunk can be fully reconstructed by get_chunk without another store.
  - cosine space (hnsw:space="cosine").
  - add() must upsert, so re-running ingestion does not duplicate.
  - Return SIMILARITY (higher = better). Chroma returns cosine DISTANCE, so
    convert: similarity = 1 - distance. Getting this inverted ranks the worst
    chunks first and looks like a broken retriever.

DONE WHEN: adding 100 chunks then querying returns 30 results ordered by
DESCENDING similarity, and get_chunk round-trips a Chunk with intact offsets.

DO NOT: add Qdrant, add pgvector, or change signatures.
```

---

## T-208 — BM25 index

```
FILE: src/researchgpt/data/bm25_index.py
CONTEXT (attach): src/researchgpt/core/models.py

WRITE: A BM25 sparse index over the same chunks, persistable to disk.

SIGNATURES (exact):
    class BM25Index:
        def __init__(self) -> None
        def build(self, chunks: list[Chunk]) -> None
        def query(self, text: str, k: int = 30) -> list[tuple[str, float]]
        def save(self, path: str = "data/bm25.pkl") -> None
        @classmethod
        def load(cls, path: str = "data/bm25.pkl") -> "BM25Index"

CONSTRAINTS:
  - Python 3.11+, type-hinted. Dependency: rank-bm25 (BM25Okapi).
  - Tokenise by lowercasing and splitting on non-alphanumerics. Keep it
    simple and identical between build() and query() - a mismatch between the
    two tokenisers is the classic silent BM25 bug.
  - Keep the chunk_id order alongside the corpus so scores map back correctly.
  - query() returns the top-k by descending score.

DONE WHEN: build over 100 chunks then query returns 30 (chunk_id, score) pairs
in descending order, and a save/load round-trip returns identical results.

DO NOT: add stemming, add stopword lists, or change signatures.
```

---

## T-209 — hybrid retriever (RRF)

```
FILE: src/researchgpt/tools/hybrid_retriever.py
CONTEXT (attach): src/researchgpt/core/models.py,
                  src/researchgpt/data/vectorstore.py,
                  src/researchgpt/data/bm25_index.py,
                  src/researchgpt/data/embeddings.py

WRITE: Reciprocal Rank Fusion over the dense and sparse rankings.

SIGNATURES (exact):
    def rrf_fuse(rankings: list[list[str]],
                 rrf_k: int = 60) -> list[tuple[str, float]]
    class HybridRetriever:
        def __init__(self, store: VectorStore, bm25: BM25Index,
                     embedder: Embedder, cfg: RetrievalConfig) -> None
        def retrieve(self, query: str) -> list[tuple[Chunk, float]]

RRF (SPEC §11): score(d) = sum over rankings of 1 / (rrf_k + rank(d)),
with rank 1-based. Documents absent from a ranking contribute nothing.

BEHAVIOUR:
  - retrieve(): dense top cfg.dense_k + sparse top cfg.sparse_k, fuse, return
    fused order. Do NOT rerank here - that is T-210's job.
  - Reconstruct Chunks via store.get_chunk.

CONSTRAINTS:
  - Python 3.11+, type-hinted. No new dependencies.
  - rrf_fuse must be a PURE function of the ranking lists - no scores in, so
    it is unaffected by the fact that BM25 and cosine are not comparable
    scales. That is the entire point of RRF; do not "improve" it by blending
    raw scores.

DONE WHEN: the fused ranking differs from both input rankings, is identical
across repeated runs on the same inputs, and rrf_fuse([["a","b"],["b","a"]])
ranks "b" and "a" by their summed reciprocal ranks.

DO NOT: add score normalisation, add weights, or change signatures.
```

---

## T-210 — cross-encoder reranker

```
FILE: src/researchgpt/tools/reranker.py
CONTEXT (attach): src/researchgpt/core/models.py

WRITE: A CPU cross-encoder reranker over the fused candidates. Its weights are
replaced later by the Phase 3C fine-tune, so the model path must be a
constructor argument, never a hardcoded constant.

SIGNATURES (exact):
    class Reranker:
        def __init__(self,
                     model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
                     device: str = "cpu", batch_size: int = 16) -> None
        def rerank(self, query: str, chunks: list[Chunk],
                   top_k: int = 12) -> list[tuple[Chunk, float]]
        @property
        def last_latency_ms(self) -> int

CONSTRAINTS:
  - Python 3.11+, type-hinted. Dependency: sentence-transformers (CrossEncoder).
  - Load the model ONCE in __init__.
  - rerank() scores every (query, chunk.text) pair, sorts descending, returns
    top_k.
  - Record wall-clock ms per rerank() call in last_latency_ms. TASKLIST T-210
    requires this measurement, and T-334 compares stock vs fine-tuned latency
    against it.
  - Empty chunks list returns [] without loading anything.

DONE WHEN: reranking 60 candidates returns 12 in descending score order,
top-12 is sensible on 3 hand-checked queries, and last_latency_ms is non-zero
and reported.

DO NOT: hardcode the model name, add GPU logic, or change signatures.
```

---

## T-211 — venue tiering

```
FILE: src/researchgpt/tools/search_sources.py   (add to the existing file)
CONTEXT (attach): src/researchgpt/core/models.py

WRITE: Infer VenueTier from OpenAlex metadata, and set it on Papers returned
by search_openalex.

SIGNATURES (exact):
    def infer_venue_tier(work: dict) -> str    # a VenueTier literal

RULES (first match wins):
    type == "preprint" or host is arXiv                  -> "preprint"
    venue name contains "IEEE"                           -> "ieee"
    venue name contains "ACL"/"EMNLP"/"NAACL"/"COLING"   -> "acl"
    source.is_in_doaj or is_core or has an ISSN          -> "peer_reviewed"
    otherwise                                            -> "unknown"

CONSTRAINTS:
  - Python 3.11+, type-hinted. No new dependencies.
  - Guard every nesting level; primary_location and source can be null.
  - Return "unknown" rather than raising on anything unexpected.
  - Do NOT attempt to infer "scopus" or "scopus_q1" - OpenAlex does not carry
    Scopus quartiles and inventing one would be fabricated metadata (SPEC
    §14.2). Those two tiers stay unused unless set manually.

DONE WHEN: a mixed result set of 20 papers assigns at least three distinct
tiers, arXiv results are all "preprint", and no call raises.

DO NOT: add an external ranking API, or change signatures.
```

---

## After Cursor finishes

Claude Code runs the acceptance checks and reviews the diffs. The two that
matter most:

1. **T-205 offset assertion.** `text[c.start_char:c.end_char] == c.text` for
   every chunk. If this is wrong, every evidence span in the final review
   points at the wrong text, and it will not be obvious until the verifier is
   producing nonsense in Phase 5.
2. **T-207 distance-vs-similarity conversion.** Chroma returns cosine
   *distance*. If it is not converted, the retriever ranks the worst chunks
   first and every downstream number is quietly wrong.

Then T-212 (Claude Code) runs the recall gate against
`eval/gold_sets/own_bibliography.json` — 35 DOIs, already built and verified.
**Gate: Recall@20 >= 0.80.**

---

## T-214 — Semantic Scholar connector (added 2026-08-25)

```
FILE: src/researchgpt/tools/search_sources.py   (add to the existing file)
CONTEXT (attach): src/researchgpt/core/models.py

WRITE: The Semantic Scholar connector, alongside OpenAlex and arXiv. It is a
SUPPLEMENTARY source and must be degradable: the pipeline runs fine without it.

SIGNATURES (exact):
    def search_semantic_scholar(query: str, *, year_min: int | None = None,
                                max_results: int = 25,
                                api_key: str | None = None) -> list[Paper]

ENDPOINT:
    GET https://api.semanticscholar.org/graph/v1/paper/search
    params: query, limit (max 100), offset, year=f"{year_min}-" when given,
            fields="paperId,externalIds,title,abstract,year,venue,authors,
                    citationCount,isOpenAccess,openAccessPdf,publicationTypes"
    header: "x-api-key": api_key   ONLY when api_key is not None
            (read S2_API_KEY from the environment; absent is normal)

MAPPING (result -> Paper):
    paper_id       = result["paperId"]
    doi            = normalise_doi(externalIds.get("DOI"))     # reuse T-201's
    title          = result["title"]
    authors        = [a["name"] for a in result.get("authors") or []]
    year           = result.get("year")
    venue          = result.get("venue") or None
    abstract       = result.get("abstract")     # already plain text
    url            = (openAccessPdf or {}).get("url")
    source         = "semantic_scholar"
    citation_count = result.get("citationCount")
    is_preprint    = "JournalArticle" not in (publicationTypes or [])

*** DEGRADABILITY — this is the point of the task ***
  - Retry 429 with exponential backoff (2, 4, 8, 16, 30s), max 6 attempts.
  - After the final failed attempt, LOG A WARNING AND RETURN [] .
    Do NOT raise. Do NOT abort the run. A run that dies because a
    supplementary source was throttled is a defect.
  - Measured keyless behaviour 2026-08-25: 1 of 4 rapid requests succeeded;
    with backoff, 2 of 3 queries succeeded and one failed after 6 attempts.
    Unreliable-without-a-key is the EXPECTED case, not an error condition.
  - Be polite: sleep >= 1s between successful requests even when they work.

CONSTRAINTS:
  - Python 3.11+, type-hinted. Dependency: httpx.
  - Reuse normalise_doi from T-201; do not write a second one.
  - Abstracts come back as plain text - no inverted index here, unlike OpenAlex.

DONE WHEN: a query returns >= 5 Papers with populated abstracts and normalised
DOIs; and a simulated sustained-429 condition returns [] with a logged warning
and no exception.

DO NOT: make this a hard dependency, raise on 429, or change signatures.
```

> **Integration note for T-203:** Semantic Scholar's `externalIds` carries DOI,
> ArXiv, DBLP and PubMed ids at once. That makes it the best source of
> cross-identifiers for dedup — an S2 record can bridge an arXiv preprint to
> its published DOI, which neither of the other two connectors can do alone.
