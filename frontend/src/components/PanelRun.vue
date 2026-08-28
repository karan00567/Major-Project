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
// Defaults low on purpose: a 25-paper run is minutes long against a metered
// free tier, so the live demo is meant to be small (T-610).
const maxPapers = ref(10)
</script>

<template>
  <section class="panel">
    <header><h2>1 · Run</h2></header>

    <label class="field">
      <span>Research question</span>
      <textarea v-model="question" rows="3" :disabled="busy" />
    </label>

    <div class="row">
      <label class="field small">
        <span>max_papers</span>
        <input v-model.number="maxPapers" type="number" min="1" max="60" :disabled="busy" />
      </label>
      <button
        class="primary"
        :disabled="busy || fixtureMode || question.trim().length < 10"
        @click="emit('start', { question, maxPapers })"
      >
        {{ busy ? 'Running…' : 'Run review' }}
      </button>
    </div>

    <p v-if="fixtureMode" class="note">
      <strong>Fixture mode.</strong> Live runs are disabled; open a recorded run below.
      Unset <code>RESEARCHGPT_FIXTURE</code> to run for real.
    </p>
    <p v-if="error" class="error">{{ error }}</p>

    <h3>Previous runs</h3>
    <ul class="runs">
      <li v-for="r in runs" :key="r.run_id">
        <button class="link" @click="emit('open', r.run_id)">{{ r.run_id }}</button>
        <span class="meta">
          <span :class="['dot', r.status]" />{{ r.status }}
          <template v-if="r.papers"> · {{ r.papers }} papers</template>
          <template v-if="r.verified_claims != null">
            · {{ r.verified_claims }} kept / {{ r.dropped_claims }} dropped
          </template>
        </span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.field { display: block; margin-bottom: .6rem; }
.field span { display: block; font-size: .78rem; text-transform: uppercase;
              letter-spacing: .06em; color: var(--muted); margin-bottom: .25rem; }
textarea, input { width: 100%; padding: .5rem .6rem; border: 1px solid var(--line);
                  border-radius: 6px; background: var(--bg); color: inherit;
                  font: inherit; }
.row { display: flex; gap: .8rem; align-items: flex-end; }
.field.small { width: 8rem; margin-bottom: 0; }
.primary { padding: .55rem 1.1rem; border: 0; border-radius: 6px; cursor: pointer;
           background: #2f6fed; color: #fff; font-weight: 600; }
.primary:disabled { opacity: .45; cursor: not-allowed; }
h3 { margin: 1.2rem 0 .4rem; font-size: .78rem; text-transform: uppercase;
     letter-spacing: .06em; color: var(--muted); }
.runs { list-style: none; margin: 0; padding: 0; max-height: 30vh; overflow-y: auto; }
.runs li { padding: .3rem 0; border-bottom: 1px solid var(--line); font-size: .85rem; }
.link { background: none; border: 0; padding: 0; color: #2f6fed; cursor: pointer;
        font: inherit; }
.meta { display: block; color: var(--muted); font-size: .78rem; }
.dot { display: inline-block; width: .5rem; height: .5rem; border-radius: 50%;
       margin-right: .35rem; background: var(--muted); }
.dot.complete { background: #2f9e5f; } .dot.running { background: #c98a2e; }
.dot.failed { background: #d9534f; }
.note { font-size: .82rem; background: #c98a2e14; border: 1px solid #c98a2e55;
        border-radius: 6px; padding: .5rem .6rem; }
.error { color: #d9534f; font-size: .85rem; }
</style>
