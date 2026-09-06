<script setup>
// T-614 — every review this account has run.
//
// The sidebar holds five; this holds the rest. The server has already filtered
// to the signed-in user (GET /api/runs is scoped by owner), so there is no
// client-side ownership check here — and there must not be one, because a
// filter in the browser is a display convenience, never a boundary.
import { computed, ref } from 'vue'
import { ago, num, pct, truncate } from '../lib/format.js'

const props = defineProps({
  runs: { type: Array, default: () => [] },
  openRunId: { type: String, default: '' },
})
const emit = defineEmits(['open', 'new'])

const filter = ref('')

const visible = computed(() => {
  const q = filter.value.trim().toLowerCase()
  if (!q) return props.runs
  return props.runs.filter(
    (r) => (r.question || '').toLowerCase().includes(q)
      || (r.run_id || '').toLowerCase().includes(q),
  )
})
</script>

<template>
  <main class="mx-auto w-full max-w-4xl px-4 pb-16 pt-6 sm:px-6">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">Your reviews</h1>
        <p class="mt-1 text-[0.83rem] text-ink-dim dark:text-night-dim">
          {{ runs.length }} review<span v-if="runs.length !== 1">s</span> on this
          account.
        </p>
      </div>
      <button class="btn-primary !px-4 !py-2 !text-[0.84rem]" @click="emit('new')">
        + New review
      </button>
    </div>

    <input v-model="filter" type="search" placeholder="Filter by question…"
           class="mt-5 w-full rounded-xl border border-paper-line bg-paper-card
                  px-3.5 py-2.5 text-[0.88rem] outline-none transition
                  focus:border-accent dark:border-night-line dark:bg-night-card
                  dark:text-night-fg" />

    <p v-if="!runs.length"
       class="mt-10 rounded-xl border border-dashed border-paper-line px-5 py-10
              text-center text-[0.88rem] leading-relaxed text-ink-dim
              dark:border-night-line dark:text-night-dim">
      No reviews yet. Start one from the question box and it will appear here.
    </p>

    <p v-else-if="!visible.length"
       class="mt-8 text-center text-[0.86rem] text-ink-faint dark:text-night-faint">
      Nothing matches “{{ filter }}”.
    </p>

    <ul v-else class="mt-4 flex flex-col gap-2">
      <li v-for="r in visible" :key="r.run_id">
        <button
          class="w-full rounded-xl border border-paper-line bg-paper-card p-4
                 text-left transition hover:border-accent
                 dark:border-night-line dark:bg-night-card"
          :class="r.run_id === openRunId ? 'border-accent' : ''"
          @click="emit('open', r.run_id)">
          <div class="flex items-start justify-between gap-3">
            <span class="text-[0.9rem] font-medium leading-snug">
              {{ truncate(r.question || r.run_id, 110) }}
            </span>
            <span v-if="r.status === 'running'"
                  class="pill-soft shrink-0 text-accent">running</span>
          </div>

          <div class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1
                      text-[0.76rem] text-ink-faint dark:text-night-faint">
            <span>{{ ago(r.started) }}</span>
            <span v-if="r.papers != null">{{ num(r.papers) }} papers</span>
            <span v-if="r.verified_claims != null">
              {{ r.verified_claims }} kept
              <template v-if="r.dropped_claims != null">
                · {{ r.dropped_claims }} dropped
              </template>
            </span>
            <span v-if="r.grounding_score != null">
              grounding {{ pct(r.grounding_score) }}
            </span>
            <span class="tag-mono">{{ r.run_id }}</span>
          </div>
        </button>
      </li>
    </ul>
  </main>
</template>
