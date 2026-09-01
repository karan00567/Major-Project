<script setup>
// T-604 — one page, Composition API, no Pinia. TASKLIST: "one page, one run —
// a store is ceremony."
import { computed, onMounted, onUnmounted, ref } from 'vue'
import AppHeader from './components/AppHeader.vue'
import PanelRun from './components/PanelRun.vue'
import PanelOverview from './components/PanelOverview.vue'
import PanelProgress from './components/PanelProgress.vue'
import PanelEvidence from './components/PanelEvidence.vue'
import PanelDropped from './components/PanelDropped.vue'
import PanelSources from './components/PanelSources.vue'
import PanelScores from './components/PanelScores.vue'
import DashboardView from './components/DashboardView.vue'
import { digest } from './lib/runStats.js'
import { getResult, health, listRuns, postOverride, startReview, streamEvents } from './api.js'

const runs = ref([])
const runId = ref('')
const result = ref(null)
const events = ref([])
const busy = ref(false)
const error = ref('')
const fixtureMode = ref(false)
const apiOk = ref(true)
const overrides = ref({})
const overrideNotes = ref({})

// Three views, chosen by path. A path check rather than vue-router: T-604
// chose "one page, one run - a store is ceremony", and a router for three
// static routes is the same kind of ceremony. Vite serves index.html for
// unknown paths (appType 'spa'), so these all load this app; navigation
// between them is a full page load, so none of this needs to be reactive.
//
//   /dashboard  what the project is, for someone who has never seen it (T-613)
//   /optimizer  the run page plus the human scoring sheet (T-612)
//   /           the run page
const route = window.location.pathname.replace(/\/+$/, '') || '/'
const onDashboard = ref(route === '/dashboard')
const onOptimizer = ref(route === '/optimizer')

// Everything the trace says about this run, folded once and shared by the
// panels. Computed rather than accumulated so a re-opened run cannot inherit
// a stale total from the run before it.
const stats = computed(() => digest(events.value))

let closeStream = null

async function refreshRuns() {
  try {
    runs.value = await listRuns()
  } catch (e) {
    error.value = e.message
  }
}

/** Overrides arrive as a list and are consumed as two lookups; both are
 *  rebuilt from the same server reply so the note and the decision can never
 *  disagree about what was stored. */
function applyOverrides(list) {
  overrides.value = Object.fromEntries((list || []).map((o) => [o.claim_id, o.decision]))
  overrideNotes.value = Object.fromEntries(
    (list || []).filter((o) => o.note).map((o) => [o.claim_id, o.note]),
  )
}

async function open(id) {
  stopStream()
  runId.value = id
  events.value = []
  applyOverrides([])
  error.value = ''
  try {
    result.value = await getResult(id)
    // T-609: rehydrate what a human already decided, so a reload does not
    // silently discard judgements that ARE in the audit record.
    applyOverrides(result.value.human_overrides)
    busy.value = result.value.status === 'running'
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
async function override({ claim, decision, note }) {
  const prevDecisions = { ...overrides.value }
  const prevNotes = { ...overrideNotes.value }

  const nextDecisions = { ...overrides.value }
  const nextNotes = { ...overrideNotes.value }
  if (decision === null) delete nextDecisions[claim.claim_id]
  else nextDecisions[claim.claim_id] = decision
  if (note) nextNotes[claim.claim_id] = note
  else delete nextNotes[claim.claim_id]
  overrides.value = nextDecisions
  overrideNotes.value = nextNotes

  try {
    applyOverrides(await postOverride(runId.value, claim.claim_id, decision, note || null))
  } catch (e) {
    error.value = `Override not saved: ${e.message}`
    // Back to what the last successful read said, not to a blank slate: an
    // optimistic edit that fails must leave the earlier judgements standing.
    overrides.value = prevDecisions
    overrideNotes.value = prevNotes
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
    apiOk.value = false
    error.value = `API unreachable: ${e.message}. Start it with `
      + `python -m uvicorn researchgpt.api.app:app --port 8000`
  }
  refreshRuns()
})
onUnmounted(stopStream)
</script>

<template>
  <DashboardView v-if="onDashboard" />

  <div v-else class="min-h-screen">
    <AppHeader :route="route" :busy="busy" :fixture-mode="fixtureMode" :api-ok="apiOk" />

    <div class="mx-auto grid max-w-[100rem] grid-cols-1 items-start gap-4 p-4
                sm:px-6 lg:grid-cols-[22rem_1fr]">
      <!-- The rail: what to ask, and what has been asked before. Sticky, so a
           long review does not scroll the controls off the screen. -->
      <div class="flex min-w-0 flex-col gap-4 lg:sticky lg:top-16">
        <PanelRun
          :runs="runs" :busy="busy" :fixture-mode="fixtureMode" :error="error"
          :open-run-id="runId"
          @start="start" @open="open"
        />
      </div>

      <div class="flex min-w-0 flex-col gap-4">
        <PanelOverview :run-id="runId" :result="result" :digest="stats" :busy="busy" />
        <PanelProgress :digest="stats" :running="busy" />
        <PanelEvidence
          :review-markdown="result?.review_markdown || ''"
          :verified-claims="result?.verified_claims || []"
          :papers="result?.papers || []"
        />
        <!-- `[&>*]:min-w-0` is load-bearing, not cosmetic. A grid item defaults
             to `min-width: auto`, i.e. it refuses to shrink below its own
             min-content width — and these two panels contain nowrap `truncate`
             spans, whose min-content is the FULL untruncated string. At 375px
             that pushed the track to 466px and gave the whole page a horizontal
             scrollbar, while the panels in the flex column beside them were
             fine (a column flex container applies min-height, not min-width).
             Measured in a 390px frame, 2026-08-30. -->
        <div class="grid min-w-0 grid-cols-1 items-start gap-4 [&>*]:min-w-0 2xl:grid-cols-2">
          <PanelDropped
            :run-id="runId"
            :dropped-claims="result?.dropped_claims || []"
            :verified-count="result?.verified_claims?.length || 0"
            :artefacts="result?.artefacts || []"
            :overrides="overrides"
            :override-notes="overrideNotes"
            :threshold="stats.verify?.threshold ?? null"
            @override="override"
          />
          <PanelSources
            :papers="result?.papers || []"
            :verified-claims="result?.verified_claims || []"
            :dropped-claims="result?.dropped_claims || []"
            :extracted-ids="result?.extracted_paper_ids || []"
            :corpus-total="stats.totals.papers"
          />
        </div>
        <PanelScores v-if="onOptimizer" :run-id="runId" />
      </div>
    </div>

    <footer class="mx-auto max-w-[100rem] px-4 pb-8 pt-2 text-[0.74rem]
                   text-ink-faint sm:px-6 dark:text-night-faint">
      ResearchGPT · B.Tech major project, GRIET (DSC06) ·
      <a href="/dashboard" class="link">what this is</a>
    </footer>
  </div>
</template>
