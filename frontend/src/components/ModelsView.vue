<script setup>
// /models — the three trained models, drawn.
//
// The dashboard already says WHICH models were trained and what they scored.
// This route answers the next question an examiner asks, which the dashboard
// cannot: *what is the model*. Every structural figure below is read from the
// checkpoint's own config.json (see the note on each diagram component), so a
// number on this page and a number in the checkpoint cannot drift apart.
//
// Diagrams are hand-authored inline SVG rather than a rendering library.
// Mermaid can draw a flowchart but not a transformer — no repeat-stack, no
// residual, no two-lane encoder/decoder — and it would arrive with its own
// palette to fight the design tokens, plus a re-render on every theme change.
// The SVG is ~9 kB, themes with the rest of the app, and prints.
import AppHeader from './AppHeader.vue'
import StatTile from './StatTile.vue'
import RankerArch from './diagrams/RankerArch.vue'
import SummaryArch from './diagrams/SummaryArch.vue'
import VerifierArch from './diagrams/VerifierArch.vue'

const DIAGRAM = { ranker: RankerArch, summary: SummaryArch, verifier: VerifierArch }

const HEADLINE = [
  { value: '3', label: 'models trained', sub: 'ranker · summariser · verifier', tone: 'accent' },
  { value: '205M', label: 'parameters, combined', sub: '22M + 139M + 44M' },
  { value: 'int8', label: 'deployed precision', sub: 'ONNX, quantised' },
]

const MODELS = [
  {
    id: 'ranker',
    agent: 'Ranker',
    name: 'Cross-encoder ranker',
    base: 'macro-MiniLm',
    params: '22M',
    spec: [
      ['Layers', '6'],
      ['Hidden size', '384'],
      ['Attention heads', '12 · 32 dims each'],
      ['Feed-forward', '1,536 · GELU'],
      ['Vocabulary', '30,522 WordPiece'],
      ['Max sequence', '512 tokens'],
      ['Position', 'absolute, learned'],
      ['Head', 'Linear 384 → 1 · relevance logit'],
    ],
    training: [
      ['Data', 'SciReviewGen — 68,380 train / 7,015 dev pairs'],
      ['Grouping', '2,342 surveys, split by title not by row'],
      ['Negatives', 'BM25 hard : random = 3 : 2'],
      ['Objective', 'binary cross-entropy on (query, abstract)'],
      ['Schedule', '10 epochs · 2e-5 AdamW · batch 32'],
    ],
    results: [
      ['Recall@20 — own bibliography', '0.775'],
      ['nDCG@10 — own bibliography', '0.762'],
      ['Precision@12 — own bibliography', '0.758'],
      ['nDCG@10 — SciReviewGen test', '0.791'],
      ['Relevance control violations', '0 / 15'],
    ],
    latency: '3.27 s per query · 33.4 candidates',
  },
  {
    id: 'summary',
    agent: 'Extractor + Writer',
    name: 'Summary generation',
    base: 'bart',
    params: '139M',
    spec: [
      ['Encoder layers', '6'],
      ['Decoder layers', '6'],
      ['Model dimension', '768'],
      ['Attention heads', '12 per side'],
      ['Feed-forward', '3,072 · GELU'],
      ['Vocabulary', '50,265 BPE'],
      ['Max positions', '1,024'],
      ['Head', 'LM head tied to token embedding'],
    ],
    training: [
      ['Stage 1', 'CNN/DailyMail — general summarisation'],
      ['Stage 2', 'SciReviewGen — chapter-to-citation pairs'],
      ['Objective', 'cross-entropy over the target sequence'],
      ['Decoding', 'beam search'],
      ['Split', 'title-disjoint, as for the ranker'],
    ],
    results: [
      ['ROUGE-1 — SciReviewGen test', '33.82'],
      ['ROUGE-2 — SciReviewGen test', '27.81'],
      ['ROUGE-L — SciReviewGen test', '29.44'],
    ],
    latency: '—',
  },
  {
    id: 'verifier',
    agent: 'Verifier',
    name: 'Claim verifier',
    base: 'deberta',
    params: '44M',
    star: true,
    spec: [
      ['Layers', '6'],
      ['Hidden size', '768'],
      ['Attention heads', '12'],
      ['Feed-forward', '3,072 · GELU'],
      ['Vocabulary', '128,100 SentencePiece'],
      ['Max sequence', '256 tokens'],
      ['Attention', 'disentangled · c→p and p→c'],
      ['Head', 'Linear 768 → 3 · softmax'],
      // Quoted the way the DeBERTa-v3 paper quotes it. The 128k vocabulary makes
      // the embedding table larger than the transformer it feeds, so a reader
      // who sums the three headline figures should know what 44M counts.
      ['Parameters', '44M backbone + 98M embedding'],
    ],
    training: [
      ['Data', 'SciFact — 1,463 train / 272 dev / 628 validation pairs'],
      ['Warm start', 'an existing NLI checkpoint, not from scratch'],
      ['Labels', 'SUPPORT · CONTRADICT · NOT ENOUGH INFO'],
      ['Schedule', '15 epochs · 2e-5 AdamW · batch 32'],
      ['Threshold', '0.7 on P(SUPPORT), biased to precision'],
    ],
    results: [
      ['Macro-F1 — SciFact held out', '0.873'],
      ['Accuracy', '0.881'],
      ['SUPPORT recall', '0.866'],
      ['SUPPORT precision', '0.884'],
      ['NOT ENOUGH INFO F1', '0.859'],
    ],
    latency: '25.4 claims/s · 39.4 ms per claim',
  },
]

</script>

<template>
  <div class="min-h-screen">
    <AppHeader route="/models" />

    <main class="mx-auto max-w-[76rem] px-4 sm:px-6">
      <section class="border-b border-paper-line pb-10 pt-10 dark:border-night-line">
        <p class="text-[0.72rem] font-semibold uppercase tracking-[0.09em]
                  text-accent dark:text-accent-lite">
          Where the machine learning is
        </p>
        <h1 class="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
          Three trained models
        </h1>
        <div class="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <StatTile v-for="s in HEADLINE" :key="s.label" v-bind="s" />
        </div>
      </section>

      <section
        v-for="(m, i) in MODELS" :key="m.id" :id="m.id"
        class="border-b border-paper-line py-12 last:border-0 dark:border-night-line"
      >
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-2">
          <span class="panel-index">{{ i + 1 }}</span>
          <h2 class="text-xl font-semibold tracking-tight">
            {{ m.name }}
            <span v-if="m.star" class="text-accent dark:text-accent-lite">★</span>
          </h2>
          <span class="pill bg-accent-soft text-accent dark:text-accent-lite">
            {{ m.agent }}
          </span>
          <span class="pill-soft">{{ m.params }} parameters</span>
          <code class="tag-mono ml-auto">{{ m.base }}</code>
        </div>

        <!-- The diagram. Given its own card so it reads as a figure rather than
             as decoration, and allowed to scroll on a narrow screen instead of
             shrinking its 10px labels into illegibility. -->
        <figure class="panel mt-4 overflow-hidden">
          <div class="scroll-soft overflow-x-auto p-4 sm:p-5">
            <div class="min-w-[46rem]">
              <component :is="DIAGRAM[m.id]" />
            </div>
          </div>
        </figure>

        <div class="mt-5 grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
          <div class="panel panel-pad">
            <p class="panel-title">Structure</p>
            <dl class="mt-3 divide-y divide-paper-hair dark:divide-night-hair">
              <div v-for="[k, v] in m.spec" :key="k"
                   class="flex items-baseline justify-between gap-4 py-1.5">
                <dt class="text-[0.82rem] text-ink-dim dark:text-night-dim">{{ k }}</dt>
                <dd class="text-right font-mono text-[0.8rem] tabular-nums text-ink
                           dark:text-night-fg">{{ v }}</dd>
              </div>
            </dl>
          </div>

          <div class="panel panel-pad">
            <p class="panel-title">Training</p>
            <dl class="mt-3 divide-y divide-paper-hair dark:divide-night-hair">
              <div v-for="[k, v] in m.training" :key="k"
                   class="flex items-baseline justify-between gap-4 py-1.5">
                <dt class="shrink-0 text-[0.82rem] text-ink-dim dark:text-night-dim">
                  {{ k }}
                </dt>
                <dd class="text-right text-[0.8rem] text-ink dark:text-night-fg">{{ v }}</dd>
              </div>
            </dl>
          </div>
        </div>

        <div class="panel panel-pad mt-4">
          <div class="panel-head">
            <p class="panel-title">Results</p>
            <span v-if="m.latency !== '—'" class="pill-soft">{{ m.latency }}</span>
          </div>
          <div class="scroll-soft mt-3 overflow-x-auto">
            <table class="w-full min-w-[20rem] border-collapse text-[0.82rem]">
              <thead>
                <tr class="border-b border-paper-line dark:border-night-line">
                  <th class="py-2 pr-3 text-left font-semibold">Metric</th>
                  <th class="py-2 pl-3 text-right font-semibold">Measured</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="[metric, measured] in m.results" :key="metric"
                    class="border-b border-paper-hair last:border-0 dark:border-night-hair">
                  <td class="py-2 pr-3 text-ink-dim dark:text-night-dim">{{ metric }}</td>
                  <td class="py-2 pl-3 text-right font-mono font-semibold tabular-nums
                             text-ink dark:text-night-fg">{{ measured }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </main>

    <footer class="mx-auto max-w-[76rem] px-4 pb-10 pt-2 text-[0.74rem]
                   text-ink-faint sm:px-6 dark:text-night-faint">
      Structural figures are read from each checkpoint’s <code class="tag-mono">config.json</code>;
      scores from <code class="tag-mono">eval/</code>. ·
      <a href="/dashboard" class="link">what this project is</a>
    </footer>
  </div>
</template>
