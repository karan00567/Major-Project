<script setup>
// T-612 — Panel 5. A human scores the papers the Extractor read, and the
// review it produced, 1 (worst) to 5 (best).
//
// Two separate verdicts on purpose: "was the retrieval any good?" and "was the
// writing any good?" are different questions, and the automated metrics cannot
// currently tell them apart — corpus recall has been 0.000 in every run while
// the grounding score read as high as 1.000. A single blended number would
// destroy exactly the distinction this panel exists to capture.
import { ref, watch, computed } from 'vue'
import { getScoreSheet, postScores } from '../api.js'

const props = defineProps({
  runId: { type: String, default: '' },
})

const SCORES = [1, 2, 3, 4, 5]

const sheet = ref(null)
const paperScores = ref({})     // paper_id -> 1..5
const paperNotes = ref({})      // paper_id -> string
const artefactScore = ref(null)
const artefactNote = ref('')
const busy = ref(false)
const error = ref('')
const saved = ref('')

const dirty = computed(() =>
  Object.keys(paperScores.value).length > 0 || artefactScore.value != null,
)

async function load(id) {
  sheet.value = null
  error.value = ''
  saved.value = ''
  paperScores.value = {}
  paperNotes.value = {}
  artefactScore.value = null
  artefactNote.value = ''
  if (!id) return
  try {
    const data = await getScoreSheet(id)
    sheet.value = data
    // Rehydrate what was already scored, so a reload does not look like a
    // blank sheet and invite the reviewer to do the work twice.
    for (const p of data.papers) {
      if (p.score != null) paperScores.value[p.paper_id] = p.score
      if (p.note) paperNotes.value[p.paper_id] = p.note
    }
    if (data.artefact_score) {
      artefactScore.value = data.artefact_score.score
      artefactNote.value = data.artefact_score.note || ''
    }
  } catch (e) {
    error.value = e.message
  }
}

watch(() => props.runId, load, { immediate: true })

async function submit() {
  if (!props.runId || !dirty.value) return
  busy.value = true
  error.value = ''
  saved.value = ''
  try {
    const payload = {
      papers: Object.entries(paperScores.value).map(([paper_id, score]) => ({
        paper_id,
        score,
        note: paperNotes.value[paper_id] || null,
      })),
      artefact: artefactScore.value != null
        ? { score: artefactScore.value, note: artefactNote.value || null }
        : null,
    }
    const data = await postScores(props.runId, payload)
    sheet.value = data
    // Say what actually happened. `trace` means the score is safe on disk but
    // Postgres did not take it — claiming "saved to the database" would be a
    // lie the reviewer cannot check.
    saved.value = data.persisted === 'trace+db'
      ? 'Saved to the trace and mirrored to the database.'
      : 'Saved to the run trace. Not mirrored — the database is unavailable.'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="panel">
    <header class="mb-3 flex items-baseline justify-between gap-2">
      <h2 class="panel-title">5 · Score</h2>
      <span v-if="sheet && sheet.papers.length"
            class="text-[0.7rem] text-ink-dim dark:text-night-dim">
        1 worst · 5 best
      </span>
    </header>

    <p v-if="!runId" class="text-[0.86rem] text-ink-dim dark:text-night-dim">
      Open a run to score it.
    </p>
    <p v-else-if="!sheet && !error"
       class="text-[0.86rem] text-ink-dim dark:text-night-dim">Loading…</p>
    <p v-else-if="sheet && !sheet.papers.length"
       class="text-[0.86rem] text-ink-dim dark:text-night-dim">
      This run extracted no papers, so there is nothing to score.
    </p>

    <template v-if="sheet && sheet.papers.length">
      <p class="mb-3 text-[0.84rem] leading-relaxed text-ink-dim dark:text-night-dim">
        Score the papers the Extractor actually read — follow the DOI to check
        one — then the review itself.
      </p>

      <ul class="papers scroll-soft -mr-1 max-h-[46vh] space-y-2 overflow-y-auto pr-1">
        <li v-for="p in sheet.papers" :key="p.paper_id"
            class="rounded-lg border border-paper-line bg-paper p-3
                   dark:border-night-line dark:bg-night">
          <div class="title text-[0.87rem] font-medium leading-snug">{{ p.title }}</div>
          <div class="sub mt-0.5 text-[0.74rem] text-ink-dim dark:text-night-dim">
            <a v-if="p.doi" :href="`https://doi.org/${p.doi}`" target="_blank"
               rel="noopener noreferrer"
               class="font-mono text-accent no-underline hover:underline">{{ p.doi }}</a>
            <em v-else class="italic">no DOI</em>
            <template v-if="p.venue"> · {{ p.venue }}</template>
            <template v-if="p.year"> · {{ p.year }}</template>
          </div>

          <div class="mt-2 flex items-center gap-1.5">
            <button
              v-for="n in SCORES" :key="n" type="button"
              class="pip h-8 w-8 rounded-md border text-[0.8rem] font-semibold transition"
              :class="paperScores[p.paper_id] === n
                ? 'border-accent bg-accent text-white'
                : 'border-paper-line text-ink-dim hover:border-accent hover:text-accent dark:border-night-line dark:text-night-dim'"
              :disabled="busy"
              :aria-label="`Score ${p.title} ${n} of 5`"
              @click="paperScores[p.paper_id] = n"
            >{{ n }}</button>
          </div>
          <input v-model="paperNotes[p.paper_id]" :disabled="busy"
                 placeholder="why? (optional)"
                 class="control mt-2 !py-1.5 text-[0.82rem]" />
        </li>
      </ul>

      <div class="artefact mt-4 border-t-2 border-paper-line pt-3 dark:border-night-line">
        <h3 class="panel-title mb-1">The review itself</h3>
        <p v-if="sheet.artefact"
           class="mb-2 font-mono text-[0.74rem] text-ink-dim dark:text-night-dim">
          {{ sheet.artefact.name }} · {{ sheet.artefact.chars.toLocaleString() }} characters
        </p>
        <div class="flex items-center gap-1.5">
          <button
            v-for="n in SCORES" :key="n" type="button"
            class="h-8 w-8 rounded-md border text-[0.8rem] font-semibold transition"
            :class="artefactScore === n
              ? 'border-accent bg-accent text-white'
              : 'border-paper-line text-ink-dim hover:border-accent hover:text-accent dark:border-night-line dark:text-night-dim'"
            :disabled="busy"
            :aria-label="`Score the review ${n} of 5`"
            @click="artefactScore = n"
          >{{ n }}</button>
        </div>
        <input v-model="artefactNote" :disabled="busy" placeholder="why? (optional)"
               class="control mt-2 !py-1.5 text-[0.82rem]" />
      </div>

      <div class="mt-4 flex flex-wrap items-center gap-3">
        <button class="btn-primary" :disabled="busy || !dirty" @click="submit">
          {{ busy ? 'Saving…' : 'Save scores' }}
        </button>
        <p v-if="saved" class="text-[0.78rem] text-ink-dim dark:text-night-dim">
          {{ saved }}
        </p>
      </div>
    </template>

    <p v-if="error" class="mt-2 text-[0.82rem] text-unsupported">{{ error }}</p>
  </section>
</template>
