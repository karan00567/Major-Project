<script setup>
// T-606 — Panel 2. The six agents lighting up as SSE events arrive.
// TASKLIST: "Makes the 'agentic' claim visible in the first thirty seconds."
//
// ★ The Critic decisions are the part worth watching. RETRIEVE and REPLAN are
// what distinguish this from a pipeline, so they render as a visible chain
// rather than being buried in a log — on the M2 run that chain reads
// RETRIEVE -> REPLAN -> RETRIEVE -> WRITE, which IS the agentic claim.
//
// The raw tail of trace events was removed (2026-08-29): with a finished run it
// only ever read "graph run_end / critic agent_end / verifier
// verification_summary ...", which is the shape of the log rather than anything
// about this run.
//
// What replaced it (2026-08-30) is the opposite of a log dump: the same events,
// READ, so each stage states the one number that says how it went, and each
// Critic decision carries the arithmetic that produced it. A reason belongs on
// the page, not only in a `title` a screenshot cannot show — "271 papers
// retained, below min_papers=5000" is why the run replanned, and it is the
// difference between demonstrating the loop and asserting it.
import { computed } from 'vue'
import { AGENTS, AGENT_ROLE, stages } from '../lib/runStats.js'
import { ms, num, pct } from '../lib/format.js'

const props = defineProps({
  digest: { type: Object, required: true },
  running: Boolean,
})

const state = computed(() => props.digest.agents)
const rail = computed(() => stages(props.digest))
const decisions = computed(() => props.digest.decisions)

/** The searches, grouped by the iteration that issued them. Two groups means
 *  the Critic sent the run back and the Planner wrote new queries — which is
 *  exactly the thing worth being able to check. */
const searchRounds = computed(() => {
  const rounds = new Map()
  for (const s of props.digest.searches) {
    if (!rounds.has(s.iteration)) rounds.set(s.iteration, [])
    rounds.get(s.iteration).push(s)
  }
  return [...rounds.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([iteration, rows]) => ({
      iteration,
      rows,
      papers: rows.reduce((n, r) => n + (r.added || 0), 0),
      queries: new Set(rows.map((r) => r.query)).size,
    }))
})

/** Queries in the later rounds that no earlier round had issued. The README
 *  claims the replan produced "12 new queries with zero repeats"; this is that
 *  claim, computed from the run in front of you. */
const freshQueries = computed(() => {
  const rounds = searchRounds.value
  if (rounds.length < 2) return null
  const seen = new Set(rounds[0].rows.map((r) => r.query))
  const later = new Set()
  for (const round of rounds.slice(1)) for (const r of round.rows) later.add(r.query)
  const fresh = [...later].filter((q) => !seen.has(q))
  return { fresh: fresh.length, total: later.size }
})

const DECISION_CLS = {
  WRITE: 'bg-write/15 text-write dark:text-write-lite',
  RETRIEVE: 'bg-retrieve/15 text-retrieve dark:text-retrieve-lite',
  REPLAN: 'bg-replan/15 text-replan dark:text-replan-lite',
}

const STATUS_CLS = {
  idle: 'border-paper-line text-ink-faint dark:border-night-line dark:text-night-faint',
  active: 'border-replan bg-replan/10 text-replan dark:text-replan-lite',
  done: 'border-supported/50 bg-supported/10 text-supported dark:text-supported-lite',
  error: 'border-unsupported bg-unsupported/10 text-unsupported dark:text-unsupported-lite',
}
</script>

<template>
  <section class="panel panel-pad">
    <header class="panel-head mb-3">
      <h2 class="panel-title"><span class="panel-index">2</span> Agents</h2>
      <p class="text-[0.72rem] text-ink-dim dark:text-night-dim">
        <span v-if="running"
              class="mr-1 inline-flex items-center gap-1 text-replan
                     dark:text-replan-lite">
          <span class="h-1.5 w-1.5 animate-pulse-ring rounded-full bg-replan" />
          live
        </span>
        iteration {{ digest.iteration }}<template v-if="digest.maxIterations">
        of {{ digest.maxIterations }}</template> · {{ digest.events }} events
      </p>
    </header>

    <p v-if="!digest.events" class="panel-note">
      Nothing streaming yet. Open a run to replay its trace, or start one.
    </p>

    <!-- The seven agents. Each carries how many times it ran and how long it
         held the graph, because "the Ranker took ten minutes" is the single
         most useful thing to know about a slow run and it was not shown. -->
    <ol v-if="digest.events" class="flex flex-wrap gap-1.5">
      <li
        v-for="a in AGENTS" :key="a"
        class="flex items-center gap-1.5 rounded-full border px-2.5 py-1
               text-[0.78rem] transition"
        :class="STATUS_CLS[state[a].status]"
        :title="AGENT_ROLE[a]"
      >
        <span
          v-if="state[a].status === 'active'"
          class="h-1.5 w-1.5 animate-pulse-ring rounded-full bg-replan"
        />
        {{ a }}
        <span v-if="state[a].runs > 1"
              class="rounded-full bg-black/10 px-1.5 text-[0.66rem] font-semibold
                     dark:bg-white/10"
              :title="`ran ${state[a].runs} times — the Critic sent the graph back`">
          ×{{ state[a].runs }}
        </span>
        <span v-if="state[a].elapsedMs"
              class="font-mono text-[0.66rem] opacity-70">{{ ms(state[a].elapsedMs) }}</span>
      </li>
    </ol>

    <!-- The stage rail: one line per stage, with the number that matters. -->
    <ol v-if="digest.events" class="mt-4 space-y-1">
      <li v-for="(s, i) in rail" :key="s.key"
          class="flex items-baseline gap-3 rounded-lg px-2 py-1.5 transition
                 hover:bg-paper-sunk dark:hover:bg-night-sunk"
          :class="s.value ? '' : 'opacity-45'">
        <span class="w-4 shrink-0 font-mono text-[0.7rem] text-ink-faint
                     dark:text-night-faint">{{ i + 1 }}</span>
        <span class="w-16 shrink-0 text-[0.8rem] font-semibold">{{ s.label }}</span>
        <span class="w-32 shrink-0 font-mono text-[0.78rem] tabular-nums
                     text-ink dark:text-night-fg">{{ s.value || '—' }}</span>
        <span class="min-w-0 flex-1 truncate text-[0.76rem] text-ink-dim
                     dark:text-night-dim" :title="s.detail">{{ s.detail }}</span>
      </li>
    </ol>

    <!-- Critic decisions, with the arithmetic that produced each one. -->
    <div v-if="decisions.length" class="mt-4 border-t border-paper-hair pt-3
                                        dark:border-night-hair">
      <h3 class="panel-title mb-2">Critic — every gate it read</h3>
      <ol class="chain space-y-1.5">
        <li v-for="(d, i) in decisions" :key="i"
            class="flex flex-wrap items-baseline gap-x-2.5 gap-y-1 rounded-lg
                   border border-paper-hair px-2.5 py-1.5
                   dark:border-night-hair">
          <span class="font-mono text-[0.68rem] text-ink-faint dark:text-night-faint">
            i{{ d.iteration }}
          </span>
          <span class="rounded px-1.5 py-0.5 font-mono text-[0.7rem] font-semibold"
                :class="DECISION_CLS[d.decision]"
                :title="d.reasons.join(' | ')">{{ d.decision }}</span>
          <span v-if="d.papers != null"
                class="text-[0.74rem] text-ink-dim dark:text-night-dim">
            {{ num(d.papers) }} papers
          </span>
          <span v-if="d.coverage != null"
                class="text-[0.74rem] text-ink-dim dark:text-night-dim">
            · coverage {{ pct(d.coverage, 0) }}
          </span>
          <span v-if="d.grounding != null"
                class="text-[0.74rem] text-ink-dim dark:text-night-dim">
            · grounding {{ pct(d.grounding, 1) }}
          </span>
          <span v-if="d.reasons.length"
                class="w-full text-[0.76rem] italic text-ink-dim dark:text-night-dim">
            {{ d.reasons.join(' · ') }}
          </span>
        </li>
      </ol>
    </div>

    <!-- The queries themselves. Collapsed by default: it is the proof, not the
         headline, and <details> keeps it keyboard-reachable for free. -->
    <details v-if="searchRounds.length" class="group mt-4">
      <summary class="flex cursor-pointer list-none items-center gap-2 rounded-lg
                      px-2 py-1.5 text-[0.78rem] font-medium text-ink-dim
                      transition hover:bg-paper-sunk hover:text-ink
                      dark:text-night-dim dark:hover:bg-night-sunk
                      dark:hover:text-night-fg">
        <span class="transition group-open:rotate-90" aria-hidden="true">›</span>
        Search queries
        <span class="pill-soft">{{ digest.searches.length }} issued</span>
        <span v-if="freshQueries"
              class="pill bg-replan/15 text-replan dark:text-replan-lite"
              title="Queries in the post-replan rounds that no earlier round had issued">
          {{ freshQueries.fresh }} of {{ freshQueries.total }} new after replanning
        </span>
      </summary>

      <div v-for="round in searchRounds" :key="round.iteration" class="mt-2">
        <p class="mb-1 text-[0.72rem] font-semibold uppercase tracking-[0.07em]
                  text-ink-dim dark:text-night-dim">
          round {{ round.iteration }} · {{ round.queries }} queries ·
          {{ num(round.papers) }} papers added
        </p>
        <ul class="scroll-soft max-h-52 space-y-0.5 overflow-y-auto pr-1">
          <li v-for="(s, i) in round.rows" :key="i"
              class="flex items-baseline gap-2 rounded px-1.5 py-1 text-[0.75rem]
                     hover:bg-paper-sunk dark:hover:bg-night-sunk">
            <span class="w-9 shrink-0 font-mono text-[0.68rem] text-ink-faint
                         dark:text-night-faint">{{ s.sq }}</span>
            <span class="min-w-0 flex-1 truncate" :title="s.query">{{ s.query }}</span>
            <span class="pill-soft shrink-0">{{ s.source }}</span>
            <span class="w-24 shrink-0 text-right font-mono text-[0.7rem]
                         tabular-nums text-ink-dim dark:text-night-dim"
                  :title="`${s.returned} returned, ${s.added} not already in the corpus`">
              +{{ s.added ?? 0 }} / {{ s.returned ?? 0 }}
            </span>
          </li>
        </ul>
      </div>
    </details>

    <!-- Anything that went wrong. A disabled source or a skipped rerank changes
         how the numbers above should be read, so it cannot be silent. -->
    <ul v-if="digest.problems.length"
        class="mt-4 space-y-1 rounded-lg border-l-[3px] border-replan bg-replan/10
               px-3 py-2">
      <li v-for="(p, i) in digest.problems" :key="i"
          class="text-[0.76rem] leading-relaxed text-ink-dim dark:text-night-dim">
        <span class="font-mono text-[0.7rem] font-semibold text-replan
                     dark:text-replan-lite">{{ p.agent }} · {{ p.event }}</span>
        — {{ p.detail }}
      </li>
    </ul>
  </section>
</template>
