<script setup>
// T-604 — one page, four panels, Composition API, no Pinia. TASKLIST: "one
// page, one run — a store is ceremony."
import { computed, onMounted, onUnmounted, ref } from 'vue'
import PanelRun from './components/PanelRun.vue'
import PanelProgress from './components/PanelProgress.vue'
import PanelEvidence from './components/PanelEvidence.vue'
import PanelDropped from './components/PanelDropped.vue'
import PanelScores from './components/PanelScores.vue'
import DashboardView from './components/DashboardView.vue'
import { getResult, health, listRuns, postOverride, startReview, streamEvents } from './api.js'

const runs = ref([])
const runId = ref('')
const result = ref(null)
const events = ref([])
const busy = ref(false)
const error = ref('')
const fixtureMode = ref(false)
const overrides = ref({})

// Three views, chosen by path. A path check rather than vue-router: T-604
// chose "one page, one run - a store is ceremony", and a router for three
// static routes is the same kind of ceremony. Vite serves index.html for
// unknown paths (appType 'spa'), so these all load this app; navigation
// between them is a full page load, so none of this needs to be reactive.
//
//   /dashboard  what the project is, for someone who has never seen it (T-613)
//   /optimizer  the run page plus the human scoring sheet (T-612)
//   /           the run page
const route = window.location.pathname.replace(/\/+$/, '')
const onDashboard = ref(route === '/dashboard')
const onOptimizer = ref(route === '/optimizer')

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
    // T-609: rehydrate what a human already decided, so a reload does not
    // silently discard judgements that ARE in the audit record.
    overrides.value = Object.fromEntries(
      (result.value.human_overrides || []).map((o) => [o.claim_id, o.decision]),
    )
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

// T-609. Written back to the run's trace, which is the audit record the report
// will count overrides from (T-904). Optimistic locally, then reconciled with
// what the server actually stored - so a failed write cannot leave the UI
// claiming a judgement that was never recorded.
async function override({ claim, decision }) {
  const next = { ...overrides.value }
  if (decision === null) delete next[claim.claim_id]
  else next[claim.claim_id] = decision
  overrides.value = next

  try {
    const stored = await postOverride(runId.value, claim.claim_id, decision)
    overrides.value = Object.fromEntries(stored.map((o) => [o.claim_id, o.decision]))
  } catch (e) {
    error.value = `Override not saved: ${e.message}`
    overrides.value = Object.fromEntries(
      (result.value?.human_overrides || []).map((o) => [o.claim_id, o.decision]),
    )
  }
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
  <DashboardView v-if="onDashboard" />

  <div v-else class="min-h-screen">
    <header
      class="sticky top-0 z-20 flex flex-wrap items-center gap-x-6 gap-y-2
             border-b border-paper-line bg-paper/85 px-5 py-3 backdrop-blur
             dark:border-night-line dark:bg-night/85"
    >
      <a href="/dashboard"
         class="group flex items-baseline gap-2 no-underline"
         title="What this project is">
        <span class="text-[0.95rem] font-semibold tracking-tight
                     text-ink dark:text-night-fg">ResearchGPT</span>
        <span class="text-[0.68rem] uppercase tracking-[0.1em] text-ink-dim
                     transition group-hover:text-accent dark:text-night-dim">
          about
        </span>
      </a>

      <div v-if="result" class="flex flex-wrap items-center gap-x-5 gap-y-1
                                text-[0.8rem] text-ink-dim dark:text-night-dim">
        <span><b class="font-semibold text-supported">{{ result.counts.verified ?? 0 }}</b> kept</span>
        <span><b class="font-semibold text-unsupported">{{ result.counts.dropped ?? 0 }}</b> dropped</span>
        <span><b class="font-semibold text-ink dark:text-night-fg">{{ grounding }}</b> grounded</span>
        <span v-if="result.decisions.length" class="flex items-center gap-1">
          <span
            v-for="(d, i) in result.decisions" :key="i"
            class="rounded px-1.5 py-0.5 font-mono text-[0.68rem] font-semibold"
            :class="{
              'bg-write/15 text-write': d === 'WRITE',
              'bg-retrieve/15 text-retrieve': d === 'RETRIEVE',
              'bg-replan/15 text-replan': d === 'REPLAN',
            }"
          >{{ d }}</span>
        </span>
      </div>

      <span v-if="busy"
            class="ml-auto flex items-center gap-2 text-[0.8rem] text-accent">
        <span class="h-2 w-2 animate-pulse-ring rounded-full bg-accent"></span>
        running
      </span>
    </header>

    <div class="mx-auto grid max-w-[96rem] grid-cols-1 gap-4 p-4 lg:grid-cols-[21rem_1fr]">
      <div class="flex min-w-0 flex-col gap-4">
        <PanelRun
          :runs="runs" :busy="busy" :fixture-mode="fixtureMode" :error="error"
          @start="start" @open="open"
        />
        <PanelProgress :events="events" :running="busy" />
      </div>
      <div class="flex min-w-0 flex-col gap-4">
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
        <PanelScores v-if="onOptimizer" :run-id="runId" />
      </div>
    </div>
  </div>
</template>
