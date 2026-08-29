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
import { computed } from 'vue'
import { artifactUrl } from '../api.js'

const props = defineProps({
  runId: { type: String, default: '' },
  droppedClaims: { type: Array, default: () => [] },
  verifiedCount: { type: Number, default: 0 },
  artefacts: { type: Array, default: () => [] },
  overrides: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['override'])

const total = computed(() => props.droppedClaims.length + props.verifiedCount)
const pct = computed(() =>
  total.value ? Math.round((props.droppedClaims.length / total.value) * 100) : 0,
)

function set(claim, decision) {
  // Clicking the same decision twice clears it: a mis-click must be undoable
  // without a reload, or the override log records something nobody meant.
  const current = props.overrides[claim.claim_id]
  emit('override', { claim, decision: current === decision ? null : decision })
}
</script>

<template>
  <section class="panel">
    <header class="mb-3">
      <h2 class="panel-title">4 · Dropped</h2>
      <p class="mt-1 text-[0.92rem]">
        <strong class="font-semibold">{{ droppedClaims.length }}</strong>
        claims were removed as unsupported
        <span class="text-ink-dim dark:text-night-dim">({{ pct }}% of {{ total }})</span>
      </p>
      <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-paper-line
                  dark:bg-night-line">
        <div class="h-full rounded-full bg-unsupported transition-all duration-500"
             :style="{ width: pct + '%' }" />
      </div>
    </header>

    <p v-if="!droppedClaims.length"
       class="text-[0.86rem] text-ink-dim dark:text-night-dim">
      Nothing was dropped in this run.
    </p>

    <ul class="scroll-soft -mr-1 max-h-[45vh] space-y-2 overflow-y-auto pr-1">
      <li v-for="c in droppedClaims" :key="c.claim_id"
          class="rounded-lg border border-paper-line bg-paper p-3
                 dark:border-night-line dark:bg-night">
        <div class="mb-1.5 flex items-baseline gap-2">
          <span
            class="rounded px-1.5 py-0.5 text-[0.68rem] font-bold tracking-wide"
            :class="c.verdict === 'CONTRADICTED'
              ? 'bg-[#8e44ad]/15 text-[#8e44ad]'
              : 'bg-unsupported/15 text-unsupported'"
          >{{ c.verdict }}</span>
          <span class="font-mono text-[0.72rem] text-ink-dim dark:text-night-dim">
            score {{ c.support_score.toFixed(3) }}
          </span>
        </div>
        <p class="mb-2 max-w-[75ch] text-[0.88rem] leading-relaxed">{{ c.text }}</p>

        <div class="flex flex-wrap items-center gap-1.5">
          <button
            class="btn-ghost"
            :class="overrides[c.claim_id] === 'confirm'
              ? '!border-supported !text-supported bg-supported/10' : ''"
            @click="set(c, 'confirm')"
          >Correct to drop</button>
          <button
            class="btn-ghost"
            :class="overrides[c.claim_id] === 'reinstate'
              ? '!border-replan !text-replan bg-replan/10' : ''"
            @click="set(c, 'reinstate')"
          >Should have been kept</button>
          <span v-if="overrides[c.claim_id]"
                class="text-[0.7rem] uppercase tracking-wide text-ink-dim
                       dark:text-night-dim">recorded</span>
        </div>
      </li>
    </ul>

    <div v-if="artefacts.length" class="mt-4 border-t border-paper-line pt-3
                                        dark:border-night-line">
      <h3 class="panel-title mb-2">Artefacts</h3>
      <div class="flex flex-wrap gap-1.5">
        <a v-for="a in artefacts" :key="a" :href="artifactUrl(runId, a)" download
           class="rounded-md border border-paper-line px-2 py-1 font-mono
                  text-[0.72rem] text-ink-dim no-underline transition
                  hover:border-accent hover:text-accent
                  dark:border-night-line dark:text-night-dim">
          ↓ {{ a }}
        </a>
      </div>
    </div>
  </section>
</template>
