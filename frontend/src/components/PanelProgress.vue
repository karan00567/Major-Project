<script setup>
// T-606 — Panel 2. The six agents lighting up as SSE events arrive.
// TASKLIST: "Makes the 'agentic' claim visible in the first thirty seconds."
//
// ★ The Critic decisions are the part worth watching. RETRIEVE and REPLAN are
// what distinguish this from a pipeline, so they render as a visible chain
// rather than being buried in a log — on the M2 run that chain reads
// RETRIEVE -> REPLAN -> RETRIEVE -> WRITE, which IS the agentic claim.
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

const latest = computed(() => props.events.slice(-6).reverse())
</script>

<template>
  <section class="panel">
    <header>
      <h2>2 · Agents</h2>
      <p class="hint">iteration {{ iteration }} · {{ events.length }} trace events</p>
    </header>

    <ol class="agents">
      <li v-for="a in AGENTS" :key="a" :class="['agent', state[a].status]">
        <span class="name">{{ a }}</span>
        <span v-if="state[a].runs > 1" class="badge">x{{ state[a].runs }}</span>
      </li>
    </ol>

    <div v-if="decisions.length" class="decisions">
      <h3>Critic</h3>
      <div class="chain">
        <span
          v-for="(d, i) in decisions"
          :key="i"
          :class="['chip', d.decision.toLowerCase()]"
          :title="d.reasons.join(' | ')"
        >{{ d.decision }}</span>
      </div>
      <p class="why">{{ decisions[decisions.length - 1].reasons[0] }}</p>
    </div>

    <ul class="log">
      <li v-for="(e, i) in latest" :key="i">
        <code>{{ e.agent }}</code> {{ e.event }}
      </li>
    </ul>
  </section>
</template>

<style scoped>
.agents { list-style: none; display: flex; flex-wrap: wrap; gap: .4rem;
          margin: 0 0 .8rem; padding: 0; }
.agent { display: flex; align-items: center; gap: .3rem; padding: .3rem .6rem;
         border: 1px solid var(--line); border-radius: 999px; font-size: .82rem;
         color: var(--muted); }
.agent.active { border-color: #c98a2e; color: #c98a2e; background: #c98a2e14; }
.agent.done { border-color: #2f9e5f; color: #2f9e5f; background: #2f9e5f14; }
.agent.error { border-color: #d9534f; color: #d9534f; }
.badge { font-size: .68rem; background: var(--line); border-radius: 999px; padding: 0 .3rem; }
h3 { margin: .6rem 0 .3rem; font-size: .76rem; text-transform: uppercase;
     letter-spacing: .06em; color: var(--muted); }
.chain { display: flex; flex-wrap: wrap; gap: .35rem; }
.chip { padding: .18rem .55rem; border-radius: 4px; font-size: .76rem; font-weight: 600; }
.chip.write { background: #2f9e5f22; color: #2f9e5f; }
.chip.retrieve { background: #2f6fed22; color: #2f6fed; }
.chip.replan { background: #c98a2e22; color: #c98a2e; }
.why { font-size: .78rem; color: var(--muted); margin: .35rem 0 0; }
.log { list-style: none; margin: .8rem 0 0; padding: 0; font-size: .76rem;
       color: var(--muted); }
.log li { padding: .12rem 0; }
.hint { color: var(--muted); font-size: .82rem; margin: .2rem 0 .6rem; }
code { color: inherit; }
</style>
