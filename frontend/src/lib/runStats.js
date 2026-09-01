// Everything the trace already says, turned into something a panel can render.
//
// ★ Why this file exists. `trace.jsonl` is the single source of truth for what
// happened (README, "Run it"), and it is far richer than what the UI was
// showing: the panels rendered `agent_start` / `agent_end` and the Critic's
// decision, and threw the rest away. So the app knew that the Retriever ran but
// not that it issued 23 source queries for 271 new papers; knew the Ranker
// finished but not that it reranked 233 of 271 in 125 seconds; knew a claim was
// dropped but not that the Verifier's bar was 0.7. All of that is already on
// the wire; none of it reached the screen.
//
// ⚠️ Pure and defensive on purpose. Events arrive from a stream that replays
// history, a live run delivers the same shapes half-finished, and old runs on
// disk predate fields added later — so every read is optional and every caller
// gets something it can render. A missing key must produce an em dash, never a
// crash that blanks the panel.

export const AGENTS = [
  'planner', 'retriever', 'ranker', 'extractor', 'writer', 'verifier', 'critic',
]

/** What each agent is for, in one line. Shown with its chip: the six names mean
 *  nothing to a reader seeing the pipeline for the first time. */
export const AGENT_ROLE = {
  planner: 'question to sub-questions and a search plan',
  retriever: 'OpenAlex + arXiv, dedup by DOI then title',
  ranker: 'embed, hybrid BM25 + dense, cross-encoder rerank',
  extractor: 'per paper: method, datasets, metrics, limitations',
  writer: 'thematic synthesis with [n] citations',
  verifier: 'claims to NLI against evidence, drop the ungrounded',
  critic: 'coverage / corpus / grounding gates',
}

const last = (arr) => (arr.length ? arr[arr.length - 1] : null)
const payloadsOf = (events, name) =>
  events.filter((e) => e.event === name).map((e) => e.payload || {})

/**
 * Fold a run's events into one digest.
 *
 * Summaries that describe an ITERATION are summed: the Retriever runs again
 * after a REPLAN and reports only what that pass added. Summaries that describe
 * the run's current STATE — the ranking, the extraction, the draft, the
 * verification — take the latest, because an earlier one has been superseded
 * rather than added to.
 */
export function digest(events) {
  const evs = Array.isArray(events) ? events : []

  // ⚠️ Two emitters, two shapes. graph/build.py writes `research_question`,
  // cli.py writes `question` — and a CLI run emits its own `run_start` FIRST,
  // so taking the first record and reading one key misses the other 85% of the
  // time (68 of 80 runs on disk carry the CLI shape). Mirrors `_question_of`
  // in api/app.py; the two must stay in agreement.
  const starts = evs.filter((e) => e.event === 'run_start').map((e) => e.payload || {})
  const start = starts.find((p) => p.research_question || p.question) || starts[0] || {}
  const end = last(payloadsOf(evs, 'run_end')) || {}
  const failed = last(payloadsOf(evs, 'run_failed'))

  // --- per-agent state and cost ------------------------------------------
  const agents = {}
  for (const a of AGENTS) agents[a] = { status: 'idle', runs: 0, elapsedMs: 0 }
  for (const e of evs) {
    const a = agents[e.agent]
    if (!a) continue
    if (e.event === 'agent_start') { a.status = 'active'; a.runs += 1 }
    if (e.event === 'agent_end') {
      a.status = 'done'
      a.elapsedMs += Number(e.payload?.elapsed_ms || 0)
    }
    if (e.event === 'agent_error') a.status = 'error'
  }

  // --- the plan -----------------------------------------------------------
  const plan = last(payloadsOf(evs, 'plan_ready'))
  const replans = payloadsOf(evs, 'replanning').length

  // --- retrieval: per-iteration, so summed --------------------------------
  const retrievals = payloadsOf(evs, 'retrieval_summary')
  const retrieval = retrievals.length
    ? retrievals.reduce(
        (acc, r) => ({
          queries: acc.queries + (r.queries || 0),
          sourceQueries: acc.sourceQueries + (r.source_queries || 0),
          failures: acc.failures + (r.failures || 0),
          newPapers: acc.newPapers + (r.new_papers || 0),
          newChunks: acc.newChunks + (r.new_chunks || 0),
          withAbstract: acc.withAbstract + (r.with_abstract || 0),
          budgetExhausted: acc.budgetExhausted || !!r.budget_exhausted,
          sourcesDisabled: [...new Set([...acc.sourcesDisabled,
                                        ...(r.sources_disabled || [])])],
        }),
        { queries: 0, sourceQueries: 0, failures: 0, newPapers: 0, newChunks: 0,
          withAbstract: 0, budgetExhausted: false, sourcesDisabled: [] },
      )
    : null

  // Every search the Retriever actually issued. This is the evidence that a
  // REPLAN produced NEW queries rather than repeating itself — the most
  // load-bearing fact about the loop, and it was on no screen anywhere.
  const searches = evs
    .filter((e) => e.event === 'search')
    .map((e) => ({
      sq: e.payload?.sq_id || '',
      query: e.payload?.query || '',
      source: e.payload?.source || '',
      returned: e.payload?.returned ?? null,
      added: e.payload?.new ?? null,
      error: e.payload?.error || null,
      iteration: e.payload?.iteration ?? 0,
    }))

  const rank = last(payloadsOf(evs, 'rank_summary'))
  const embedCache = last(payloadsOf(evs, 'embed_cache'))
  const extract = last(payloadsOf(evs, 'extract_summary'))
  const progress = last(payloadsOf(evs, 'extract_progress'))
  const review = last(payloadsOf(evs, 'review_written'))
  const sections = payloadsOf(evs, 'section_written')
  const decomposed = last(payloadsOf(evs, 'claims_decomposed'))
  const verification = last(payloadsOf(evs, 'verification_summary'))

  const decisions = payloadsOf(evs, 'critic_decision').map((p) => ({
    decision: p.decision,
    iteration: p.iteration ?? 0,
    maxIterations: p.max_iterations ?? null,
    papers: p.papers ?? null,
    coverage: p.coverage ?? null,
    uncovered: p.uncovered || [],
    grounding: p.grounding_score ?? null,
    reasons: p.reasons || [],
  }))

  // --- LLM cost -----------------------------------------------------------
  // Counted from the stream when present; `run_end` carries the same totals and
  // is authoritative for a finished run, so it wins when it is there.
  const requests = evs.filter((e) => e.event === 'request').length
  const cacheHits = evs.filter((e) => e.event === 'cache_hit').length
  const llmRequests = end.llm_requests ?? requests
  const llmCacheHits = end.llm_cache_hits ?? cacheHits
  const llmTotal = llmRequests + llmCacheHits

  // --- wall clock ---------------------------------------------------------
  const stamps = evs.map((e) => Date.parse(e.ts)).filter((t) => !Number.isNaN(t))
  const wallMs = stamps.length > 1 ? Math.max(...stamps) - Math.min(...stamps) : null

  const problems = evs
    .filter((e) => ['agent_error', 'error', 'run_failed', 'source_disabled',
                    'section_failed', 'rank_skipped'].includes(e.event))
    .map((e) => ({
      agent: e.agent || 'graph',
      event: e.event,
      detail: e.payload?.error || e.payload?.detail || e.payload?.reason
              || JSON.stringify(e.payload || {}).slice(0, 160),
    }))

  return {
    events: evs.length,
    question: start.research_question || start.question || null,
    // A CLI run nests its resolved config instead of naming the model flat.
    model: start.model || start.config?.llm?.model || null,
    maxPapers: start.max_papers ?? start.config?.review?.max_papers ?? null,
    startedAt: evs.length ? evs[0].ts : null,
    wallMs,
    finished: evs.some((e) => e.event === 'run_end'),
    failed: failed || null,
    agents,
    plan: plan && {
      subQuestions: plan.n_sub_questions ?? null,
      searchTasks: plan.n_search_tasks ?? null,
      facets: plan.facets || [],
      queries: plan.queries || [],
      meanTerms: plan.mean_query_terms ?? null,
      repairs: plan.repairs_used ?? null,
      replans,
    },
    retrieval,
    searches,
    rank: rank && {
      queries: rank.queries ?? null,
      chunks: rank.chunks ?? null,
      papers: rank.papers ?? null,
      ranked: rank.ranked ?? null,
      unrankedTail: rank.unranked_tail ?? null,
      reranker: rank.reranker || null,
      embedMs: rank.embed_ms ?? null,
      rerankMs: rank.rerank_ms ?? null,
      topTitles: rank.top_10 || [],
      embedCacheHitRate: embedCache?.hit_rate ?? null,
    },
    extract: (extract || progress) && {
      papers: extract?.papers ?? progress?.done ?? null,
      target: progress?.of ?? null,
      done: progress?.done ?? null,
      skippedNoText: extract?.skipped_no_text ?? null,
      failedAfterRepairs: extract?.failed_after_repairs ?? null,
      meanFields: extract?.mean_fields_of_8 ?? null,
      truncated: extract?.sources_truncated ?? null,
    },
    write: review && {
      sections: review.sections ?? null,
      references: review.references ?? null,
      chars: review.chars ?? null,
      citationsDropped: review.citations_dropped ?? null,
      themes: sections.map((s) => ({
        theme: s.theme, chars: s.chars, cited: s.sources_cited,
      })),
    },
    verify: verification && {
      claims: verification.claims ?? decomposed?.claims ?? null,
      supported: verification.supported ?? null,
      partial: verification.partial ?? null,
      dropped: verification.dropped ?? null,
      contradicted: verification.contradicted ?? null,
      abstractOnlyCapped: verification.abstract_only_capped ?? null,
      grounding: verification.grounding_score ?? null,
      threshold: verification.support_threshold ?? null,
      note: decomposed?.note || null,
    },
    decisions,
    iteration: decisions.length
      ? Math.max(...decisions.map((d) => d.iteration || 0))
      : 0,
    maxIterations: decisions.find((d) => d.maxIterations)?.maxIterations ?? null,
    llm: { requests: llmRequests, cacheHits: llmCacheHits,
           hitRate: llmTotal ? llmCacheHits / llmTotal : null },
    totals: {
      papers: end.papers ?? null,
      insights: end.insights ?? null,
      reviewChars: end.review_chars ?? null,
      verified: end.verified_claims ?? null,
      dropped: end.dropped_claims ?? null,
      grounding: end.grounding_score ?? null,
      iterations: end.iterations ?? null,
    },
    problems,
  }
}

/** The pipeline as a list of stages, each with the one number that says how it
 *  went. Drives the stage rail in Panel 2. A stage with nothing to say yet
 *  still renders, so the reader can see what has not happened. */
export function stages(d) {
  const n = (v) => (v == null ? 0 : Number(v)).toLocaleString()
  return [
    {
      key: 'planner',
      label: 'Plan',
      value: d.plan ? `${d.plan.subQuestions ?? '—'} sub-questions` : null,
      detail: d.plan
        ? `${d.plan.searchTasks ?? '—'} search tasks · facets: ${
            (d.plan.facets || []).join(', ') || 'none'}`
        : 'not started',
    },
    {
      key: 'retriever',
      label: 'Retrieve',
      value: d.retrieval ? `${n(d.retrieval.newPapers)} papers` : null,
      detail: d.retrieval
        ? `${d.retrieval.sourceQueries} source queries · ${
            n(d.retrieval.newChunks)} chunks · ${d.retrieval.failures} failed`
        : 'not started',
    },
    {
      key: 'ranker',
      label: 'Rank',
      value: d.rank ? `${n(d.rank.ranked)} reranked` : null,
      detail: d.rank
        ? `${n(d.rank.chunks)} chunks scored · ${
            n(d.rank.unrankedTail)} left in the tail`
        : 'not started',
    },
    {
      key: 'extractor',
      label: 'Extract',
      value: d.extract ? `${d.extract.papers ?? d.extract.done ?? 0} papers read` : null,
      detail: d.extract
        ? `${d.extract.meanFields != null
              ? `${d.extract.meanFields} of 8 fields filled`
              : 'in progress'}${
            d.extract.skippedNoText ? ` · ${d.extract.skippedNoText} had no text` : ''}`
        : 'not started',
    },
    {
      key: 'writer',
      label: 'Write',
      value: d.write ? `${d.write.sections ?? 0} sections` : null,
      detail: d.write
        ? `${n(d.write.chars)} characters · ${d.write.references ?? 0} references`
        : 'not started',
    },
    {
      key: 'verifier',
      label: 'Verify',
      value: d.verify ? `${d.verify.claims ?? 0} claims checked` : null,
      detail: d.verify
        ? `${d.verify.dropped ?? 0} dropped below a ${
            d.verify.threshold ?? '—'} support bar`
        : 'not started',
    },
  ]
}
