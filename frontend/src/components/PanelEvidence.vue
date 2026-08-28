<script setup>
// T-607 — Panel 3, evidence inspection. TASKLIST calls this the money shot:
// "click any sentence -> see its supporting evidence span and source paper.
// If one panel survives, it is this one."
//
// ★ The panel's whole job is to make the anti-hallucination claim CHECKABLE
// rather than asserted. So it renders the review as prose and marks each
// sentence the Verifier actually ruled on, with the evidence one click away.
//
// ⚠️ Sentences are matched to claims by NORMALISED TEXT, not by offset. The
// Verifier strips `[n]` markers when it decomposes, and the Writer's markdown
// carries them, so a byte offset into review.md points at the wrong place. The
// normalisation here (drop markers, collapse whitespace, casefold) has to match
// what agents/verifier.py did, and an unmatched sentence renders as plain prose
// rather than being dropped - showing the reader less is better than showing
// them something misattributed.
import { computed, ref } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  reviewMarkdown: { type: String, default: '' },
  verifiedClaims: { type: Array, default: () => [] },
  papers: { type: Array, default: () => [] },
})

const selected = ref(null)

const paperById = computed(() => {
  const map = {}
  for (const p of props.papers) map[p.paper_id] = p
  return map
})

function normalise(s) {
  return (s || '')
    .replace(/\[\d+\]/g, ' ')      // citation markers: the Verifier stripped these
    .replace(/[*_`#]/g, ' ')       // markdown emphasis the model sprinkles in
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

// claim lookup keyed by normalised sentence text
const claimByText = computed(() => {
  const map = new Map()
  for (const c of props.verifiedClaims) {
    const key = normalise(c.text)
    if (key) map.set(key, c)
  }
  return map
})

// Split the review into blocks, then sentences, keeping markdown headings
// intact so the document still reads as a document.
const blocks = computed(() => {
  const out = []
  for (const raw of (props.reviewMarkdown || '').split('\n')) {
    const line = raw.trimEnd()
    if (!line.trim()) { out.push({ kind: 'blank' }); continue }
    if (/^#{1,6}\s/.test(line) || line.startsWith('|') || line.startsWith('---')) {
      out.push({ kind: 'md', html: marked.parse(line) })
      continue
    }
    const parts = line.split(/(?<=[.!?])\s+(?=[A-Z0-9"'(\[])/)
    out.push({
      kind: 'prose',
      sentences: parts.map((text) => ({
        text,
        claim: claimByText.value.get(normalise(text)) || null,
      })),
    })
  }
  return out
})

const matched = computed(() =>
  blocks.value.reduce(
    (n, b) => n + (b.sentences ? b.sentences.filter((s) => s.claim).length : 0), 0),
)

function verdictClass(claim) {
  if (!claim) return ''
  return `v-${claim.verdict.toLowerCase()}`
}

function select(sentence) {
  if (sentence.claim) selected.value = sentence.claim
}
</script>

<template>
  <section class="panel">
    <header>
      <h2>3 · Evidence</h2>
      <p class="hint">
        <strong>{{ matched }}</strong> of {{ verifiedClaims.length }} verified claims
        located in the text. Click a marked sentence to see the evidence the
        Verifier scored it against.
      </p>
    </header>

    <div class="split">
      <article class="review" v-if="reviewMarkdown">
        <template v-for="(b, i) in blocks" :key="i">
          <div v-if="b.kind === 'md'" v-html="b.html" class="md" />
          <div v-else-if="b.kind === 'blank'" class="spacer" />
          <p v-else class="para">
            <span
              v-for="(s, j) in b.sentences"
              :key="j"
              :class="['sentence', verdictClass(s.claim),
                       { active: selected && s.claim && selected.claim_id === s.claim.claim_id }]"
              :title="s.claim ? `${s.claim.verdict} · score ${s.claim.support_score.toFixed(3)}` : ''"
              @click="select(s)"
            >{{ s.text }} </span>
          </p>
        </template>
      </article>
      <p v-else class="empty">No review yet.</p>

      <aside class="evidence">
        <div v-if="!selected" class="empty">
          <p>Select a highlighted sentence.</p>
          <p class="legend">
            <span class="swatch v-supported" /> supported
            <span class="swatch v-partial" /> partial
          </p>
        </div>
        <div v-else>
          <div class="verdict" :class="verdictClass(selected)">
            {{ selected.verdict }}
            <span class="score">score {{ selected.support_score.toFixed(3) }}</span>
          </div>
          <blockquote class="claim">{{ selected.text }}</blockquote>

          <h4>Evidence the Verifier scored</h4>
          <div v-if="selected.evidence.length" class="spans">
            <blockquote v-for="(e, i) in selected.evidence" :key="i" class="span">
              <p>{{ e.quote }}</p>
              <code>{{ e.chunk_id }}</code>
            </blockquote>
          </div>
          <p v-else class="empty">
            No evidence span recorded — this claim cited a paper whose text we
            do not hold.
          </p>

          <h4>Source papers</h4>
          <ul class="papers">
            <li v-for="pid in selected.paper_ids" :key="pid">
              <span v-if="paperById[pid]">
                {{ paperById[pid].title }}
                <em v-if="paperById[pid].year">({{ paperById[pid].year }})</em>
                <span v-if="paperById[pid].text_availability !== 'full'" class="flag">
                  abstract only
                </span>
              </span>
              <code v-else>{{ pid }}</code>
            </li>
          </ul>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.split { display: grid; grid-template-columns: 1.6fr 1fr; gap: 1rem; align-items: start; }
@media (max-width: 900px) { .split { grid-template-columns: 1fr; } }

.review {
  max-height: 60vh; overflow-y: auto; padding-right: .75rem;
  line-height: 1.65; font-size: .94rem;
}
.para { margin: 0 0 .7rem; }
.spacer { height: .4rem; }
.md :deep(h2), .md :deep(h3), .md :deep(h4) { margin: 1rem 0 .4rem; }

.sentence { cursor: default; border-radius: 2px; }
.sentence.v-supported, .sentence.v-partial { cursor: pointer; }
/* Underline, not highlight: the prose must still read as prose. */
.sentence.v-supported { border-bottom: 2px solid #2f9e5f; background: #2f9e5f14; }
.sentence.v-partial   { border-bottom: 2px solid #c98a2e; background: #c98a2e14; }
.sentence.active      { background: #2f6fed26; }

.evidence {
  position: sticky; top: 0; border: 1px solid var(--line);
  border-radius: 8px; padding: .85rem; background: var(--card);
  max-height: 60vh; overflow-y: auto;
}
.verdict { font-weight: 700; letter-spacing: .02em; margin-bottom: .5rem; }
.verdict.v-supported { color: #2f9e5f; }
.verdict.v-partial   { color: #c98a2e; }
.score { font-weight: 400; color: var(--muted); margin-left: .5rem; font-size: .85rem; }

.claim { margin: 0 0 .8rem; padding-left: .7rem; border-left: 3px solid var(--line); }
h4 { margin: .9rem 0 .35rem; font-size: .8rem; text-transform: uppercase;
     letter-spacing: .06em; color: var(--muted); }
.span { margin: 0 0 .6rem; padding: .5rem .6rem; background: var(--bg);
        border-radius: 6px; font-size: .87rem; }
.span p { margin: 0 0 .3rem; }
code { font-size: .76rem; color: var(--muted); }

.papers { margin: 0; padding-left: 1.1rem; font-size: .87rem; }
.flag { font-size: .72rem; color: #c98a2e; border: 1px solid #c98a2e55;
        border-radius: 999px; padding: 0 .4rem; margin-left: .35rem; }

.empty { color: var(--muted); font-size: .88rem; }
.legend { margin-top: .6rem; }
.swatch { display: inline-block; width: .8rem; height: .55rem; border-radius: 2px;
          margin: 0 .25rem 0 .6rem; vertical-align: middle; }
.swatch.v-supported { background: #2f9e5f; }
.swatch.v-partial { background: #c98a2e; }
.hint { color: var(--muted); font-size: .85rem; margin: .2rem 0 .8rem; }
</style>
