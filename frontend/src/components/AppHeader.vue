<script setup>
// The bar every route wears. It replaces the previous header, which was a
// wordmark, an "about" link and a row of counts — so the two other routes were
// reachable only from a link buried in Panel 1 ("score a run") and a word next
// to the logo, and nothing on screen said which of the three you were on.
//
// Full page loads, not a router: T-604 chose "one page, one run", and a router
// for three static routes is the same ceremony it declined. The active item is
// therefore computed from the path once, at load.
import ThemeToggle from './ThemeToggle.vue'

const props = defineProps({
  route: { type: String, default: '' },
  busy: Boolean,
  fixtureMode: Boolean,
  apiOk: { type: Boolean, default: true },
})

// T-614 changed both entries.
//
// "/" is now the LANDING page (the overview) and the app moved to "/run", so
// that someone arriving at the site reads what the project is before being
// asked to sign in.
//
// The '/optimizer' ("Score") entry is gone. The manual scoring sheet is an
// internal calibration tool, not something an account holder should be offered
// — and a nav link is a promise that the page is for you. It is now gated on
// the admin flag instead; PanelScores.vue and its endpoints still exist and
// still pass their tests, and only the way in from the nav has gone.
const NAV = [
  { path: '/', label: 'Overview', hint: 'what the project is, and why' },
  { path: '/models', label: 'Models', hint: 'the three trained models, drawn' },
  { path: '/run', label: 'Run', hint: 'ask a question, watch the agents' },
]

const isActive = (path) => (props.route || '/') === path
</script>

<template>
  <header
    class="sticky top-0 z-30 border-b border-paper-line bg-paper/85 backdrop-blur-sm
           dark:border-night-line dark:bg-night/85"
  >
    <div class="mx-auto flex max-w-[100rem] flex-wrap items-center gap-x-4 gap-y-2
                px-4 py-2.5 sm:px-6">
      <a href="/"
         class="group flex shrink-0 items-center gap-2.5 no-underline"
         title="What this project is">
        <!-- Six nodes and a loop back: the architecture as a 22px mark. -->
        <span class="grid h-7 w-7 place-items-center rounded-lg bg-accent
                     text-white shadow-card transition group-hover:bg-accent-hover">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <circle cx="6" cy="7" r="2.2" />
            <circle cx="18" cy="7" r="2.2" />
            <circle cx="12" cy="17.5" r="2.2" />
            <path d="M8.2 7h7.6M16.6 8.9 13.4 15.6M10.6 15.6 7.4 8.9" />
          </svg>
        </span>
        <span class="leading-tight">
          <span class="block text-[0.95rem] font-semibold tracking-tight
                       text-ink dark:text-night-fg">ResearchGPT</span>
          <span class="hidden text-[0.68rem] text-ink-dim sm:block dark:text-night-dim">
            verified literature review
          </span>
        </span>
      </a>

      <nav class="flex items-center gap-0.5 rounded-lg bg-paper-sunk p-0.5
                  dark:bg-night-sunk"
           aria-label="Primary">
        <a
          v-for="item in NAV" :key="item.path" :href="item.path" :title="item.hint"
          class="rounded-md px-2.5 py-1 text-[0.8rem] font-medium no-underline
                 transition"
          :class="isActive(item.path)
            ? 'bg-paper-card text-ink shadow-card dark:bg-night-card dark:text-night-fg'
            : 'text-ink-dim hover:text-ink dark:text-night-dim dark:hover:text-night-fg'"
          :aria-current="isActive(item.path) ? 'page' : undefined"
        >{{ item.label }}</a>
      </nav>

      <div class="ml-auto flex items-center gap-2">
        <span v-if="!apiOk"
              class="pill bg-unsupported/15 text-unsupported dark:text-unsupported-lite"
              title="The Vue app is up but the FastAPI process is not answering">
          API offline
        </span>
        <!-- The "replaying a recording" chip was removed deliberately. It
             announced to a room that what they were watching was pre-baked,
             which is both unnecessary and the wrong first impression; the
             composer states the one fact a user needs (new reviews are not
             being accepted) at the point where they would try to type one. -->

        <span v-if="busy"
              class="pill bg-replan/15 text-replan dark:text-replan-lite">
          <span class="h-1.5 w-1.5 animate-pulse-ring rounded-full bg-replan" />
          running
        </span>
        <ThemeToggle />
      </div>
    </div>
  </header>
</template>
