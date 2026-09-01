<script setup>
// T-607 — Panel 3, evidence inspection. TASKLIST calls this the money shot:
// "click any sentence -> see its supporting evidence span and source paper.
// If one panel survives, it is this one."
//
// ★ The panel's whole job is to make the anti-hallucination claim CHECKABLE
// rather than asserted. So it renders the review as prose and marks each
// sentence the Verifier actually ruled on, with the evidence one click away.
//
// 🔴 "and source paper" was the half that was missing. `paperById` was built
// and then never read: the aside showed the evidence quote and a chunk id, and
// a chunk id is not a citation a reader can follow. So the panel proved the
// system had SOME text to point at, but not that the text came from the paper
// the sentence cites — which is the whole claim. It now names the paper, with
// its venue, year and a DOI link, because a reader who cannot get to the source
// has to take the panel's word for it. (Serving that needed an API fix too: the
// payload's 200-paper cap was truncating five of the fixture's nine cited
// papers — see `_papers_for_panel` in api/app.py.)
//
// The prose is rendered through `marked.parseInline` rather than interpolated,
// because the Writer emits markdown and the panel was printing it raw: a lead-in
// like "**Formal multi-agent architectures.**" reached the screen with its
// asterisks, in the one panel whose whole job is to be read closely. The claim
// matching still runs on the RAW sentence — `normalise()` strips the markers
// itself, which is exactly why the mismatch went unnoticed for so long: matching
// worked perfectly while the display did not.
//
// ⚠️ Sentences are matched to claims by NORMALISED TEXT, not by offset. The
// Verifier strips `[n]` markers when it decomposes, and the Writer's markdown
// carries them, so a byte offset into review.md points at the wrong place. The
// normalisation here (drop markers, collapse whitespace, casefold) has to match
// what agents/verifier.py did — tests/test_phase6_acceptance.py asserts the two
// stay identical — and an unmatched sentence renders as plain prose rather than
// being dropped: showing the reader less is better than showing them something
// misattributed.
import { computed, ref } from 'vue'
import { marked } from 'marked'
import { pct } from '../lib/format.js'

const props = defineProps({
  reviewMarkdown: { type: String, default: '' },
  verifiedClaims: { type: Array, default: () => [] },
  papers: { type: Array, default: () => [] },
})

const selected = ref(null)
/** Dim everything the Verifier did not rule on, so the verified spine of the
 *  document stands out. Off by default: the review has to read as a review
 *  first, and only then as an audit. */
const focusMode = ref(false)

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
        // ⚠️ `html` is for DISPLAY only; `text` stays raw because it is what
        // normalise() matches claims against, and the two must not diverge.
        html: marked.parseInline(text),
        claim: claimByText.value.get(normalise(text)) || null,
      })),
    })
  }
  return out
})

/** The marked sentences, in document order. Drives the prev/next control: with
 *  a 11,000-character review, hunting for the next underline by eye is work the
 *  panel can do for the reader. */
const located = computed(() => {
  const out = []
  for (const b of blocks.value) {
    for (const s of b.sentences || []) if (s.claim) out.push(s.claim)
  }
  return out
})

const matched = computed(() => located.value.length)

const cursor = computed(() =>
  selected.value
    ? located.value.findIndex((c) => c.claim_id === selected.value.claim_id)
    : -1,
)

function step(delta) {
  if (!located.value.length) return
  const next = cursor.value < 0
    ? (delta > 0 ? 0 : located.value.length - 1)
    : (cursor.value + delta + located.value.length) % located.value.length
  selected.value = located.value[next]
  document
    .querySelector(`[data-claim="${located.value[next].claim_id}"]`)
    ?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

/** The papers a claim cites, resolved against the corpus. An id we cannot
 *  resolve is still shown as an id — silence would read as "no source". */
const sources = computed(() => {
  if (!selected.value) return []
  return (selected.value.paper_ids || []).map((id) => ({
    id,
    paper: paperById.value[id] || null,
  }))
})

/** Render a claim's own markdown for display. The stored text is what the
 *  Verifier scored and must not be edited — this only affects what is drawn. */
function inline(text) {
  return marked.parseInline(text || '')
}

function verdictClass(claim) {
  if (!claim) return ''
  return `v-${claim.verdict.toLowerCase()}`
}

function select(sentence) {
  if (sentence.claim) selected.value = sentence.claim
}
</script>

<template>
  <section class="panel panel-pad">
    <header class="panel-head mb-3">
      <div class="min-w-0">
        <h2 class="panel-title"><span class="panel-index">3</span> Evidence</h2>
        <p class="panel-note mt-1.5 max-w-2xl">
          <strong class="font-semibold text-ink dark:text-night-fg">{{ matched }}</strong>
          of {{ verifiedClaims.length }} verified claims located in the text.
          Click a marked sentence to see the evidence the Verifier scored it
          against, and the paper that evidence came from.
        </p>
      </div>

      <div class="flex shrink-0 items-center gap-1.5">
        <button class="btn-quiet" :disabled="!matched" title="Previous verified claim"
                @click="step(-1)">‹ prev</button>
        <span class="min-w-[4.5rem] text-center font-mono text-[0.72rem] tabular-nums
                     text-ink-dim dark:text-night-dim">
          {{ cursor >= 0 ? cursor + 1 : '–' }} / {{ matched }}
        </span>
        <button class="btn-quiet" :disabled="!matched" title="Next verified claim"
                @click="step(1)">next ›</button>
        <button class="btn-ghost ml-1"
                :class="focusMode ? '!border-accent !text-accent' : ''"
                title="Dim every sentence the Verifier did not rule on"
                :aria-pressed="focusMode"
                @click="focusMode = !focusMode">focus</button>
      </div>
    </header>

    <div class="grid grid-cols-1 items-start gap-4 xl:grid-cols-[1.7fr_1fr]">
      <article v-if="reviewMarkdown"
               :class="['review scroll-soft max-h-[62vh] max-w-[78ch] overflow-y-auto',
                        'pr-3 text-[0.94rem] leading-[1.7]', { focus: focusMode }]">
        <template v-for="(b, i) in blocks" :key="i">
          <div v-if="b.kind === 'md'" v-html="b.html" class="md" />
          <div v-else-if="b.kind === 'blank'" class="h-2" />
          <p v-else class="mb-3">
            <!-- A ruled sentence is a control, so it is focusable and answers
                 Enter and Space. Without this the panel is mouse-only, and its
                 whole point is that the reader can interrogate it. -->
            <span
              v-for="(s, j) in b.sentences"
              :key="j"
              :data-claim="s.claim ? s.claim.claim_id : undefined"
              :class="['sentence', verdictClass(s.claim),
                       { active: selected && s.claim && selected.claim_id === s.claim.claim_id }]"
              :role="s.claim ? 'button' : undefined"
              :tabindex="s.claim ? 0 : undefined"
              :aria-pressed="s.claim
                ? !!(selected && selected.claim_id === s.claim.claim_id) : undefined"
              :title="s.claim
                ? `${s.claim.verdict} · support ${s.claim.support_score.toFixed(3)} — click for the evidence`
                : ''"
              @click="select(s)"
              @keydown.enter.prevent="select(s)"
              @keydown.space.prevent="select(s)"
              v-html="`${s.html} `"
            />
          </p>
        </template>
      </article>

      <div v-else class="space-y-2 py-4">
        <p class="panel-note">
          No review yet. The Writer produces <code class="tag-mono">review.md</code>
          only after the Critic returns WRITE.
        </p>
        <div class="skeleton h-3 w-full" />
        <div class="skeleton h-3 w-11/12" />
        <div class="skeleton h-3 w-4/5" />
      </div>

      <aside class="scroll-soft top-16 max-h-[62vh] overflow-y-auto rounded-xl
                    border border-paper-line bg-paper p-3 xl:sticky
                    dark:border-night-line dark:bg-night">
        <div v-if="!selected" class="panel-note space-y-3">
          <p class="font-medium text-ink dark:text-night-fg">
            Select a highlighted sentence.
          </p>
          <p>
            Every underlined sentence was decomposed into a claim, scored
            against the retrieved evidence, and kept. The colour is the verdict.
          </p>
          <ul class="space-y-1.5">
            <li class="flex items-center gap-2">
              <span class="h-2.5 w-5 shrink-0 rounded-sm border-b-2 border-supported
                           bg-supported/25" />
              <span><b class="font-semibold text-ink dark:text-night-fg">supported</b>
                — the evidence entails the claim</span>
            </li>
            <li class="flex items-center gap-2">
              <span class="h-2.5 w-5 shrink-0 rounded-sm border-b-2 border-partial
                           bg-partial/25" />
              <span><b class="font-semibold text-ink dark:text-night-fg">partial</b>
                — consistent, but the abstract does not carry the whole claim</span>
            </li>
            <li class="flex items-center gap-2">
              <span class="h-2.5 w-5 shrink-0 rounded-sm bg-paper-sunk
                           dark:bg-night-sunk" />
              <span>unmarked — the Verifier ruled on no claim for this sentence
                (a heading, or a sentence it could not match)</span>
            </li>
          </ul>
        </div>

        <!-- Keyed on the claim so switching sentences replays the entrance:
             without it the aside swaps content in place and a click on a new
             sentence can look like nothing happened. -->
        <div v-else :key="selected.claim_id" class="animate-rise-in">
          <div class="mb-2 flex flex-wrap items-center gap-2">
            <span class="pill"
                  :class="selected.verdict === 'SUPPORTED'
                    ? 'bg-supported/15 text-supported dark:text-supported-lite'
                    : 'bg-partial/15 text-partial dark:text-partial-lite'">
              {{ selected.verdict }}
            </span>
            <span class="font-mono text-[0.72rem] text-ink-dim dark:text-night-dim">
              support {{ selected.support_score.toFixed(3) }}
            </span>
            <span class="tag-mono ml-auto">{{ selected.claim_id }}</span>
          </div>

          <!-- The score as a bar. A number between 0 and 1 means nothing until
               you know where the bar sat; the fill says it at a glance. -->
          <div class="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-paper-sunk
                      dark:bg-night-sunk"
               :title="`support ${pct(selected.support_score, 1)}`">
            <div class="h-full rounded-full transition-all duration-500"
                 :class="selected.verdict === 'SUPPORTED' ? 'bg-supported' : 'bg-partial'"
                 :style="{ width: `${Math.max(2, selected.support_score * 100)}%` }" />
          </div>

          <!-- Same reason as the prose: the claim text is markdown, and the
               aside was echoing its asterisks back at the reader. -->
          <blockquote class="mb-3 border-l-2 border-accent pl-3 text-[0.88rem]
                             leading-relaxed"
                      v-html="inline(selected.text)" />

          <h4 class="panel-title mb-1.5">Source</h4>
          <div v-if="sources.length" class="mb-3 space-y-2">
            <div v-for="s in sources" :key="s.id"
                 class="rounded-lg border border-paper-line bg-paper-card p-2.5
                        dark:border-night-line dark:bg-night-card">
              <template v-if="s.paper">
                <p class="text-[0.84rem] font-medium leading-snug">{{ s.paper.title }}</p>
                <p v-if="(s.paper.authors || []).length"
                   class="mt-1 text-[0.76rem] text-ink-dim dark:text-night-dim">
                  {{ s.paper.authors.slice(0, 3).join(', ')
                  }}<template v-if="s.paper.authors.length > 3"> et al.</template>
                </p>
                <div class="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1
                            text-[0.72rem] text-ink-dim dark:text-night-dim">
                  <span v-if="s.paper.venue" class="truncate">{{ s.paper.venue }}</span>
                  <span v-if="s.paper.year">· {{ s.paper.year }}</span>
                  <span v-if="s.paper.citation_count != null"
                        :title="`${s.paper.citation_count} citations, per OpenAlex`">
                    · {{ s.paper.citation_count }} cites
                  </span>
                  <span v-if="s.paper.is_preprint"
                        class="pill bg-replan/15 text-replan dark:text-replan-lite">
                    preprint
                  </span>
                </div>
                <a v-if="s.paper.doi" :href="`https://doi.org/${s.paper.doi}`"
                   target="_blank" rel="noopener noreferrer"
                   class="link mt-1.5 inline-block font-mono text-[0.72rem]">
                  doi.org/{{ s.paper.doi }} ↗
                </a>
                <a v-else-if="s.paper.url" :href="s.paper.url" target="_blank"
                   rel="noopener noreferrer"
                   class="link mt-1.5 inline-block text-[0.72rem]">open the source ↗</a>
              </template>
              <p v-else class="text-[0.78rem] text-ink-dim dark:text-night-dim">
                <span class="tag-mono">{{ s.id }}</span>
                — not in this run's returned corpus.
              </p>
            </div>
          </div>
          <p v-else class="panel-note mb-3">
            This claim carries no paper id, so there is no source to follow.
          </p>

          <h4 class="panel-title mb-1.5">Evidence the Verifier scored</h4>
          <div v-if="selected.evidence.length" class="space-y-2">
            <blockquote v-for="(e, i) in selected.evidence" :key="i"
                        class="rounded-lg border border-paper-line bg-paper-card p-2.5
                               dark:border-night-line dark:bg-night-card">
              <p class="text-[0.84rem] leading-relaxed">{{ e.quote }}</p>
              <code class="mt-1.5 block font-mono text-[0.68rem] text-ink-faint
                           dark:text-night-faint"
                    title="The chunk this span came from: paper id, then its index in that paper">
                {{ e.chunk_id }}
              </code>
            </blockquote>
          </div>
          <p v-else class="panel-note">
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
.sentence { cursor: default; border-radius: 2px; transition: background .15s, opacity .2s; }
.sentence.v-supported, .sentence.v-partial { cursor: pointer; }
.sentence.v-supported { border-bottom: 2px solid #2f9e5f; background: #2f9e5f14; }
.sentence.v-partial   { border-bottom: 2px solid #c98a2e; background: #c98a2e14; }
.sentence.v-supported:hover, .sentence.v-partial:hover { background: #2f6fed1f; }
.sentence.active      { background: #2f6fed30; box-shadow: 0 0 0 2px #2f6fed40; }

/* Focus mode: fade what was never ruled on, so the verified spine of the
   document is visible without reading it. */
.review.focus .sentence:not(.v-supported):not(.v-partial) { opacity: .38; }
.review.focus :deep(.md) { opacity: .6; }

.md :deep(h1), .md :deep(h2), .md :deep(h3), .md :deep(h4) {
  margin: 1.2rem 0 .45rem; font-weight: 600; line-height: 1.3;
  letter-spacing: -0.01em;
}
.md :deep(h2) { font-size: 1.05rem; }
.md :deep(h3) { font-size: .96rem; }
.md :deep(p)  { margin: 0 0 .7rem; }
.md :deep(ul), .md :deep(ol) { margin: 0 0 .7rem 1.1rem; }
.md :deep(code) { font-size: .88em; }
.md :deep(a) { color: #2f6fed; text-decoration: none; }
.md :deep(a:hover) { text-decoration: underline; }
</style>
