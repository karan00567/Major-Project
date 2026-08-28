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
  es.onmessage = (m) => safeParse(m.data, onEvent)
  for (const name of [
    'run_start', 'agent_start', 'agent_end', 'critic_decision',
    'claims_decomposed', 'verification_summary', 'claim_dropped',
    'extract_progress', 'retrieval_summary', 'rank_summary', 'replanning',
    'run_end', 'run_failed',
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
