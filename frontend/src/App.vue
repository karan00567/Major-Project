<script setup>
// T-604 — one page, four panels, Composition API, no Pinia. TASKLIST: "one
// page, one run — a store is ceremony."
import { computed, onMounted, onUnmounted, ref } from 'vue'
import PanelRun from './components/PanelRun.vue'
import PanelProgress from './components/PanelProgress.vue'
import PanelEvidence from './components/PanelEvidence.vue'
import PanelDropped from './components/PanelDropped.vue'
import { getResult, health, listRuns, startReview, streamEvents } from './api.js'

const runs = ref([])
const runId = ref('')
const result = ref(null)
const events = ref([])
const busy = ref(false)
const error = ref('')
const fixtureMode = ref(false)
const overrides = ref({})

let closeStream = null

async function refreshRuns() {
  try {
    runs.value = await listRuns()
  } catch (e) {
    error.value = e.message
  }
}

async function open(id) {
  stopStream()
  runId.value = id
  events.value = []
  overrides.value = {}
  error.value = ''
  try {
    result.value = await getResult(id)
  } catch (e) {
    error.value = e.message
    return
  }
  // Replays history, so opening a finished run fills Panel 2 exactly as a live
  // one does. That is what makes the T-610 pre-baked demo indistinguishable.
  closeStream = streamEvents(
    id,
    (ev) => events.value.push(ev),
    async () => {
      busy.value = false
      result.value = await getResult(id)
      refreshRuns()
    },
  )
}

async function start({ question, maxPapers }) {
  error.value = ''
  busy.value = true
  try {
    const accepted = await startReview(question, maxPapers)
    await open(accepted.run_id)
  } catch (e) {
    error.value = e.message
    busy.value = false
  }
}

// T-609. Held client-side for now and written back through the trace when the
// API grows a write endpoint; the shape matches graph/state.py::human_overrides
// so nothing has to be reinterpreted later.
function override({ claim, decision }) {
  const next = { ...overrides.value }
  if (decision === null) delete next[claim.claim_id]
  else next[claim.claim_id] = decision
  overrides.value = next
}

function stopStream() {
  if (closeStream) { closeStream(); closeStream = null }
}

onMounted(async () => {
  try {
    const h = await health()
    fixtureMode.value = h.fixture_mode
    if (h.fixture_mode && h.fixture_available) await open(h.fixture_run_id)
  } catch (e) {
    error.value = `API unreachable: ${e.message}`
  }
  refreshRuns()
})
onUnmounted(stopStream)

const grounding = computed(() =>
  result.value?.grounding_score != null
    ? `${(result.value.grounding_score * 100).toFixed(1)}%`
    : '—',
)
</script>

<template>
  <div class="app">
    <header class="top">
      <h1>ResearchGPT</h1>
      <div class="stats" v-if="result">
        <span><b>{{ result.counts.verified ?? 0 }}</b> claims kept</span>
        <span><b>{{ result.counts.dropped ?? 0 }}</b> dropped</span>
        <span><b>{{ grounding }}</b> grounded</span>
        <span v-if="result.decisions.length" class="chain">{{ result.decisions.join(' → ') }}</span>
      </div>
    </header>

    <div class="grid">
      <div class="col">
        <PanelRun
          :runs="runs" :busy="busy" :fixture-mode="fixtureMode" :error="error"
          @start="start" @open="open"
        />
        <PanelProgress :events="events" :running="busy" />
      </div>
      <div class="col wide">
        <PanelEvidence
          :review-markdown="result?.review_markdown || ''"
          :verified-claims="result?.verified_claims || []"
          :papers="result?.papers || []"
        />
        <PanelDropped
          :run-id="runId"
          :dropped-claims="result?.dropped_claims || []"
          :verified-count="result?.verified_claims?.length || 0"
          :artefacts="result?.artefacts || []"
          :overrides="overrides"
          @override="override"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.top { display: flex; align-items: baseline; gap: 1.2rem; flex-wrap: wrap;
       padding: .9rem 1.2rem; border-bottom: 1px solid var(--line); }
h1 { font-size: 1.05rem; margin: 0; letter-spacing: .01em; }
.stats { display: flex; gap: 1rem; font-size: .82rem; color: var(--muted); flex-wrap: wrap; }
.stats b { color: var(--fg); }
.chain { font-family: ui-monospace, monospace; font-size: .76rem; }
.grid { display: grid; grid-template-columns: 22rem 1fr; gap: 1rem; padding: 1rem 1.2rem; }
@media (max-width: 1000px) { .grid { grid-template-columns: 1fr; } }
.col { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }
</style>
