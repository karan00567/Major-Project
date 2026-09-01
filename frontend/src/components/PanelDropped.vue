<script setup>
// T-608 — Panel 4, dropped claims and artefact downloads.
// TASKLIST: "Showing what the system REFUSED to say is more persuasive than
// showing what it said."
//
// T-609 — Human-in-the-loop. REQUIRED: decisions.txt T-007 (2026-08-25) made
// HITL mandatory, and it is the concrete implementation of Objective 2's "and
// Human-in-the-loop" clause. Without it that objective is unmet and the claim
// on deck slide 5 is false.
//
// ⚠️ An override does NOT edit the review. It records a human judgement against
// a claim the Verifier dropped, which is a different and more honest thing: the
// artefact keeps saying what the system could ground, and the override says
// what a person decided about the gap. Reinstating text into review.md on a
// click would quietly destroy the very property the panel exists to prove.
//
// Two additions, 2026-08-30. The panel showed a dropped claim's score but not
// the evidence behind it, so it asserted "this was not supported" with the
// supporting material one file away — the near-miss span is what makes a 0.217
// legible as a judgement rather than a verdict. And the reviewer's REASON now
// has somewhere to go: `OverrideRequest.note` has always accepted one (2,000
// chars, persisted to the trace) and the UI never sent it, so the audit record
// could say a human disagreed but never why.
import { computed, ref } from 'vue'
import { artifactUrl } from '../api.js'
import { marked } from 'marked'
import { pct } from '../lib/format.js'

const props = defineProps({
  runId: { type: String, default: '' },
  droppedClaims: { type: Array, default: () => [] },
  verifiedCount: { type: Number, default: 0 },
  artefacts: { type: Array, default: () => [] },
  overrides: { type: Object, default: () => ({}) },
  overrideNotes: { type: Object, default: () => ({}) },
  threshold: { type: Number, default: null },
})
const emit = defineEmits(['override'])

/** What each artefact is. A row of filenames tells a reader nothing about
 *  which one to open, and `trace.jsonl` — the audit record every figure in the
 *  report is derived from — looked like the least interesting of the seven. */
const ARTEFACT_NOTE = {
  'review.md': 'the cited survey, as written',
  'claims.json': 'every claim, its verdict, score and evidence span',
  'insights.csv': 'per-paper structured extraction',
  'refs.bib': 'BibTeX for everything cited',
  'corpus.json': 'every retrieved paper, with metadata',
  'config.json': 'the resolved config, including which provider served it',
  'trace.jsonl': 'every agent event — the audit record',
}

const total = computed(() => props.droppedClaims.length + props.verifiedCount)
const pctDropped = computed(() =>
  total.value ? Math.round((props.droppedClaims.length / total.value) * 100) : 0,
)

/** How many of the drops a human has actually looked at. Without this the
 *  panel cannot say whether an empty override log means "the Verifier was
 *  right about all of them" or "nobody checked". */
const reviewed = computed(() =>
  props.droppedClaims.filter((c) => props.overrides[c.claim_id]).length,
)
const disputed = computed(() =>
  props.droppedClaims.filter((c) => props.overrides[c.claim_id] === 'reinstate').length,
)

/** Which claim's note editor is open. One at a time: a column of open text
 *  boxes turns a short list of judgements into a form. */
const noting = ref(null)
const draft = ref('')

function set(claim, decision) {
  // Clicking the same decision twice clears it: a mis-click must be undoable
  // without a reload, or the override log records something nobody meant.
  const current = props.overrides[claim.claim_id]
  const next = current === decision ? null : decision
  emit('override', { claim, decision: next, note: next ? props.overrideNotes[claim.claim_id] : null })
  if (next === null && noting.value === claim.claim_id) noting.value = null
}

function openNote(claim) {
  noting.value = noting.value === claim.claim_id ? null : claim.claim_id
  draft.value = props.overrideNotes[claim.claim_id] || ''
}

function saveNote(claim) {
  emit('override', {
    claim,
    decision: props.overrides[claim.claim_id] || null,
    note: draft.value.trim() || null,
  })
  noting.value = null
}

function inline(text) {
  return marked.parseInline(text || '')
}

const VERDICT_CLS = {
  CONTRADICTED: 'bg-contradicted/15 text-contradicted dark:text-contradicted-lite',
  UNSUPPORTED: 'bg-unsupported/15 text-unsupported dark:text-unsupported-lite',
}
</script>

<template>
  <section class="panel panel-pad">
    <header class="mb-3">
      <div class="panel-head">
        <h2 class="panel-title"><span class="panel-index">4</span> Dropped</h2>
        <span v-if="droppedClaims.length" class="pill-soft"
              :title="`${reviewed} of ${droppedClaims.length} drops have a recorded human judgement`">
          {{ reviewed }}/{{ droppedClaims.length }} reviewed
          <template v-if="disputed">· {{ disputed }} disputed</template>
        </span>
      </div>

      <p class="mt-2 text-[0.92rem]">
        <strong class="font-semibold">{{ droppedClaims.length }}</strong>
        {{ droppedClaims.length === 1 ? 'claim was' : 'claims were' }} removed as
        unsupported
        <span class="text-ink-dim dark:text-night-dim">
          ({{ pctDropped }}% of {{ total }} decomposed)</span>
      </p>
      <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-paper-sunk
                  dark:bg-night-sunk">
        <div class="h-full rounded-full bg-unsupported transition-all duration-500"
             :style="{ width: pctDropped + '%' }" />
      </div>
      <p class="panel-note mt-2">
        These sentences were written, then cut. Each was scored against the
        paper it cited and fell below the
        <template v-if="threshold != null">
          <b class="font-semibold text-ink dark:text-night-fg">{{ threshold }}</b>
        </template>
        support bar. Judge each one — your decision is appended to
        <code class="tag-mono">trace.jsonl</code>, and does not change the review.
      </p>
    </header>

    <p v-if="!droppedClaims.length" class="panel-note">
      Nothing was dropped in this run. Every decomposed claim cleared the
      support bar — which is a result about this question, not a guarantee.
    </p>

    <ul class="scroll-soft -mr-1 max-h-[48vh] space-y-2 overflow-y-auto pr-1">
      <li v-for="c in droppedClaims" :key="c.claim_id"
          class="rounded-xl border border-paper-line bg-paper p-3 transition
                 dark:border-night-line dark:bg-night"
          :class="overrides[c.claim_id] === 'reinstate'
            ? '!border-replan/60' : overrides[c.claim_id] ? '!border-supported/60' : ''">
        <div class="mb-1.5 flex flex-wrap items-center gap-2">
          <span class="pill" :class="VERDICT_CLS[c.verdict] || VERDICT_CLS.UNSUPPORTED">
            {{ c.verdict }}
          </span>
          <span class="font-mono text-[0.72rem] text-ink-dim dark:text-night-dim"
                :title="threshold != null
                  ? `scored ${c.support_score.toFixed(3)} against a ${threshold} bar`
                  : ''">
            support {{ c.support_score.toFixed(3) }}
          </span>
          <span class="tag-mono ml-auto">{{ c.claim_id }}</span>
        </div>

        <!-- How far short it fell, against the bar it had to clear. -->
        <div v-if="threshold != null"
             class="relative mb-2 h-1.5 w-full overflow-hidden rounded-full
                    bg-paper-sunk dark:bg-night-sunk">
          <div class="h-full rounded-full bg-unsupported/70"
               :style="{ width: `${Math.max(1, c.support_score * 100)}%` }" />
          <div class="absolute inset-y-0 w-px bg-ink-dim dark:bg-night-dim"
               :style="{ left: `${threshold * 100}%` }"
               :title="`support threshold ${threshold}`" />
        </div>

        <!-- The Writer emits markdown, so an interpolated claim shows its own
             asterisks. Display only: `c.text` is what the Verifier scored. -->
        <p class="mb-2 max-w-[75ch] text-[0.88rem] leading-relaxed"
           v-html="inline(c.text)" />

        <!-- The closest thing the Verifier found. Showing it is what turns
             "unsupported" from a verdict into something checkable. -->
        <details v-if="c.evidence && c.evidence.length" class="group mb-2">
          <summary class="cursor-pointer list-none text-[0.74rem] font-medium
                          text-ink-dim transition hover:text-accent
                          dark:text-night-dim">
            <span class="transition group-open:rotate-90 inline-block"
                  aria-hidden="true">›</span>
            the closest evidence it found ({{ pct(c.support_score, 1) }} support)
          </summary>
          <blockquote v-for="(e, i) in c.evidence" :key="i"
                      class="mt-1.5 rounded-lg border border-paper-line bg-paper-card
                             p-2.5 text-[0.82rem] leading-relaxed
                             dark:border-night-line dark:bg-night-card">
            {{ e.quote }}
            <code class="mt-1 block font-mono text-[0.66rem] text-ink-faint
                         dark:text-night-faint">{{ e.chunk_id }}</code>
          </blockquote>
        </details>

        <div class="flex flex-wrap items-center gap-1.5">
          <button
            class="btn-ghost"
            :class="overrides[c.claim_id] === 'confirm'
              ? '!border-supported !text-supported bg-supported/10' : ''"
            :aria-pressed="overrides[c.claim_id] === 'confirm'"
            @click="set(c, 'confirm')"
          >Correct to drop</button>
          <button
            class="btn-ghost"
            :class="overrides[c.claim_id] === 'reinstate'
              ? '!border-replan !text-replan bg-replan/10' : ''"
            :aria-pressed="overrides[c.claim_id] === 'reinstate'"
            @click="set(c, 'reinstate')"
          >Should have been kept</button>
          <button v-if="overrides[c.claim_id]" class="btn-quiet"
                  @click="openNote(c)">
            {{ overrideNotes[c.claim_id] ? 'edit note' : 'add a note' }}
          </button>
          <span v-if="overrides[c.claim_id]"
                class="ml-auto text-[0.7rem] uppercase tracking-wide text-ink-dim
                       dark:text-night-dim">recorded</span>
        </div>

        <div v-if="noting === c.claim_id" class="mt-2">
          <textarea v-model="draft" rows="2" maxlength="2000"
                    placeholder="Why? This is appended to the run's trace, not to the review."
                    class="control resize-y text-[0.82rem]" />
          <div class="mt-1.5 flex items-center gap-2">
            <button class="btn-ghost" @click="saveNote(c)">Save note</button>
            <button class="btn-quiet" @click="noting = null">Cancel</button>
          </div>
        </div>
        <p v-else-if="overrideNotes[c.claim_id]"
           class="mt-2 border-l-2 border-paper-line pl-2.5 text-[0.8rem] italic
                  text-ink-dim dark:border-night-line dark:text-night-dim">
          {{ overrideNotes[c.claim_id] }}
        </p>
      </li>
    </ul>

    <div v-if="artefacts.length" class="mt-4 border-t border-paper-hair pt-3
                                        dark:border-night-hair">
      <h3 class="panel-title mb-2">Artefacts</h3>
      <div class="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        <a v-for="a in artefacts" :key="a" :href="artifactUrl(runId, a)" download
           class="group flex items-baseline gap-2 rounded-lg border border-paper-line
                  px-2.5 py-1.5 no-underline transition hover:border-accent
                  hover:bg-accent-soft dark:border-night-line">
          <span class="font-mono text-[0.74rem] text-accent dark:text-accent-lite">
            ↓ {{ a }}
          </span>
          <span class="min-w-0 flex-1 truncate text-[0.72rem] text-ink-dim
                       dark:text-night-dim">{{ ARTEFACT_NOTE[a] || '' }}</span>
        </a>
      </div>
      <p class="panel-note mt-2">
        <code class="tag-mono">trace.jsonl</code> is the single source of truth:
        the live stream tails it, these overrides append to it, and every figure
        in the report is derived from it.
      </p>
    </div>
  </section>
</template>
