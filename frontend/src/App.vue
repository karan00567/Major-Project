<script setup>
// T-604, rebuilt for T-614 — a chat-shaped shell around the same panels.
//
// The layout is now sidebar + scrolling transcript + a composer pinned to the
// bottom, which is what people already know how to use. What did NOT change is
// what the panels show: the run's evidence, its dropped claims and its sources
// are the project's argument, so they stayed exactly as they were and only
// their frame moved.
//
// Still no router and still no Pinia. Views are chosen by pathname (as before)
// and the only shared state is the session, which lives in lib/auth.js.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import AppSidebar from './components/AppSidebar.vue'
import AuthView from './components/AuthView.vue'
import Composer from './components/Composer.vue'
import ProfileModal from './components/ProfileModal.vue'
import PanelOverview from './components/PanelOverview.vue'
import PanelProgress from './components/PanelProgress.vue'
import PanelEvidence from './components/PanelEvidence.vue'
import PanelDropped from './components/PanelDropped.vue'
import PanelSources from './components/PanelSources.vue'
import PanelScores from './components/PanelScores.vue'
import DashboardView from './components/DashboardView.vue'
import ModelsView from './components/ModelsView.vue'
import HistoryView from './components/HistoryView.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import { digest } from './lib/runStats.js'
import { clearSession, isAuthed, user } from './lib/auth.js'
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

const authed = ref(isAuthed())
const showProfile = ref(false)
const sidebarOpen = ref(false)

// T-614 — the routes moved. "/" is now the LANDING page: the dashboard, which
// is public, because it is the "what is this project" page an examiner may open
// without an account, and making people sign in before they can read what the
// project *is* gets the order backwards. The app itself moved to "/run".
//
//   /            the landing page (public) — CTA is "Log in" or "Run a review"
//   /dashboard   the same page, kept so existing links and the footer still work
//   /models      the three trained models and their architectures (public)
//   /run         the question box and the results (needs a session)
//
// Still a pathname check rather than vue-router: four static routes and a full
// page load between them is not worth a router, and the SPA fallback in Vite
// already serves index.html for /run.
//
// /models is public for the same reason the landing page is: it explains what
// was built, and asking someone to sign in before they may read that gets the
// order backwards. It calls no endpoint, so it needs no session either.
const route = window.location.pathname.replace(/\/+$/, '') || '/'
const onDashboard = ref(route === '/' || route === '/dashboard')
const onModels = ref(route === '/models')
const showHistory = ref(false)

const stats = computed(() => digest(events.value))
// T-614: the manual scoring sheet is an administrator tool. This only decides
// what to RENDER - every /scores route re-checks the flag server side.
const isAdmin = computed(() => Boolean(user.value?.is_admin))
const hasRun = computed(() => Boolean(runId.value && result.value))

let closeStream = null

async function refreshRuns() {
  try {
    runs.value = await listRuns()
  } catch (e) {
    // A 401 here means the session expired; api.js has already cleared it, so
    // reflect that rather than showing a scary error over a blank app.
    if (!isAuthed()) { authed.value = false; return }
    error.value = e.message
  }
}

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
  showHistory.value = false
  sidebarOpen.value = false
  try {
    result.value = await getResult(id)
    applyOverrides(result.value.human_overrides)
    busy.value = result.value.status === 'running'
  } catch (e) {
    error.value = e.message
    return
  }
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

function newReview() {
  stopStream()
  runId.value = ''
  result.value = null
  events.value = []
  applyOverrides([])
  error.value = ''
  showHistory.value = false
  sidebarOpen.value = false
}

async function start({ question, maxPapers }) {
  error.value = ''
  busy.value = true
  try {
    const accepted = await startReview(question, maxPapers)
    await open(accepted.run_id)
    refreshRuns()
  } catch (e) {
    error.value = e.message
    busy.value = false
  }
}

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
    overrides.value = prevDecisions
    overrideNotes.value = prevNotes
  }
}

function stopStream() {
  if (closeStream) { closeStream(); closeStream = null }
}

function signOut() {
  stopStream()
  clearSession()
  authed.value = false
  runs.value = []
  newReview()
}

async function boot() {
  try {
    const h = await health()
    fixtureMode.value = h.fixture_mode
    if (h.fixture_mode && h.fixture_available) await open(h.fixture_run_id)
  } catch (e) {
    apiOk.value = false
    error.value = `API unreachable: ${e.message}. Start it with `
      + `py -3.13 -m uvicorn researchgpt.api.app:app --port 8000`
  }
  refreshRuns()
}

async function onAuthed() {
  authed.value = true
  await boot()
}

// The landing page is static and public: it reads nothing from the API, so it
// must not call it. Booting there would fire /api/runs without a token, take a
// 401, and log a scary error behind a page that is working perfectly.
onMounted(() => { if (!onDashboard.value && !onModels.value && authed.value) boot() })
onUnmounted(stopStream)
</script>

<template>
  <DashboardView v-if="onDashboard" />

  <ModelsView v-else-if="onModels" />

  <AuthView v-else-if="!authed" @authed="onAuthed" />

  <div v-else class="min-h-screen lg:pl-[17rem]">
    <AppSidebar
      :runs="runs" :open-run-id="runId" :open="sidebarOpen"
      @new="newReview" @open="open" @profile="showProfile = true"
      @signout="signOut" @history="showHistory = true; sidebarOpen = false"
      @close="sidebarOpen = false"
    />

    <!-- Top bar: only the things the sidebar cannot hold. -->
    <header class="sticky top-0 z-20 flex items-center gap-3 border-b
                   border-paper-line bg-paper/85 px-4 py-2.5 backdrop-blur
                   dark:border-night-line dark:bg-night/85">
      <button class="rounded-lg p-1.5 text-ink-dim hover:bg-paper-sunk lg:hidden
                     dark:text-night-dim dark:hover:bg-night-sunk"
              aria-label="Open menu" @click="sidebarOpen = true">☰</button>
      <span class="min-w-0 flex-1 truncate text-[0.85rem] text-ink-dim
                   dark:text-night-dim">
        {{ result?.question || (showHistory ? 'All reviews' : 'New review') }}
      </span>
      <!-- No "demo mode" badge. The composer already says, in one plain
           sentence, that new reviews are not being accepted; a chip in the
           title bar saying the app is in a demo adds nothing a viewer needs and
           frames everything below it as a rehearsal. -->
      <span v-if="!apiOk" class="pill-soft shrink-0 text-rose-600">API offline</span>
      <ThemeToggle />
    </header>

    <HistoryView
      v-if="showHistory" :runs="runs" :open-run-id="runId"
      @open="open" @new="newReview"
    />

    <!-- The transcript. Scrolls under a composer that stays put. -->
    <div v-else class="flex min-h-[calc(100vh-3.25rem)] flex-col">
      <main class="mx-auto w-full max-w-5xl flex-1 px-4 pb-2 pt-5 sm:px-6">
        <!-- Empty state: no run open yet. -->
        <div v-if="!hasRun && !busy" class="grid h-full place-items-center py-16">
          <div class="max-w-md text-center">
            <h1 class="text-2xl font-semibold tracking-tight">
              What would you like reviewed?
            </h1>
            <p class="mt-3 text-[0.9rem] leading-relaxed text-ink-dim
                      dark:text-night-dim">
              Ask a research question below. Six agents plan, search, rank,
              extract and draft — then every claim written is checked against the
              evidence retrieved, and whatever cannot be grounded is dropped.
            </p>
            <p v-if="error" class="mt-4 text-[0.82rem] text-rose-600">{{ error }}</p>
          </div>
        </div>

        <div v-else class="flex flex-col gap-4">
          <PanelOverview :run-id="runId" :result="result" :digest="stats" :busy="busy" />
          <PanelProgress :digest="stats" :running="busy" />
          <PanelEvidence
            :review-markdown="result?.review_markdown || ''"
            :verified-claims="result?.verified_claims || []"
            :papers="result?.papers || []"
          />
          <!-- `[&>*]:min-w-0` is load-bearing: a grid item defaults to
               min-width:auto and these panels hold nowrap truncate spans, whose
               min-content is the FULL string — which gave the page a horizontal
               scrollbar at 375px before this was added. -->
          <div class="grid min-w-0 grid-cols-1 items-start gap-4 [&>*]:min-w-0
                      2xl:grid-cols-2">
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
          <PanelScores v-if="isAdmin && hasRun" :run-id="runId" />
        </div>
      </main>

      <Composer
        :busy="busy" :fixture-mode="fixtureMode" :error="error"
        @start="start"
      />
    </div>

    <ProfileModal v-if="showProfile" @close="showProfile = false" />
  </div>
</template>
