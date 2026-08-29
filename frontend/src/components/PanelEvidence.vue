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
    <header class="mb-3">
      <h2 class="panel-title">3 · Evidence</h2>
      <p class="mt-1 text-[0.84rem] leading-relaxed text-ink-dim dark:text-night-dim">
        <strong class="font-semibold text-ink dark:text-night-fg">{{ matched }}</strong>
        of {{ verifiedClaims.length }} verified claims located in the text.
        Click a marked sentence to see the evidence the Verifier scored it against.
      </p>
    </header>

    <div class="grid items-start gap-4 lg:grid-cols-[1.6fr_1fr]">
      <article v-if="reviewMarkdown"
               class="review scroll-soft max-h-[60vh] max-w-[78ch] overflow-y-auto
                      pr-3 text-[0.94rem] leading-[1.65]">
        <template v-for="(b, i) in blocks" :key="i">
          <div v-if="b.kind === 'md'" v-html="b.html" class="md" />
          <div v-else-if="b.kind === 'blank'" class="h-2" />
          <p v-else class="mb-3">
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
      <p v-else class="text-[0.86rem] text-ink-dim dark:text-night-dim">No review yet.</p>

      <aside class="rounded-xl border border-paper-line bg-paper p-3
                    dark:border-night-line dark:bg-night">
        <div v-if="!selected" class="text-[0.84rem] text-ink-dim dark:text-night-dim">
          <p>Select a highlighted sentence.</p>
          <p class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span class="flex items-center gap-1.5">
              <span class="h-2.5 w-4 rounded-sm bg-supported/25
                           border-b-2 border-supported" /> supported
            </span>
            <span class="flex items-center gap-1.5">
              <span class="h-2.5 w-4 rounded-sm bg-partial/25
                           border-b-2 border-partial" /> partial
            </span>
          </p>
        </div>

        <div v-else>
          <div class="mb-2 flex items-baseline gap-2">
            <span class="rounded px-1.5 py-0.5 text-[0.68rem] font-bold tracking-wide"
                  :class="selected.verdict === 'SUPPORTED'
                    ? 'bg-supported/15 text-supported' : 'bg-partial/15 text-partial'">
              {{ selected.verdict }}
            </span>
            <span class="font-mono text-[0.72rem] text-ink-dim dark:text-night-dim">
              score {{ selected.support_score.toFixed(3) }}
            </span>
          </div>
          <blockquote class="mb-3 border-l-2 border-accent pl-3 text-[0.88rem]
                             leading-relaxed">{{ selected.text }}</blockquote>

          <h4 class="panel-title mb-1.5">Evidence the Verifier scored</h4>
          <div v-if="selected.evidence.length" class="space-y-2">
            <blockquote v-for="(e, i) in selected.evidence" :key="i"
                        class="rounded-lg border border-paper-line bg-paper-card p-2.5
                               dark:border-night-line dark:bg-night-card">
              <p class="text-[0.84rem] leading-relaxed">{{ e.quote }}</p>
              <code class="mt-1 block font-mono text-[0.68rem] text-ink-dim
                           dark:text-night-dim">{{ e.chunk_id }}</code>
            </blockquote>
          </div>
          <p v-else class="text-[0.82rem] text-ink-dim dark:text-night-dim">
            No evidence span recorded for this claim.
          </p>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
/* Kept as scoped CSS rather than utilities: these style sentences rendered
   from v-html and marked at runtime, which utility classes in the template
   cannot reach. Underline rather than highlight, so the prose still reads as
   prose (T-607). */
.sentence { cursor: default; border-radius: 2px; transition: background .15s; }
.sentence.v-supported, .sentence.v-partial { cursor: pointer; }
.sentence.v-supported { border-bottom: 2px solid #2f9e5f; background: #2f9e5f14; }
.sentence.v-partial   { border-bottom: 2px solid #c98a2e; background: #c98a2e14; }
.sentence.v-supported:hover, .sentence.v-partial:hover { background: #2f6fed1f; }
.sentence.active      { background: #2f6fed30; }

.md :deep(h1), .md :deep(h2), .md :deep(h3), .md :deep(h4) {
  margin: 1.1rem 0 .4rem; font-weight: 600; line-height: 1.3;
}
.md :deep(h2) { font-size: 1.02rem; }
.md :deep(h3) { font-size: .95rem; }
.md :deep(p)  { margin: 0 0 .7rem; }
.md :deep(ul), .md :deep(ol) { margin: 0 0 .7rem 1.1rem; }
.md :deep(code) { font-size: .88em; }
</style>
