// Small formatters, shared. Every one of these was being written inline in two
// or three panels with slightly different rounding, which is how "551 papers"
// and "551.0 papers" end up on the same screen.

export function num(n) {
  return n == null || Number.isNaN(n) ? '—' : Number(n).toLocaleString()
}

export function pct(x, digits = 1) {
  return x == null || Number.isNaN(x) ? '—' : `${(x * 100).toFixed(digits)}%`
}

/** Milliseconds as something a human reads at a glance. */
export function ms(v) {
  if (v == null || Number.isNaN(v)) return '—'
  if (v < 1000) return `${Math.round(v)} ms`
  const s = v / 1000
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)} s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${String(Math.round(s % 60)).padStart(2, '0')}s`
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`
}

/** "4 min ago". Falls back to the raw string if the timestamp will not parse -
 *  showing the reader the value we were given beats showing "Invalid Date". */
export function ago(iso) {
  if (!iso) return ''
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return String(iso)
  const s = (Date.now() - t) / 1000
  if (s < 45) return 'just now'
  if (s < 5400) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  if (s < 2592000) return `${Math.round(s / 86400)} d ago`
  return new Date(t).toLocaleDateString()
}

/** The full timestamp, for a title attribute next to the relative one. */
export function stamp(iso) {
  if (!iso) return ''
  const t = Date.parse(iso)
  return Number.isNaN(t) ? String(iso) : new Date(t).toLocaleString()
}

export function truncate(s, n = 120) {
  const v = String(s || '')
  return v.length > n ? `${v.slice(0, n - 1)}…` : v
}

/** A run id is `20260828T101500Z-ab12cd34`; the tail alone identifies it in a
 *  list and fits in a narrow rail. */
export function shortId(id) {
  const s = String(id || '')
  const dash = s.lastIndexOf('-')
  return dash > 0 ? s.slice(dash + 1) : s
}
