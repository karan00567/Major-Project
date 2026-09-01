<script setup>
// T-605 — Panel 1. Query, max_papers, run. Also the run picker, because the
// demo path (T-610) replays a pre-baked run rather than running live.
import { computed, ref } from 'vue'
import { ago, num, pct, stamp, truncate } from '../lib/format.js'

const props = defineProps({
  runs: { type: Array, default: () => [] },
  busy: Boolean,
  fixtureMode: Boolean,
  error: { type: String, default: '' },
  openRunId: { type: String, default: '' },
})
const emit = defineEmits(['start', 'open'])

const question = ref(
  'How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?',
)

// Three questions the corpus can actually answer, so a reader with no question
// of their own has somewhere to start. Picking one only fills the box — it
// never starts a run, for the same reason the dashboard's CTA does not: a
// 40-minute job against a metered daily budget must be deliberate.
const EXAMPLES = [
  'How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?',
  'What evaluation metrics are used for citation faithfulness in generated scientific text?',
  'How do cross-encoder rerankers compare with dense retrieval for scientific literature search?',
]

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

const filter = ref('')

const tooShort = computed(() => question.value.trim().length < 10)

const visibleRuns = computed(() => {
  const q = filter.value.trim().toLowerCase()
  if (!q) return props.runs
  return props.runs.filter((r) =>
    `${r.run_id} ${r.question || ''}`.toLowerCase().includes(q))
})

const DOT = {
  complete: 'bg-supported',
  running: 'bg-replan animate-pulse-ring',
  failed: 'bg-unsupported',
}
</script>

<template>
  <section class="panel panel-pad">
    <h2 class="panel-title mb-3"><span class="panel-index">1</span> Run</h2>

    <label class="block">
      <span class="field-label">Research question</span>
      <textarea v-model="question" rows="3" :disabled="busy"
                class="control resize-y leading-relaxed" />
    </label>

    <div class="mt-1.5 flex flex-wrap items-center gap-1.5">
      <span class="text-[0.7rem] text-ink-faint dark:text-night-faint">try:</span>
      <button v-for="(ex, i) in EXAMPLES" :key="i" type="button"
              class="btn-quiet max-w-full truncate !text-[0.72rem]"
              :disabled="busy" :title="ex" @click="question = ex">
        {{ truncate(ex, 38) }}
      </button>
    </div>

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
        :disabled="busy || fixtureMode || tooShort"
        :title="fixtureMode
          ? 'Fixture mode refuses live runs'
          : tooShort ? 'The question needs at least 10 characters' : ''"
        @click="emit('start', { question, maxPapers })"
      >
        {{ busy ? 'Running…' : 'Run review' }}
      </button>
    </div>
    <p v-if="tooShort && !busy"
       class="mt-1.5 text-[0.74rem] text-ink-dim dark:text-night-dim">
      The API requires at least 10 characters.
    </p>

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
      <code class="tag-mono">RESEARCHGPT_FIXTURE</code> to run for real.
    </p>
    <p v-if="error"
       class="mt-3 rounded-lg border-l-[3px] border-unsupported bg-unsupported/10
              px-3 py-2 text-[0.82rem] text-unsupported dark:text-unsupported-lite">
      {{ error }}
    </p>

    <div class="panel-head mb-2 mt-5">
      <h3 class="panel-title">Previous runs</h3>
      <span class="text-[0.7rem] text-ink-dim dark:text-night-dim">
        {{ visibleRuns.length }} of {{ runs.length }}
      </span>
    </div>
    <input v-if="runs.length > 6" v-model="filter" type="search"
           placeholder="filter runs"
           class="control mb-2 !py-1.5 text-[0.8rem]" aria-label="Filter runs" />

    <p v-if="!runs.length" class="panel-note">
      No runs on disk yet. Artefacts land in
      <code class="tag-mono">outputs/runs/</code>, and every directory there
      shows up here — the filesystem is the record, not a database.
    </p>

    <ul class="scroll-soft -mr-1 max-h-72 space-y-1 overflow-y-auto pr-1">
      <li v-for="r in visibleRuns" :key="r.run_id">
        <button
          class="w-full rounded-lg border px-2.5 py-2 text-left transition"
          :class="r.run_id === openRunId
            ? 'border-accent bg-accent-soft'
            : 'border-transparent hover:border-paper-line hover:bg-paper dark:hover:border-night-line dark:hover:bg-night'"
          :aria-current="r.run_id === openRunId ? 'true' : undefined"
          @click="emit('open', r.run_id)"
        >
          <!-- The question first. A column of run ids is unreadable: they are
               all the same shape, and the only thing that distinguishes one
               run from another is what it was asked. A run whose trace never
               recorded one falls back to its id as the heading rather than to
               a row of identical "(not recorded)" placeholders. -->
          <span class="block truncate text-[0.8rem] font-medium
                       text-ink dark:text-night-fg"
                :class="r.question ? '' : 'font-mono !text-[0.76rem]'">
            {{ r.question || r.run_id }}
          </span>
          <span class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5
                       text-[0.7rem] text-ink-dim dark:text-night-dim">
            <span class="flex items-center gap-1">
              <span class="h-1.5 w-1.5 rounded-full" :class="DOT[r.status]" />
              {{ r.status }}
            </span>
            <template v-if="r.started">
              · <span :title="stamp(r.started)">{{ ago(r.started) }}</span>
            </template>
            <template v-if="r.papers">· {{ num(r.papers) }} papers</template>
            <template v-if="r.verified_claims != null">
              · {{ r.verified_claims }} kept / {{ r.dropped_claims }} dropped
            </template>
            <template v-if="r.grounding_score != null">
              · {{ pct(r.grounding_score, 0) }} grounded
            </template>
          </span>
          <span v-if="r.question"
                class="mt-0.5 block truncate font-mono text-[0.68rem]
                       text-ink-faint dark:text-night-faint">{{ r.run_id }}</span>
        </button>
      </li>
    </ul>
  </section>
</template>
