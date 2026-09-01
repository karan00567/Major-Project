<script setup>
// Panel 5 — the papers behind the review. New 2026-08-30.
//
// ★ Why. The run page could tell you that 551 papers were found and 22 claims
// were checked, and then never showed you a single paper. The corpus was in the
// payload the whole time and rendered nowhere on the main route — the only
// place any paper appeared was the scoring sheet, behind /optimizer. So a
// reader could not answer the first question anyone asks a literature-review
// tool: *what did it read?*
//
// The funnel is the honest framing, and it is also the project's main
// limitation stated in its own numbers: hundreds retrieved, ten read, nine
// cited. Retrieval quality is the known bottleneck (README, "Results,
// honestly"); a panel that showed only the nine winners would hide the shape of
// that.
import { computed, ref } from 'vue'
import { num } from '../lib/format.js'

const props = defineProps({
  papers: { type: Array, default: () => [] },
  verifiedClaims: { type: Array, default: () => [] },
  droppedClaims: { type: Array, default: () => [] },
  extractedIds: { type: Array, default: () => [] },
  /** Everything the Retriever found, which is usually more than the payload
   *  carries — so the panel can say what it is not showing. */
  corpusTotal: { type: Number, default: null },
})

const query = ref('')
const view = ref('cited')          // cited | read | all

/** paper_id -> how many surviving claims cite it. The count is the paper's
 *  weight in the review, and it is the only ranking here that is about this
 *  run rather than about the wider literature. */
const citedCount = computed(() => {
  const counts = {}
  for (const c of props.verifiedClaims) {
    for (const id of c.paper_ids || []) counts[id] = (counts[id] || 0) + 1
  }
  return counts
})

const droppedCount = computed(() => {
  const counts = {}
  for (const c of props.droppedClaims) {
    for (const id of c.paper_ids || []) counts[id] = (counts[id] || 0) + 1
  }
  return counts
})

const extracted = computed(() => new Set(props.extractedIds))

const decorated = computed(() =>
  props.papers.map((p) => ({
    ...p,
    cites: citedCount.value[p.paper_id] || 0,
    dropped: droppedCount.value[p.paper_id] || 0,
    read: extracted.value.has(p.paper_id),
  })),
)

const counts = computed(() => ({
  cited: decorated.value.filter((p) => p.cites || p.dropped).length,
  read: decorated.value.filter((p) => p.read).length,
  all: decorated.value.length,
}))

const VIEWS = computed(() => [
  { key: 'cited', label: 'Cited', n: counts.value.cited,
    hint: 'papers a claim in the review points at' },
  { key: 'read', label: 'Read', n: counts.value.read,
    hint: 'papers the Extractor pulled structured fields from' },
  { key: 'all', label: 'Retrieved', n: counts.value.all,
    hint: 'the corpus this payload carries' },
])

const rows = computed(() => {
  const q = query.value.trim().toLowerCase()
  let out = decorated.value
  if (view.value === 'cited') out = out.filter((p) => p.cites || p.dropped)
  else if (view.value === 'read') out = out.filter((p) => p.read)
  if (q) {
    out = out.filter((p) =>
      `${p.title || ''} ${(p.authors || []).join(' ')} ${p.venue || ''}`
        .toLowerCase().includes(q))
  }
  // Most-cited first inside the current view; then newest, so an unranked tail
  // does not open with a 2019 paper nobody cited.
  return [...out].sort((a, b) => (b.cites - a.cites) || ((b.year || 0) - (a.year || 0)))
})

/** A one-line profile of the corpus. Every number is counted from what is on
 *  screen, so it cannot drift from the list under it. */
const profile = computed(() => {
  const all = decorated.value
  if (!all.length) return null
  const years = all.map((p) => p.year).filter(Boolean)
  const preprints = all.filter((p) => p.is_preprint).length
  const abstracts = all.filter((p) => p.abstract).length
  const sources = {}
  for (const p of all) sources[p.source || 'unknown'] = (sources[p.source || 'unknown'] || 0) + 1
  return {
    span: years.length ? `${Math.min(...years)}–${Math.max(...years)}` : '—',
    preprints,
    abstracts,
    sources: Object.entries(sources).sort((a, b) => b[1] - a[1]),
  }
})

const truncated = computed(() =>
  props.corpusTotal != null && props.corpusTotal > props.papers.length
    ? props.corpusTotal - props.papers.length
    : 0,
)
</script>

<template>
  <section class="panel panel-pad">
    <header class="panel-head mb-3">
      <div class="min-w-0">
        <h2 class="panel-title"><span class="panel-index">5</span> Sources</h2>
        <p class="panel-note mt-1.5">
          The funnel this run actually ran:
          <b class="font-semibold text-ink dark:text-night-fg">{{ num(corpusTotal ?? counts.all) }}</b>
          retrieved →
          <b class="font-semibold text-ink dark:text-night-fg">{{ counts.read || '—' }}</b>
          read →
          <b class="font-semibold text-ink dark:text-night-fg">{{ counts.cited }}</b>
          cited in the surviving review.
        </p>
      </div>
      <input v-model="query" type="search" placeholder="filter by title, author, venue"
             class="control w-full max-w-[16rem] !py-1.5 text-[0.82rem]"
             aria-label="Filter papers" />
    </header>

    <div v-if="!papers.length" class="panel-note">
      No corpus in this payload. The Retriever writes
      <code class="tag-mono">corpus.json</code> once it has run.
    </div>

    <template v-else>
      <div class="mb-3 flex flex-wrap items-center gap-1">
        <button
          v-for="v in VIEWS" :key="v.key" type="button" :title="v.hint"
          class="rounded-lg px-2.5 py-1 text-[0.78rem] font-medium transition"
          :class="view === v.key
            ? 'bg-accent text-white shadow-card'
            : 'text-ink-dim hover:bg-paper-sunk hover:text-ink dark:text-night-dim dark:hover:bg-night-sunk dark:hover:text-night-fg'"
          :aria-pressed="view === v.key"
          @click="view = v.key"
        >{{ v.label }} <span class="opacity-70">{{ v.n }}</span></button>

        <p v-if="profile"
           class="ml-auto flex flex-wrap items-center gap-x-3 text-[0.72rem]
                  text-ink-dim dark:text-night-dim">
          <span>{{ profile.span }}</span>
          <span v-for="[src, n] in profile.sources" :key="src">· {{ n }} {{ src }}</span>
          <span v-if="profile.preprints">· {{ profile.preprints }} preprints</span>
        </p>
      </div>

      <p v-if="!rows.length" class="panel-note py-4 text-center">
        Nothing matches. <button class="link" @click="query = ''; view = 'all'">
          Show the whole corpus</button>.
      </p>

      <ul class="scroll-soft -mr-1 max-h-[46vh] space-y-1.5 overflow-y-auto pr-1">
        <li v-for="p in rows" :key="p.paper_id"
            class="rounded-xl border border-paper-line bg-paper p-3 transition
                   hover:border-accent/40 hover:shadow-card
                   dark:border-night-line dark:bg-night">
          <div class="flex items-start gap-2">
            <p class="min-w-0 flex-1 text-[0.87rem] font-medium leading-snug">
              {{ p.title || '(untitled)' }}
            </p>
            <span v-if="p.cites"
                  class="pill shrink-0 bg-supported/15 text-supported dark:text-supported-lite"
                  :title="`${p.cites} surviving claims cite this paper`">
              {{ p.cites }} cited
            </span>
            <span v-if="p.dropped"
                  class="pill shrink-0 bg-unsupported/15 text-unsupported dark:text-unsupported-lite"
                  :title="`${p.dropped} claims citing this paper were dropped as unsupported`">
              {{ p.dropped }} dropped
            </span>
          </div>

          <p v-if="(p.authors || []).length"
             class="mt-1 truncate text-[0.76rem] text-ink-dim dark:text-night-dim">
            {{ p.authors.slice(0, 4).join(', ')
            }}<template v-if="p.authors.length > 4"> et al.</template>
          </p>

          <div class="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1
                      text-[0.72rem] text-ink-dim dark:text-night-dim">
            <span v-if="p.venue" class="max-w-[22rem] truncate">{{ p.venue }}</span>
            <span v-if="p.year">· {{ p.year }}</span>
            <span v-if="p.citation_count != null"
                  title="citations, per OpenAlex">· {{ num(p.citation_count) }} cites</span>
            <span v-if="p.read" class="pill bg-accent-soft text-accent dark:text-accent-lite"
                  title="The Extractor pulled structured fields from this paper">read</span>
            <span v-if="p.is_preprint"
                  class="pill bg-replan/15 text-replan dark:text-replan-lite">preprint</span>
            <a v-if="p.doi" :href="`https://doi.org/${p.doi}`" target="_blank"
               rel="noopener noreferrer" class="link ml-auto font-mono">
              {{ p.doi }} ↗
            </a>
            <a v-else-if="p.url" :href="p.url" target="_blank" rel="noopener noreferrer"
               class="link ml-auto">source ↗</a>
            <span v-else class="ml-auto italic">no DOI</span>
          </div>
        </li>
      </ul>

      <p class="panel-note mt-3">
        <template v-if="truncated">
          {{ num(truncated) }} more papers are in
          <code class="tag-mono">corpus.json</code> but not in this payload — it
          carries every cited and every read paper, then fills to 200.
        </template>
        <template v-else>
          Abstracts only: {{ profile ? profile.abstracts : 0 }} of
          {{ counts.all }} papers here carry one, and no full text was fetched —
          which is why a claim can be scored PARTIAL at best.
        </template>
      </p>
    </template>
  </section>
</template>
