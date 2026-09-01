<script setup>
// The run, in one card: what was asked, what came back, and what it cost.
//
// New 2026-08-30. The header previously carried three counts (kept, dropped,
// grounded) and that was the whole of the run's context — the question itself
// was nowhere on the page, so a screenshot of a finished run did not say what
// the run had been asked. Everything here is read from `trace.jsonl` via
// runStats.digest(), which is the same record every report figure is derived
// from, so a panel and a figure cannot disagree.
import { computed } from 'vue'
import StatTile from './StatTile.vue'
import { ago, ms, num, pct, stamp } from '../lib/format.js'

const props = defineProps({
  runId: { type: String, default: '' },
  result: { type: Object, default: null },
  digest: { type: Object, required: true },
  busy: Boolean,
})

const question = computed(
  () => props.result?.question || props.digest.question || '',
)

const grounding = computed(() =>
  props.result?.grounding_score ?? props.digest.verify?.grounding ?? null,
)

const kept = computed(() => props.result?.counts?.verified ?? null)
const dropped = computed(() => props.result?.counts?.dropped ?? null)

/** The composition of the verdicts, as one bar. Reads left to right in the
 *  order a claim survives: supported, partial, then the two ways of failing. */
const composition = computed(() => {
  const c = props.result?.counts || {}
  const rows = [
    { key: 'supported', n: c.supported || 0, cls: 'bg-supported' },
    { key: 'partial', n: c.partial || 0, cls: 'bg-partial' },
    { key: 'contradicted', n: c.contradicted || 0, cls: 'bg-contradicted' },
    {
      key: 'unsupported',
      // `dropped` counts everything removed; the contradicted ones are already
      // named above, so subtracting keeps the bar summing to the total.
      n: Math.max(0, (c.dropped || 0) - (c.contradicted || 0)),
      cls: 'bg-unsupported',
    },
  ].filter((r) => r.n > 0)
  const total = rows.reduce((s, r) => s + r.n, 0)
  return { rows, total }
})

const status = computed(() => {
  if (props.busy) return { label: 'running', cls: 'bg-replan/15 text-replan dark:text-replan-lite' }
  const s = props.result?.status
  if (s === 'complete') return { label: 'complete', cls: 'bg-supported/15 text-supported dark:text-supported-lite' }
  if (s === 'failed') return { label: 'failed', cls: 'bg-unsupported/15 text-unsupported dark:text-unsupported-lite' }
  return { label: s || 'idle', cls: 'pill-soft' }
})

const DECISION_CLS = {
  WRITE: 'bg-write/15 text-write dark:text-write-lite',
  RETRIEVE: 'bg-retrieve/15 text-retrieve dark:text-retrieve-lite',
  REPLAN: 'bg-replan/15 text-replan dark:text-replan-lite',
}

/** Why the Critic said what it said, on the chip itself rather than only in a
 *  title — a decision without its reason is a claim, not evidence. */
const chain = computed(() =>
  props.digest.decisions.length
    ? props.digest.decisions
    : (props.result?.decisions || []).map((d) => ({ decision: d, reasons: [] })),
)

function copyId() {
  navigator.clipboard?.writeText(props.runId).catch(() => {})
}
</script>

<template>
  <section class="panel panel-pad">
    <!-- Nothing open yet. Say what to do rather than rendering an empty grid. -->
    <div v-if="!runId" class="py-6 text-center">
      <p class="text-[0.95rem] font-medium text-ink dark:text-night-fg">
        No run open.
      </p>
      <p class="panel-note mx-auto mt-1.5 max-w-md">
        Ask a question on the left to start one, or pick a previous run to
        replay it — a finished run replays exactly as a live one does, because
        the SSE stream reads the same <code class="tag-mono">trace.jsonl</code>
        either way.
      </p>
    </div>

    <template v-else>
      <div class="panel-head">
        <div class="min-w-0">
          <h2 class="panel-title">
            <span class="panel-index">0</span> Run
          </h2>
          <p class="mt-2 max-w-3xl text-[1.02rem] font-medium leading-snug
                    text-ink dark:text-night-fg">
            {{ question || 'This run’s trace records no question.' }}
          </p>
        </div>
        <span class="pill" :class="status.cls">
          <span v-if="busy" class="h-1.5 w-1.5 animate-pulse-ring rounded-full bg-replan" />
          {{ status.label }}
        </span>
      </div>

      <div class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5
                  text-[0.74rem] text-ink-dim dark:text-night-dim">
        <button class="tag-mono transition hover:text-accent"
                :title="`Copy run id — ${runId}`" @click="copyId">
          {{ runId }}
        </button>
        <span v-if="digest.startedAt" :title="stamp(digest.startedAt)">
          started {{ ago(digest.startedAt) }}
        </span>
        <span v-if="digest.wallMs">· wall clock {{ ms(digest.wallMs) }}</span>
        <span v-if="digest.model">
          · <span class="font-mono">{{ digest.model }}</span>
        </span>
        <span v-if="digest.maxPapers">· cap {{ digest.maxPapers }} papers</span>
      </div>

      <!-- The Critic's decision chain. This is the agentic claim, so it sits
           above the numbers rather than inside a panel further down. -->
      <div v-if="chain.length" class="mt-4">
        <p class="panel-title mb-1.5">Critic decisions</p>
        <div class="chain flex flex-wrap items-center gap-1.5">
          <template v-for="(d, i) in chain" :key="i">
            <span v-if="i" class="text-ink-faint dark:text-night-faint">→</span>
            <span
              class="rounded-md px-2 py-0.5 font-mono text-[0.7rem] font-semibold"
              :class="DECISION_CLS[d.decision]"
              :title="d.reasons.join(' | ')"
            >{{ d.decision }}</span>
          </template>
          <span v-if="digest.maxIterations"
                class="pill-soft ml-1">
            iteration {{ digest.iteration }} of {{ digest.maxIterations }}
          </span>
        </div>
        <p v-if="chain.at(-1)?.reasons?.length"
           class="mt-1.5 text-[0.76rem] italic text-ink-dim dark:text-night-dim">
          last: {{ chain.at(-1).reasons.join(' · ') }}
        </p>
      </div>

      <div class="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile
          :value="num(digest.totals.papers ?? digest.retrieval?.newPapers)"
          label="papers found" tone="accent"
          :sub="digest.retrieval ? `${num(digest.retrieval.withAbstract)} with abstracts` : ''"
          hint="Unique papers in the corpus after dedup by DOI then title" />
        <StatTile
          :value="num(digest.extract?.papers ?? digest.totals.insights)"
          label="papers read"
          :sub="digest.extract?.meanFields != null ? `${digest.extract.meanFields}/8 fields` : ''"
          hint="A run retrieves thousands and extracts a handful — the extraction is the expensive, LLM-metered step" />
        <StatTile
          :value="num(digest.verify?.claims)" label="claims checked"
          :sub="digest.write ? `${digest.write.sections} sections` : ''"
          hint="Every sentence of the draft is decomposed and scored against the paper it cites" />
        <StatTile
          :value="num(kept)" label="kept" tone="good"
          hint="Claims the Verifier could ground in retrieved evidence" />
        <StatTile
          :value="num(dropped)" label="dropped" tone="bad"
          :sub="digest.verify?.threshold != null ? `below ${digest.verify.threshold}` : ''"
          hint="Removed from the review because the evidence did not support them" />
        <StatTile
          :value="pct(grounding, 2)" label="grounding"
          :tone="grounding == null ? 'plain' : grounding >= 0.8 ? 'good' : 'warn'"
          hint="Share of decomposed claims that survived verification" />
      </div>

      <!-- Verdict composition. The proportions are the argument; the legend
           carries the counts so the bar does not need to be measured. -->
      <div v-if="composition.total" class="mt-4">
        <div class="flex h-2 w-full overflow-hidden rounded-full bg-paper-sunk
                    dark:bg-night-sunk">
          <div v-for="r in composition.rows" :key="r.key"
               class="h-full transition-all duration-700" :class="r.cls"
               :style="{ width: `${(r.n / composition.total) * 100}%` }"
               :title="`${r.n} ${r.key}`" />
        </div>
        <div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[0.74rem]
                    text-ink-dim dark:text-night-dim">
          <span v-for="r in composition.rows" :key="r.key"
                class="flex items-center gap-1.5">
            <span class="h-2 w-2 rounded-full" :class="r.cls" />
            <b class="font-semibold text-ink dark:text-night-fg">{{ r.n }}</b>
            {{ r.key }}
          </span>
        </div>
        <p v-if="digest.verify?.abstractOnlyCapped"
           class="panel-note mt-2.5 rounded-lg border-l-[3px] border-partial
                  bg-partial/10 px-3 py-2">
          <strong class="font-semibold text-ink dark:text-night-fg">
            {{ digest.verify.abstractOnlyCapped }} claims were capped at PARTIAL
            by design.</strong>
          The corpus is built from abstracts, and full support needs full text —
          so SUPPORTED is unreachable here, and reporting these as partial is
          the honest ceiling rather than a weak result.
        </p>
      </div>

      <!-- What the run cost. Free tier or not, the token bill is the binding
           constraint on this project, so it belongs on screen. -->
      <div class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t
                  border-paper-hair pt-3 text-[0.76rem] text-ink-dim
                  dark:border-night-hair dark:text-night-dim">
        <span class="panel-title">Cost</span>
        <span>
          <b class="font-semibold text-ink dark:text-night-fg">{{ digest.llm.requests }}</b>
          LLM calls
        </span>
        <span v-if="digest.llm.hitRate != null">
          <b class="font-semibold text-ink dark:text-night-fg">{{ digest.llm.cacheHits }}</b>
          served from cache ({{ pct(digest.llm.hitRate, 0) }})
        </span>
        <span v-if="digest.rank?.rerankMs">rerank {{ ms(digest.rank.rerankMs) }}</span>
        <span v-if="digest.rank?.embedMs">embed {{ ms(digest.rank.embedMs) }}</span>
        <span>· {{ digest.events }} trace events</span>
      </div>
    </template>
  </section>
</template>
