<script setup>
// T-606 — Panel 2. The six agents lighting up as SSE events arrive.
// TASKLIST: "Makes the 'agentic' claim visible in the first thirty seconds."
//
// ★ The Critic decisions are the part worth watching. RETRIEVE and REPLAN are
// what distinguish this from a pipeline, so they render as a visible chain
// rather than being buried in a log — on the M2 run that chain reads
// RETRIEVE -> REPLAN -> RETRIEVE -> WRITE, which IS the agentic claim.
//
// The raw tail of trace events and the Critic's reason line were removed
// (2026-08-29): with a finished run they only ever read "graph run_end /
// critic agent_end / verifier verification_summary ...", which is the shape of
// the log rather than anything about this run. The reasons are still there on
// hover - each chip carries them as its title - and trace.jsonl remains the
// full record for anyone who wants the events themselves.
import { computed } from 'vue'

const props = defineProps({
  events: { type: Array, default: () => [] },
  running: Boolean,
})

const AGENTS = ['planner', 'retriever', 'ranker', 'extractor', 'writer', 'verifier', 'critic']

const state = computed(() => {
  const s = {}
  for (const a of AGENTS) s[a] = { status: 'idle', runs: 0 }
  for (const e of props.events) {
    const a = e.agent
    if (!s[a]) continue
    if (e.event === 'agent_start') { s[a].status = 'active'; s[a].runs += 1 }
    if (e.event === 'agent_end') s[a].status = 'done'
    if (e.event === 'agent_error') s[a].status = 'error'
  }
  return s
})

const decisions = computed(() =>
  props.events
    .filter((e) => e.event === 'critic_decision')
    .map((e) => ({
      decision: e.payload.decision,
      iteration: e.payload.iteration,
      reasons: e.payload.reasons || [],
    })),
)

const iteration = computed(() => {
  const d = decisions.value
  return d.length ? Math.max(...d.map((x) => x.iteration || 0)) : 0
})

</script>

<template>
  <section class="panel">
    <header class="mb-3 flex items-baseline justify-between gap-2">
      <h2 class="panel-title">2 · Agents</h2>
      <p class="text-[0.72rem] text-ink-dim dark:text-night-dim">
        iteration {{ iteration }} · {{ events.length }} events
      </p>
    </header>

    <ol class="flex flex-wrap gap-1.5">
      <li
        v-for="a in AGENTS" :key="a"
        class="flex items-center gap-1.5 rounded-full border px-2.5 py-1
               text-[0.78rem] transition"
        :class="{
          'border-paper-line text-ink-dim dark:border-night-line dark:text-night-dim':
            state[a].status === 'idle',
          'border-replan bg-replan/10 text-replan': state[a].status === 'active',
          'border-supported bg-supported/10 text-supported': state[a].status === 'done',
          'border-unsupported bg-unsupported/10 text-unsupported': state[a].status === 'error',
        }"
      >
        <span
          v-if="state[a].status === 'active'"
          class="h-1.5 w-1.5 animate-pulse-ring rounded-full bg-replan"
        />
        {{ a }}
        <span v-if="state[a].runs > 1"
              class="rounded-full bg-black/10 px-1.5 text-[0.66rem] font-semibold
                     dark:bg-white/10">
          ×{{ state[a].runs }}
        </span>
      </li>
    </ol>

    <div v-if="decisions.length" class="mt-4">
      <h3 class="panel-title mb-1.5">Critic</h3>
      <div class="chain flex flex-wrap items-center gap-1.5">
        <template v-for="(d, i) in decisions" :key="i">
          <span v-if="i" class="text-ink-dim dark:text-night-dim">→</span>
          <span
            class="rounded px-2 py-0.5 font-mono text-[0.7rem] font-semibold"
            :class="{
              'bg-write/15 text-write': d.decision === 'WRITE',
              'bg-retrieve/15 text-retrieve': d.decision === 'RETRIEVE',
              'bg-replan/15 text-replan': d.decision === 'REPLAN',
            }"
            :title="d.reasons.join(' | ')"
          >{{ d.decision }}</span>
        </template>
      </div>
    </div>
  </section>
</template>
