<script setup>
// T-614 — the rail: new chat, the five most recent, and the account.
//
// Five is the brief, and it is also the right number: the sidebar is for
// "the thing I was just doing", not for browsing. Everything older lives on
// the full history view, one click away, so the rail never scrolls.
import { computed } from 'vue'
import { ago, truncate } from '../lib/format.js'
import { initials, shortName, user } from '../lib/auth.js'

const props = defineProps({
  runs: { type: Array, default: () => [] },
  openRunId: { type: String, default: '' },
  open: Boolean, // mobile drawer
})
const emit = defineEmits(['new', 'open', 'profile', 'signout', 'history', 'close'])

const RECENT_LIMIT = 5
const recent = computed(() => props.runs.slice(0, RECENT_LIMIT))
const hasMore = computed(() => props.runs.length > RECENT_LIMIT)

/** A run's question is the only human-readable handle it has; the run_id is a
 *  timestamp and a hash, which tells a reader nothing about what they asked. */
function label(run) {
  return truncate(run.question || run.run_id, 42)
}
</script>

<template>
  <!-- Scrim: mobile only, closes the drawer. -->
  <div v-if="open" class="fixed inset-0 z-30 bg-black/40 lg:hidden"
       @click="emit('close')" />

  <aside
    class="fixed inset-y-0 left-0 z-40 flex w-[17rem] flex-col border-r
           border-paper-line bg-paper-sunk transition-transform
           dark:border-night-line dark:bg-night-sunk lg:translate-x-0"
    :class="open ? 'translate-x-0' : '-translate-x-full'">

    <!-- brand -->
    <div class="flex items-center justify-between px-4 pb-3 pt-4">
      <a href="/" class="text-[0.95rem] font-semibold tracking-tight">
        ResearchGPT
      </a>
      <button class="rounded-lg p-1.5 text-ink-dim hover:bg-paper-line lg:hidden
                     dark:text-night-dim dark:hover:bg-night-line"
              aria-label="Close menu" @click="emit('close')">✕</button>
    </div>

    <div class="px-3">
      <button class="flex w-full items-center gap-2 rounded-xl border
                     border-paper-line bg-paper-card px-3 py-2.5 text-[0.86rem]
                     font-medium transition hover:border-accent hover:text-accent
                     dark:border-night-line dark:bg-night-card"
              @click="emit('new')">
        <span class="text-[1.05rem] leading-none">+</span> New review
      </button>
    </div>

    <!-- recent -->
    <div class="mt-6 min-h-0 flex-1 overflow-y-auto px-3">
      <p class="px-2 pb-2 text-[0.72rem] font-semibold uppercase tracking-wide
                text-ink-faint dark:text-night-faint">
        Recent
      </p>

      <p v-if="!recent.length"
         class="px-2 py-3 text-[0.8rem] leading-relaxed text-ink-faint
                dark:text-night-faint">
        Nothing yet. Ask a question below and it will appear here.
      </p>

      <button v-for="r in recent" :key="r.run_id"
              class="mb-0.5 block w-full rounded-lg px-2 py-2 text-left transition
                     hover:bg-paper-line dark:hover:bg-night-line"
              :class="r.run_id === openRunId
                ? 'bg-paper-line dark:bg-night-line' : ''"
              @click="emit('open', r.run_id)">
        <span class="block truncate text-[0.83rem] leading-snug">{{ label(r) }}</span>
        <span class="mt-0.5 block text-[0.72rem] text-ink-faint dark:text-night-faint">
          {{ ago(r.started) }}
          <span v-if="r.status === 'running'" class="text-accent">· running</span>
        </span>
      </button>

      <button v-if="hasMore"
              class="mt-1 w-full rounded-lg px-2 py-2 text-left text-[0.79rem]
                     text-ink-dim transition hover:bg-paper-line
                     dark:text-night-dim dark:hover:bg-night-line"
              @click="emit('history')">
        All reviews ({{ runs.length }}) →
      </button>
    </div>

    <!-- account -->
    <div class="border-t border-paper-line p-3 dark:border-night-line">
      <button class="flex w-full items-center gap-2.5 rounded-xl px-2 py-2
                     text-left transition hover:bg-paper-line
                     dark:hover:bg-night-line"
              @click="emit('profile')">
        <span class="grid h-8 w-8 shrink-0 place-items-center rounded-full
                     bg-accent text-[0.72rem] font-semibold text-white">
          {{ initials(user) }}
        </span>
        <span class="min-w-0 flex-1">
          <span class="flex items-center gap-1.5">
            <span class="truncate text-[0.83rem] font-medium">
              {{ shortName(user) }}
            </span>
            <span v-if="user?.is_admin"
                  class="shrink-0 rounded px-1.5 py-px text-[0.62rem] font-semibold
                         uppercase tracking-wide text-accent ring-1 ring-accent/40">
              admin
            </span>
          </span>
          <span class="block truncate text-[0.72rem] text-ink-faint
                       dark:text-night-faint">Profile &amp; settings</span>
        </span>
      </button>
      <button class="mt-1 w-full rounded-lg px-2 py-1.5 text-left text-[0.79rem]
                     text-ink-dim transition hover:bg-paper-line
                     dark:text-night-dim dark:hover:bg-night-line"
              @click="emit('signout')">
        Sign out
      </button>
    </div>
  </aside>
</template>
