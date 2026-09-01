// Thin wrapper over the five endpoints in PROJECT_PLAN §7.2.
//
// No store (TASKLIST T-604: "no Pinia - one page, one run, a store is
// ceremony"). State lives in App.vue; this file only talks to the network.

async function json(path, options) {
  const res = await fetch(path, options)
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body.detail) detail = body.detail
    } catch {
      /* a non-JSON error body is fine; keep the status line */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const health = () => json('/api/health')
export const listRuns = () => json('/api/runs?limit=50')
export const getResult = (runId) => json(`/api/runs/${encodeURIComponent(runId)}/result`)

export const startReview = (question, maxPapers) =>
  json('/api/review', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, max_papers: maxPapers, use_loop: true }),
  })

// T-609. Persisted to the run's trace, so an override survives a reload.
export const postOverride = (runId, claimId, decision, note) =>
  json(`/api/runs/${encodeURIComponent(runId)}/overrides`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ claim_id: claimId, decision, note }),
  })

// T-612. The sheet is rebuilt from the run's trace on every request, so it
// survives an API restart and shows what a previous session already scored.
export const getScoreSheet = (runId) =>
  json(`/api/runs/${encodeURIComponent(runId)}/scores`)

export const postScores = (runId, body) =>
  json(`/api/runs/${encodeURIComponent(runId)}/scores`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const artifactUrl = (runId, name) =>
  `/api/runs/${encodeURIComponent(runId)}/artifact/${encodeURIComponent(name)}`

/**
 * Subscribe to a run's trace.
 *
 * The server replays history before following the tail, so a late subscriber
 * still sees the whole story - which is also how a finished run replays for the
 * T-610 demo. `onEvent` therefore receives past events immediately.
 *
 * Returns a close function. Callers MUST call it: an EventSource left open
 * keeps reconnecting after the stream ends and quietly re-runs onEvent.
 */
export function streamEvents(runId, onEvent, onDone) {
  const es = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events`)

  // Named events, because the server sets `event:` to the trace's own event
  // name rather than using a single generic channel.
  //
  // ⚠️ EventSource ONLY delivers a named event to a listener registered for
  // that exact name - `onmessage` sees the unnamed default channel and nothing
  // else. So this list is not documentation, it is the filter: an event missing
  // from it is silently discarded, with no error anywhere.
  //
  // It was thirteen names, and the run page was consequently blind to the nine
  // richest payloads on the wire - `plan_ready` (the sub-questions), `search`
  // (every query and what it returned), `rank_summary`, `extract_summary`,
  // `review_written`, `embed_cache`, `request` / `cache_hit` (the LLM bill).
  // Enumerated from every event name emitted across src/researchgpt/ and
  // present in outputs/runs/*/trace.jsonl, 2026-08-30. Adding a new trace event
  // means adding it here too, or the UI will not see it.
  es.onmessage = (m) => safeParse(m.data, onEvent)
  for (const name of [
    // lifecycle
    'run_start', 'run_end', 'run_failed', 'agent_start', 'agent_end',
    'agent_error', 'error', 'artefacts_written',
    // planner
    'plan_ready', 'replanning',
    // retriever
    'search', 'retrieval_summary', 'source_disabled', 'retry',
    // ranker
    'embed_cache', 'rank_summary', 'rank_skipped',
    // extractor
    'extract_progress', 'extract_summary',
    // writer
    'section_written', 'section_failed', 'section_rejected_uncited',
    'section_uncited_retry', 'review_written',
    // verifier
    'claims_decomposed', 'claim_dropped', 'verification_summary',
    // critic + llm adapter
    'critic_decision', 'request', 'cache_hit',
  ]) {
    es.addEventListener(name, (m) => safeParse(m.data, onEvent))
  }

  es.addEventListener('done', (m) => {
    safeParse(m.data, (d) => onDone && onDone(d))
    es.close()
  })

  // An error after the server closed a finished stream is normal, not a fault.
  es.onerror = () => es.close()

  return () => es.close()
}

function safeParse(raw, fn) {
  try {
    fn(JSON.parse(raw))
  } catch {
    /* a malformed frame must not kill the stream */
  }
}
