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
    <header>
      <h2>4 · Dropped</h2>
      <p class="headline">
        <strong>{{ droppedClaims.length }}</strong> claims were removed as unsupported
        <span class="muted">({{ pct }}% of {{ total }})</span>
      </p>
    </header>

    <p v-if="!droppedClaims.length" class="empty">
      Nothing was dropped in this run.
    </p>

    <ul class="claims">
      <li v-for="c in droppedClaims" :key="c.claim_id">
        <div class="head">
          <span :class="['verdict', c.verdict.toLowerCase()]">{{ c.verdict }}</span>
          <span class="score">score {{ c.support_score.toFixed(3) }}</span>
        </div>
        <p class="text">{{ c.text }}</p>

        <div class="hitl">
          <button
            :class="['btn', { on: overrides[c.claim_id] === 'confirm' }]"
            @click="set(c, 'confirm')"
          >Correct to drop</button>
          <button
            :class="['btn', 'warn', { on: overrides[c.claim_id] === 'reinstate' }]"
            @click="set(c, 'reinstate')"
          >Should have been kept</button>
          <span v-if="overrides[c.claim_id]" class="logged">recorded</span>
        </div>
      </li>
    </ul>

    <div v-if="artefacts.length" class="downloads">
      <h3>Artefacts</h3>
      <a v-for="a in artefacts" :key="a" :href="artifactUrl(runId, a)" download>{{ a }}</a>
    </div>
  </section>
</template>

<style scoped>
.headline { margin: .2rem 0 .8rem; font-size: .92rem; }
.muted { color: var(--muted); font-weight: 400; }
.claims { list-style: none; margin: 0; padding: 0; max-height: 45vh; overflow-y: auto; }
.claims li { border: 1px solid var(--line); border-radius: 8px; padding: .6rem .7rem;
             margin-bottom: .55rem; background: var(--card); }
.head { display: flex; gap: .6rem; align-items: baseline; margin-bottom: .3rem; }
.verdict { font-size: .72rem; font-weight: 700; letter-spacing: .04em;
           padding: .1rem .4rem; border-radius: 4px; }
.verdict.unsupported { background: #d9534f22; color: #d9534f; }
.verdict.contradicted { background: #8e44ad22; color: #8e44ad; }
.score { font-size: .76rem; color: var(--muted); }
.text { margin: 0 0 .5rem; font-size: .88rem; line-height: 1.5; }
.hitl { display: flex; gap: .4rem; align-items: center; }
.btn { font-size: .76rem; padding: .25rem .55rem; border: 1px solid var(--line);
       background: var(--bg); color: var(--muted); border-radius: 5px; cursor: pointer; }
.btn.on { border-color: #2f9e5f; color: #2f9e5f; background: #2f9e5f14; }
.btn.warn.on { border-color: #c98a2e; color: #c98a2e; background: #c98a2e14; }
.logged { font-size: .72rem; color: var(--muted); }
.downloads { margin-top: 1rem; }
.downloads h3 { font-size: .76rem; text-transform: uppercase; letter-spacing: .06em;
                color: var(--muted); margin: 0 0 .35rem; }
.downloads a { display: inline-block; font-size: .8rem; margin: 0 .5rem .3rem 0;
               color: #2f6fed; }
.empty { color: var(--muted); font-size: .88rem; }
</style>
