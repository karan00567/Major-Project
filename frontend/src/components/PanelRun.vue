<script setup>
// T-605 — Panel 1. Query, max_papers, run. Also the run picker, because the
// demo path (T-610) replays a pre-baked run rather than running live.
import { ref } from 'vue'

defineProps({
  runs: { type: Array, default: () => [] },
  busy: Boolean,
  fixtureMode: Boolean,
  error: { type: String, default: '' },
})
const emit = defineEmits(['start', 'open'])

const question = ref(
  'How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?',
)
// T-611. A fixed list, not a free number box. These are the sizes whose cost
// is actually known, and the runtime is paced by the provider's tokens per
// minute rather than by CPU - measured 2026-08-29, extraction admits roughly
// ONE PAPER PER MINUTE on Groq's free tier. So the size chosen here is very
// nearly the run's length in minutes, and 100 exceeds a 200,000-token daily
// budget on its own. A typed number invites a two-hour run nobody meant to
// start; a list can carry that warning next to each option.
//
// Kept in sync with the API bound by tests/test_phase6_acceptance.py (T-611):
// max(PAPER_OPTIONS) must equal ReviewRequest's `le`.
const PAPER_OPTIONS = [5, 10, 15, 25, 50, 100]

// Rough end-to-end minutes, dominated by extraction at ~1 paper/min plus a
// fixed ~20 min of retrieval and ranking at the default max_per_source.
const RUNTIME_HINT = {
  5: '~25 min', 10: '~30 min', 15: '~35 min',
  25: '~45 min', 50: '~70 min', 100: '~2 h',
}

// Defaults low on purpose: a 25-paper run is minutes long against a metered
// free tier, so the live demo is meant to be small (T-610).
const maxPapers = ref(10)
</script>

<template>
  <section class="panel">
    <header class="mb-3 flex items-baseline justify-between">
      <h2 class="panel-title">1 · Run</h2>
      <a href="/optimizer"
         class="text-[0.68rem] uppercase tracking-[0.08em] text-ink-dim
                no-underline transition hover:text-accent dark:text-night-dim">
        score a run
      </a>
    </header>

    <label class="block">
      <span class="field-label">Research question</span>
      <textarea v-model="question" rows="3" :disabled="busy"
                class="control resize-y leading-relaxed" />
    </label>

    <div class="mt-3 flex items-end gap-3">
      <label class="block min-w-0 flex-1">
        <span class="field-label">max_papers</span>
        <select v-model.number="maxPapers" :disabled="busy" class="control">
          <option v-for="n in PAPER_OPTIONS" :key="n" :value="n">
            {{ n }} — {{ RUNTIME_HINT[n] }}
          </option>
        </select>
      </label>
      <button
        class="btn-primary shrink-0"
        :disabled="busy || fixtureMode || question.trim().length < 10"
        @click="emit('start', { question, maxPapers })"
      >
        {{ busy ? 'Running…' : 'Run review' }}
      </button>
    </div>

    <p v-if="maxPapers >= 50"
       class="mt-3 rounded-lg border-l-[3px] border-replan bg-replan/10 px-3 py-2
              text-[0.8rem] leading-relaxed text-ink-dim dark:text-night-dim">
      <strong class="text-ink dark:text-night-fg">
        {{ maxPapers }} papers is {{ RUNTIME_HINT[maxPapers] }}.
      </strong>
      Extraction is one LLM call per paper, paced by the free tier's 8,000
      tokens/minute — bounded by the token budget, not your CPU.
    </p>

    <p v-if="fixtureMode"
       class="mt-3 rounded-lg bg-accent-soft px-3 py-2 text-[0.8rem]
              text-ink-dim dark:text-night-dim">
      <strong class="text-ink dark:text-night-fg">Fixture mode.</strong>
      Live runs are disabled; open a recorded run below. Unset
      <code class="font-mono text-[0.9em]">RESEARCHGPT_FIXTURE</code> to run for real.
    </p>
    <p v-if="error" class="mt-3 text-[0.82rem] text-unsupported">{{ error }}</p>

    <h3 class="panel-title mb-2 mt-5">Previous runs</h3>
    <ul class="scroll-soft -mr-1 max-h-64 space-y-1 overflow-y-auto pr-1">
      <li v-for="r in runs" :key="r.run_id">
        <button
          class="w-full rounded-lg border border-transparent px-2 py-1.5 text-left
                 transition hover:border-paper-line hover:bg-paper
                 dark:hover:border-night-line dark:hover:bg-night"
          @click="emit('open', r.run_id)"
        >
          <span class="block truncate font-mono text-[0.78rem] text-accent">
            {{ r.run_id }}
          </span>
          <span class="mt-0.5 flex flex-wrap items-center gap-x-2 text-[0.72rem]
                       text-ink-dim dark:text-night-dim">
            <span class="flex items-center gap-1">
              <span class="h-1.5 w-1.5 rounded-full"
                    :class="{
                      'bg-supported': r.status === 'complete',
                      'bg-replan animate-pulse-ring': r.status === 'running',
                      'bg-unsupported': r.status === 'failed',
                    }" />
              {{ r.status }}
            </span>
            <template v-if="r.papers">· {{ r.papers }} papers</template>
            <template v-if="r.verified_claims != null">
              · {{ r.verified_claims }} kept / {{ r.dropped_claims }} dropped
            </template>
          </span>
        </button>
      </li>
    </ul>
  </section>
</template>
