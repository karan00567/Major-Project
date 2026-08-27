"""Core Pydantic data models.

Source of truth: RESEARCHGPT_SPEC.md §8. Every other module imports its shapes
from here; nothing in this file may import from the rest of the package, so it
stays dependency-free and safe to import anywhere.

Deviations from SPEC §8, all deliberate and recorded in TASKLIST.md:

* ``Paper.text_availability`` is new. TASKLIST T-204 sets it and T-505 enforces
  the abstract-only rule that depends on it (abstract-only papers may be cited
  as existing but may not supply verified claims).
* ``ALLOWED_MODELS`` lives here rather than in ``core/llm.py`` as TASKLIST §0.1
  originally said. Reason: this module has no dependencies, so ``core/config.py``
  can validate model names at config-load time instead of failing at the first
  API call. ``core/llm.py`` still owns *enforcement* — it imports and checks this
  constant before constructing any request.
* ``RunConfig`` and its nested models are new. SPEC §10.1 specifies the YAML but
  never types it, and SPEC's version predates the $0 constraint.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# --------------------------------------------------------------------------
# Enumerations (SPEC §8)
# --------------------------------------------------------------------------

VenueTier = Literal[
    "scopus_q1", "scopus", "ieee", "acl", "peer_reviewed", "preprint", "unknown"
]
Verdict = Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED", "CONTRADICTED"]
Decision = Literal["WRITE", "RETRIEVE", "REPLAN"]
TextAvailability = Literal["full", "abstract_only", "none"]

#: TASKLIST §0.1 — the $0 hard rule. Only free, open-weight models.
#: Verified live 2026-08-25. ``core/llm.py`` raises on anything not in here.
ALLOWED_MODELS: frozenset[str] = frozenset(
    {
        # Google AI Studio — open-weight Gemma, free tier
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
        # Groq — open-weight, free tier
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.6-27b",
    }
)

#: Literature sources that actually have a connector in ``tools/search_sources.py``.
#: ``SourcesConfig`` validates against this so a config can never name a source
#: that does not exist — the failure mode that hid T-214 for a day, when
#: ``configs/default.yaml`` listed ``semantic_scholar`` and nothing implemented it.
IMPLEMENTED_SOURCES: frozenset[str] = frozenset(
    {"openalex", "arxiv", "semantic_scholar"}
)

#: Provider inferred from model name; used by ``core/llm.py`` to pick a client.
MODEL_PROVIDER: dict[str, str] = {
    "gemma-4-31b-it": "google",
    "gemma-4-26b-a4b-it": "google",
    "openai/gpt-oss-120b": "groq",
    "openai/gpt-oss-20b": "groq",
    "qwen/qwen3.6-27b": "groq",
}


# --------------------------------------------------------------------------
# Corpus models (SPEC §8)
# --------------------------------------------------------------------------


class Paper(BaseModel):
    paper_id: str
    doi: Optional[str] = None
    title: str
    authors: list[str] = []
    year: Optional[int] = None
    venue: Optional[str] = None
    venue_tier: VenueTier = "unknown"
    abstract: Optional[str] = None
    url: Optional[str] = None
    pdf_path: Optional[str] = None
    source: str  # openalex | arxiv
    citation_count: Optional[int] = None
    is_preprint: bool = False
    #: Set by the PDF loader (T-204). Gates claim sourcing under T-505.
    text_availability: TextAvailability = "none"


class Chunk(BaseModel):
    chunk_id: str
    paper_id: str
    text: str
    section: Optional[str] = None  # abstract | methods | results | ...
    start_char: int
    end_char: int
    embedding_id: Optional[str] = None

    @field_validator("end_char")
    @classmethod
    def _end_after_start(cls, v: int, info) -> int:
        start = info.data.get("start_char")
        if start is not None and v < start:
            raise ValueError(f"end_char {v} precedes start_char {start}")
        return v


class EvidenceSpan(BaseModel):
    chunk_id: str
    quote: str
    start_char: int
    end_char: int


# --------------------------------------------------------------------------
# Agent output models (SPEC §8)
# --------------------------------------------------------------------------


class PaperInsight(BaseModel):
    """Extractor output. The four graded fields are all Optional by design:
    SPEC §14.2 forbids fabrication, so an unresolvable field is ``None`` plus an
    ``extraction_note``, never an invented string."""

    paper_id: str
    methodology: Optional[str] = None
    advantages: Optional[str] = None
    disadvantages: Optional[str] = None
    critique: Optional[str] = None
    datasets: list[str] = []
    metrics: list[str] = []
    results: Optional[str] = None
    limitations: Optional[str] = None
    cluster: Optional[str] = None  # C1..C6, SPEC §1.6
    evidence_spans: list[EvidenceSpan] = []
    extraction_note: Optional[str] = None


class Claim(BaseModel):
    claim_id: str
    text: str
    paper_ids: list[str]
    verdict: Verdict
    support_score: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceSpan] = []


class SubQuestion(BaseModel):
    sq_id: str
    text: str
    facet: str  # method | application | evaluation | limitation
    covered: bool = False
    supporting_paper_ids: list[str] = []


class SearchTask(BaseModel):
    sq_id: str
    query: str
    sources: list[str]
    year_min: Optional[int] = None
    max_results: int = 25


# --------------------------------------------------------------------------
# Run configuration (types SPEC §10.1, revised for the $0 / CPU constraints)
# --------------------------------------------------------------------------


class LLMConfig(BaseModel):
    """Generative-agent settings. Model names are checked against
    ``ALLOWED_MODELS`` here so a forbidden model fails at config load, not at
    the first billable request."""

    model: str
    planner_model: Optional[str] = None
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = 4096
    requests_per_minute: int = 15
    max_retries: int = 5
    cache_dir: str = "data/llm_cache"

    @field_validator("model", "planner_model")
    @classmethod
    def _allowlisted(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_MODELS:
            raise ValueError(
                f"Model {v!r} is not in ALLOWED_MODELS (TASKLIST §0.1: free, "
                f"open-weight models only). Permitted: {sorted(ALLOWED_MODELS)}"
            )
        return v


class EmbeddingsConfig(BaseModel):
    model: str = "BAAI/bge-small-en-v1.5"
    device: Literal["cpu", "cuda"] = "cpu"
    batch_size: int = 32


class RetrievalConfig(BaseModel):
    dense_k: int = 30
    sparse_k: int = 30
    fusion: Literal["rrf"] = "rrf"
    rrf_k: int = 60
    rerank: bool = True
    reranker: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    final_k: int = 12
    chunk_size: int = 1200
    chunk_overlap: int = 200


class SourcesConfig(BaseModel):
    enabled: list[str] = ["openalex", "arxiv"]
    max_per_source: int = 25

    @field_validator("enabled")
    @classmethod
    def _implemented(cls, v: list[str]) -> list[str]:
        unknown = [s for s in v if s not in IMPLEMENTED_SOURCES]
        if unknown:
            raise ValueError(
                f"sources.enabled names {unknown}, which have no connector in "
                f"tools/search_sources.py. Implemented: {sorted(IMPLEMENTED_SOURCES)}"
            )
        return v


class ReviewConfig(BaseModel):
    min_papers: int = 20
    max_papers: int = 60
    year_min: int = 2019
    max_iterations: int = 3
    grounding_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    coverage_threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class VerifierConfig(BaseModel):
    onnx_path: str = "data/models/verifier-int8.onnx"
    tokenizer: str = "microsoft/deberta-v3-small"
    #: T-503 — biased toward precision. CliVER measured a 21% false-Support
    #: rate, and over-predicting "supported" is the dangerous direction here.
    support_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class OutputConfig(BaseModel):
    citation_style: Literal["ieee"] = "ieee"
    formats: list[str] = ["markdown", "csv", "bibtex"]
    runs_dir: str = "outputs/runs"


class RunConfig(BaseModel):
    llm: LLMConfig
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
    sources: SourcesConfig = SourcesConfig()
    review: ReviewConfig = ReviewConfig()
    verifier: VerifierConfig = VerifierConfig()
    output: OutputConfig = OutputConfig()

    model_config = {"extra": "forbid"}


# --------------------------------------------------------------------------
# Aliases for the names used in TASKLIST T-102's acceptance criterion.
# SPEC §8 naming is canonical; these exist so both vocabularies resolve.
# --------------------------------------------------------------------------

Insight = PaperInsight
CritiqueDecision = Decision

__all__ = [
    "ALLOWED_MODELS",
    "IMPLEMENTED_SOURCES",
    "MODEL_PROVIDER",
    "VenueTier",
    "Verdict",
    "Decision",
    "CritiqueDecision",
    "TextAvailability",
    "Paper",
    "Chunk",
    "EvidenceSpan",
    "PaperInsight",
    "Insight",
    "Claim",
    "SubQuestion",
    "SearchTask",
    "LLMConfig",
    "EmbeddingsConfig",
    "RetrievalConfig",
    "SourcesConfig",
    "ReviewConfig",
    "VerifierConfig",
    "OutputConfig",
    "RunConfig",
]
