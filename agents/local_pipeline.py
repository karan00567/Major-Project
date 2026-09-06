from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from agents import checkpoints, pdf_reader
from agents.ollama_client import OllamaClient, OllamaError

KEEP_RATIO = 5


MIN_KEPT, MAX_KEPT = 5, 40


MAX_PER_SOURCE = 25

MAX_OUTPUT_TOKENS = 1024

CHUNK_CHARS = 6000

MAX_CHUNKS = 6

OUT_DIR = pathlib.Path("agents/out")


@dataclass
class Trace:

    run_id: str
    path: pathlib.Path
    events: list[dict] = field(default_factory=list)

    def emit(self, agent: str, event: str, payload: dict | None = None) -> None:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": self.run_id,
            "agent": agent,
            "event": event,
            "iteration": 0,
            "payload": payload or {},
        }
        self.events.append(record)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        detail = ""
        if payload:
            detail = " " + " ".join(f"{k}={v}" for k, v in list(payload.items())[:4])
        print(f"  [{agent}] {event}{detail}", flush=True)


PLANNER_PROMPT = """You are planning a literature search.

Research question:
{question}

Produce exactly {n} search queries that together cover this question. Each
query must be 2-6 words of the kind that appear in a paper's title or abstract
— not a sentence, not a question. Cover different facets: method, evaluation,
limitation.

Reply with JSON only, no prose:
{{"queries": ["...", "..."]}}"""


def plan(llm: OllamaClient, question: str, n: int, trace: Trace) -> list[str]:
    trace.emit("planner", "agent_start", {"model": llm.model})
    raw = llm.complete(
        PLANNER_PROMPT.format(question=question, n=n),
        max_tokens=MAX_OUTPUT_TOKENS, force_json=True,
    )
    queries = _queries_from(raw, question, n)
    trace.emit("planner", "plan_ready", {"queries": len(queries)})
    trace.emit("planner", "agent_end", {"queries": queries})
    return queries


def _queries_from(raw: str, question: str, n: int) -> list[str]:
    try:
        match = re.search(r"\{.*\}", raw, re.S)
        payload = json.loads(match.group(0)) if match else {}
        queries = [str(q).strip() for q in payload.get("queries", []) if str(q).strip()]
    except (json.JSONDecodeError, AttributeError, TypeError):
        queries = []
    if not queries:
        queries = [" ".join(question.split()[:6])]
    return queries[:n]


def retrieve(queries: list[str], trace: Trace, year_min: int | None = 2019) -> list:
    from researchgpt.tools.search_sources import (
        search_arxiv,
        search_openalex,
        search_semantic_scholar,
    )

    trace.emit("retriever", "agent_start", {"queries": len(queries)})
    by_doi: dict[str, Any] = {}
    by_title: dict[str, Any] = {}
    failures = 0

    for query in queries:
        for name, fn in (
            ("openalex", lambda q: search_openalex(
                q, year_min=year_min, max_results=MAX_PER_SOURCE)),
            ("arxiv", lambda q: search_arxiv(q, max_results=MAX_PER_SOURCE)),
            ("semantic_scholar", lambda q: search_semantic_scholar(
                q, year_min=year_min, max_results=MAX_PER_SOURCE)),
        ):
            try:
                found = fn(query)
            except Exception as exc:
                failures += 1
                trace.emit("retriever", "source_failed",
                           {"source": name, "query": query, "error": type(exc).__name__})
                continue
            for paper in found:
                doi = (getattr(paper, "doi", None) or "").lower().strip()
                title = re.sub(r"\W+", " ", (paper.title or "")).strip().lower()
                if doi and doi in by_doi:
                    continue
                if not doi and title and title in by_title:
                    continue
                if doi:
                    by_doi[doi] = paper
                elif title:
                    by_title[title] = paper
            trace.emit("retriever", "search",
                       {"source": name, "query": query, "found": len(found)})

    papers = list(by_doi.values()) + list(by_title.values())
    trace.emit("retriever", "agent_end", {"n_papers": len(papers), "failures": failures})
    return papers


def rank(papers: list, question: str, trace: Trace) -> list:
    import torch

    trace.emit("ranker", "agent_start", {"candidates": len(papers)})
    model, tokenizer = checkpoints.load("ranker")

    texts = [
        f"{p.title or ''}\n{(getattr(p, 'abstract', '') or '')[:1500]}" for p in papers
    ]
    scores: list[float] = []
    batch = 16
    with torch.no_grad():
        for i in range(0, len(texts), batch):
            chunk = texts[i:i + batch]
            enc = tokenizer([question] * len(chunk), chunk, padding=True,
                            truncation=True, max_length=512, return_tensors="pt")
            logits = model(**enc).logits


            scores.extend(
                (logits[:, 0] if logits.shape[-1] == 1 else logits[:, -1]).tolist()
            )

    ordered = [p for _, p in sorted(zip(scores, papers, strict=True),
                                    key=lambda pair: pair[0], reverse=True)]
    keep = max(MIN_KEPT, min(MAX_KEPT, len(ordered) // KEEP_RATIO or 1))
    kept = ordered[:keep]

    fetched = _fetch_full_text(kept, trace)

    trace.emit("ranker", "agent_end",
               {"ranked": len(ordered), "kept": len(kept),
                "ratio": f"1:{KEEP_RATIO}", "full_text": fetched})
    return kept


def _fetch_full_text(kept: list, trace: Trace) -> int:
    counts = {"full_text": 0, "abstract_only": 0, "none": 0}

    def record(paper, availability: str, chars: int) -> None:
        counts[availability] = counts.get(availability, 0) + 1
        trace.emit("ranker", "pdf",
                   {"paper_id": paper.paper_id, "availability": availability,
                    "chars": chars})

    pdf_reader.fetch_many(kept, on_result=record)
    trace.emit("ranker", "pdf_summary", counts)
    return counts["full_text"]


def _chunks(text: str, size: int) -> list[str]:
    out, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind("\n\n", start, end)
            if cut == -1:
                cut = text.rfind(". ", start, end)
            if cut > start + size // 2:
                end = cut
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        start = end
    return out


def summarise(papers: list, trace: Trace, max_papers: int) -> list[dict]:
    import torch

    papers = papers[:max_papers]
    trace.emit("extractor", "agent_start", {"papers": len(papers)})
    model, tokenizer = checkpoints.load("extractor")

    out: list[dict] = []
    with torch.no_grad():
        for i, paper in enumerate(papers, 1):
            full = pdf_reader.cached_text(paper.paper_id)
            source = (full or getattr(paper, "abstract", "") or paper.title or "").strip()
            availability = "full_text" if full else (
                "abstract_only" if getattr(paper, "abstract", None) else "none")
            if not source:
                trace.emit("extractor", "skipped",
                           {"paper_id": paper.paper_id, "why": "no text"})
                continue

            chunks = _chunks(source, CHUNK_CHARS) if full else [source]
            pieces: list[str] = []
            for chunk in chunks[:MAX_CHUNKS]:
                enc = tokenizer(chunk, truncation=True, max_length=1024,
                                return_tensors="pt")
                ids = model.generate(**enc, max_new_tokens=MAX_OUTPUT_TOKENS,
                                     num_beams=4, no_repeat_ngram_size=3)
                piece = tokenizer.decode(ids[0], skip_special_tokens=True).strip()
                if piece:
                    pieces.append(piece)
            summary = " ".join(pieces).strip()
            if not summary:
                continue

            out.append({
                "n": i,
                "paper_id": paper.paper_id,
                "title": paper.title,
                "year": getattr(paper, "year", None),
                "text_availability": availability,
                "summary": summary,
            })
            trace.emit("extractor", "summarised",
                       {"paper_id": paper.paper_id, "availability": availability,
                        "source_chars": len(source), "chunks": len(chunks[:MAX_CHUNKS]),
                        "chars": len(summary)})

    trace.emit("extractor", "agent_end", {"summaries": len(out)})
    return out


SECTIONS: tuple[tuple[str, str], ...] = (
    ("Architectures and methods", "the method and architecture used"),
    ("Datasets", "the datasets used"),
    ("Metrics and evaluation", "the evaluation metrics and results"),
    ("Advantages and limitations", "the advantages and limitations"),
)


def write(question: str, summaries: list[dict], trace: Trace) -> str:
    import torch

    trace.emit("writer", "agent_start",
               {"summaries": len(summaries), "sections": len(SECTIONS),
                "checkpoint": checkpoints.SPECS["extractor"].filename})


    model, tokenizer = checkpoints.load("extractor")

    parts: list[str] = [f"# {question}\n"]
    generated = 0
    with torch.no_grad():
        for heading, focus in SECTIONS:
            lines: list[str] = []
            for s in summaries:
                source = (s.get("summary") or "").strip()
                if not source:
                    continue
                enc = tokenizer(f"{focus}: {source}", truncation=True,
                                max_length=1024, return_tensors="pt")
                ids = model.generate(**enc, max_new_tokens=MAX_OUTPUT_TOKENS,
                                     num_beams=4, no_repeat_ngram_size=3)
                text = tokenizer.decode(ids[0], skip_special_tokens=True).strip()
                if not text:
                    continue
                if text[-1] not in ".!?":
                    text += "."
                lines.append(f"{text} [{s['n']}]")
                generated += 1
            if lines:
                parts.append(f"## {heading}\n\n" + " ".join(lines) + "\n")

    review = "\n".join(parts).strip()


    trace.emit("writer", "agent_end",
               {"chars": len(review), "sections": len(parts) - 1,
                "sentences": generated})
    return review


_CITE = re.compile(r"\[(\d+)\]")


def verify(review: str, summaries: list[dict], trace: Trace,
           threshold: float = 0.5) -> dict:
    import torch

    trace.emit("verifier", "agent_start", {})
    model, tokenizer = checkpoints.load("verifier")
    labels = checkpoints.SPECS["verifier"].labels
    by_n = {s["n"]: s for s in summaries}

    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", review)
        if s.strip() and not s.strip().startswith("#")
    ]

    kept, dropped = [], []
    with torch.no_grad():
        for sentence in sentences:
            cited = [int(n) for n in _CITE.findall(sentence)]
            evidence = " ".join(
                by_n[n]["summary"] for n in cited if n in by_n
            ).strip()
            if not evidence:


                continue
            enc = tokenizer(evidence, sentence, truncation=True,
                            max_length=512, return_tensors="pt")
            probs = torch.softmax(model(**enc).logits, dim=-1)[0]
            idx = int(probs.argmax())
            verdict = labels[idx] if idx < len(labels) else str(idx)
            score = float(probs[idx])
            row = {
                "text": sentence,
                "verdict": verdict,
                "support_score": score,
                "paper_ids": [by_n[n]["paper_id"] for n in cited if n in by_n],
            }
            (kept if verdict == "SUPPORT" and score >= threshold
             else dropped).append(row)

    total = len(kept) + len(dropped)
    grounding = len(kept) / total if total else 0.0
    trace.emit("verifier", "agent_end",
               {"kept": len(kept), "dropped": len(dropped),
                "grounding": round(grounding, 4)})
    return {"verified": kept, "dropped": dropped, "grounding_score": grounding}


CRITIC_PROMPT = """You are grading a generated literature review.

The question that was asked:
{question}

The review that was produced:
{review}

Grounding measured by the verifier: {grounding:.2f}
({kept} claims supported by their cited source, {dropped} not.)

Score it. Reply with JSON only:
{{"coverage": 1-5,
  "grounding": 1-5,
  "reasoning": 1-5,
  "verdict": "ACCEPT" or "REVISE",
  "why": "one sentence"}}"""


def critique(llm: OllamaClient, question: str, review: str, verdicts: dict,
             trace: Trace) -> dict:
    trace.emit("critic", "agent_start", {"model": llm.model})
    raw = llm.complete(
        CRITIC_PROMPT.format(
            question=question, review=review,
            grounding=verdicts["grounding_score"],
            kept=len(verdicts["verified"]), dropped=len(verdicts["dropped"]),
        ),
        max_tokens=MAX_OUTPUT_TOKENS, force_json=True,
    )
    try:
        match = re.search(r"\{.*\}", raw, re.S)
        scored = json.loads(match.group(0)) if match else {}
    except (json.JSONDecodeError, AttributeError):
        scored = {"verdict": "UNPARSED", "why": raw[:200]}
    trace.emit("critic", "critic_decision", scored)
    trace.emit("critic", "agent_end", {})
    return scored


def preflight(need_models: bool) -> None:
    if not need_models:
        return
    missing = [
        str(checkpoints.checkpoint_path(n))
        for n, ok in checkpoints.available().items() if not ok
    ]
    if missing:
        raise SystemExit(
            "Missing checkpoints:\n  " + "\n  ".join(missing)
            + "\n\nPut them there, or set RESEARCHGPT_CHECKPOINT_DIR."
        )


def run(question: str, *, max_papers: int, queries: int,
        host: str | None, model: str | None) -> dict:
    run_id = time.strftime("local-%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = OUT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace = Trace(run_id, run_dir / "trace.jsonl")

    llm = OllamaClient(host=host, model=model)
    trace.emit("graph", "run_start",
               {"question": question, "max_papers": max_papers,
                "model": llm.model, "host": llm.host})

    started = time.time()
    queries_out = plan(llm, question, queries, trace)
    papers = retrieve(queries_out, trace)
    if not papers:
        raise SystemExit("No papers retrieved — check the network and try again.")
    kept = rank(papers, question, trace)
    summaries = summarise(kept, trace, max_papers)
    if not summaries:
        raise SystemExit("Nothing could be summarised.")
    review = write(question, summaries, trace)
    verdicts = verify(review, summaries, trace)
    scored = critique(llm, question, review, verdicts, trace)
    elapsed = time.time() - started

    (run_dir / "review.md").write_text(review, encoding="utf-8")
    (run_dir / "claims.json").write_text(
        json.dumps(verdicts, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "summaries.json").write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "critic.json").write_text(
        json.dumps(scored, indent=2, ensure_ascii=False), encoding="utf-8")

    trace.emit("graph", "run_end", {
        "papers": len(papers), "kept": len(kept), "summarised": len(summaries),
        "verified_claims": len(verdicts["verified"]),
        "dropped_claims": len(verdicts["dropped"]),
        "grounding_score": verdicts["grounding_score"],
        "elapsed_s": round(elapsed, 1),
    })
    print(f"\n  artefacts -> {run_dir}\n  elapsed   -> {elapsed / 60:.1f} min")
    return {"run_dir": str(run_dir), "critic": scored, **verdicts}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Seven-agent pipeline on local checkpoints plus Ollama."
    )
    ap.add_argument("--question", required=True)
    ap.add_argument("--max-papers", type=int, default=10,
                    help="how many ranked papers reach the summariser")
    ap.add_argument("--queries", type=int, default=2,
                    help="how many search queries the planner writes")
    ap.add_argument("--host", default=None, help="Ollama host; else $OLLAMA_HOST")
    ap.add_argument("--model", default=None, help="Ollama model; else $OLLAMA_MODEL")
    ap.add_argument("--skip-preflight", action="store_true",
                    help="start even if a checkpoint is missing")
    args = ap.parse_args(argv)

    preflight(need_models=not args.skip_preflight)
    try:
        run(args.question, max_papers=args.max_papers, queries=args.queries,
            host=args.host, model=args.model)
    except OllamaError as exc:
        raise SystemExit(f"Ollama: {exc}") from exc
    return 0


if __name__ == "__main__":
    sys.exit(main())
