<script setup>
// T-613 — /dashboard. What this project is, what it is for, and how it works,
// for someone who has never seen it: an examiner, a reviewer, a co-author.
//
// The numbers here are the project's own citations and the project's own
// measurements, not marketing copy. The whole argument for claim-level
// verification rests on the first set, and the credibility of the system rests
// on the second being stated where a reader trips over them rather than buried
// in README §"Results, honestly" — so both are on the page that makes the
// argument. Every figure below is traceable: the four studies to
// `documents/refs.bib`, the run figures to `outputs/runs/fixture/`, the model
// scores to `documents/TRAINING_SPEC.md`.
import { computed } from 'vue'
import AppHeader from './AppHeader.vue'
import StatTile from './StatTile.vue'
import { isAuthed } from '../lib/auth.js'

const STUDIES = [
  { study: 'Sarol et al.', finding: '39.18% of citation instances contain accuracy errors' },
  { study: 'ALCE', finding: 'best models “lack complete citation support 50% of the time”' },
  { study: 'FActScore', finding: 'ChatGPT factually correct on 58% of atomic claims' },
  { study: 'SurveyGen', finding: '35.84% citation accuracy' },
]

const STAGES = [
  { name: 'Planner', does: 'splits the question into sub-questions and search terms' },
  { name: 'Retriever', does: 'searches OpenAlex and arXiv, dedups by DOI and title' },
  { name: 'Ranker', does: 'hybrid dense + BM25 retrieval, then a cross-encoder' },
  { name: 'Extractor', does: 'pulls method, datasets, metrics and critique per paper' },
  { name: 'Writer', does: 'drafts the survey with inline citations' },
  { name: 'Verifier', does: 'checks every claim against the paper it cites' },
]

// The recorded showcase run — outputs/runs/fixture/, the one the demo replays.
// Stated as measurements with a date, because a number without one is a claim.
const RUN = [
  { value: '551', label: 'papers retrieved', sub: 'from 271, after one replan',
    tone: 'accent' },
  { value: '10', label: 'papers read', sub: 'the extraction budget' },
  { value: '22', label: 'claims decomposed', sub: 'from 3 sections' },
  { value: '19 / 3', label: 'kept / dropped', sub: 'every drop is listed',
    tone: 'good' },
  { value: '0.864', label: 'grounding score', sub: 'share that survived',
    tone: 'good' },
  { value: '4', label: 'critic decisions', sub: 'two loops, then write' },
]

// Two fine-tuned models, ~66M parameters combined, both trained on free Kaggle
// GPU and both deployed quantized to int8 on a CPU-only machine.
const MODELS = [
  {
    name: 'Claim verifier',
    parameters: '44M',
    data: 'SciFact',
    metric: 'held-out macro-F1',
    metric_value: 0.873,
  },
  {
    name: 'Cross-encoder reranker',
    parameters: '22M',
    data: 'SciReviewGen',
    metric: 'Recall@20, own bibliography',
    metric_value: 0.775,
  },
  {
    name: 'Summarizer(Used across different agents)',
    parameters: '200M',
    data: 'CNN Daily mail & SciReviewGen',
    metric: 'ROGUE-L',
    metric_value: '30.81',
  }
]

const ARTEFACTS = [
  ['review.md', 'the cited survey'],
  ['claims.json', 'every claim, its verdict, score and evidence span'],
  ['insights.csv', 'per-paper structured extraction'],
  ['refs.bib', 'BibTeX'],
  ['corpus.json', 'every retrieved paper'],
  ['trace.jsonl', 'every agent event — the audit record'],
  ['config.json', 'the resolved config, including which provider served it'],
]

// T-614 — this page is now the landing page ("/"), so its call to action has to
// answer a question it did not used to: is anyone signed in?
//   signed in  -> "Run a review", straight to the question box
//   signed out -> "Log in", to the same place, which shows the sign-in screen
// Both go to /run, because the destination really is the same page; only the
// gate in front of it differs. Reading the session directly (rather than being
// passed a prop) keeps the dashboard usable as a standalone route.
const signedIn = computed(() => isAuthed())
const ctaLabel = computed(() => (signedIn.value ? 'Run a review →' : 'Log in →'))

function goToRun() {
  // A full page load, deliberately: there is no router, and arriving at /run
  // with an empty question box is the point - the button starts nothing, it
  // just takes you to where you type the question.
  window.location.href = '/run'
}
</script>

<template>
  <div class="min-h-screen">
    <AppHeader route="/" />

    <main class="mx-auto max-w-5xl px-5 pb-20 pt-10 sm:px-6">
      <!-- ── hero ─────────────────────────────────────────────────────── -->
      <section class="border-b border-paper-line pb-12 dark:border-night-line">
        <!-- The badge row was removed. It front-loaded provenance and
             implementation trivia — the institution, the framework, the
             parameter count, the budget — before the reader had been told what
             the thing does. The page now opens on the name and the claim. -->
        <h1 class="text-4xl font-semibold tracking-tight sm:text-5xl">
          ResearchGPT
        </h1>
        <p class="mt-3 text-lg text-ink dark:text-night-fg">
          A multi-agent agentic RAG platform for automated literature review.
        </p>
        <p class="mt-4 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
          Give it a research question. It plans sub-questions, searches the
          literature, ranks and extracts what it finds, drafts a cited survey —
          and then
          <strong class="font-semibold text-ink dark:text-night-fg">verifies every
          claim it wrote against the evidence it retrieved, dropping whatever it
          cannot ground.</strong>
        </p>

        <div class="mt-7 flex flex-wrap items-center gap-4">
          <button class="btn-primary !px-6 !py-3 !text-base shadow-lift"
                  @click="goToRun">
            {{ ctaLabel }}
          </button>
        </div>
      </section>

      <!-- ── the recorded run, in numbers ─────────────────────────────── -->
      <section class="border-b border-paper-line py-12 dark:border-night-line">
        <h2 class="text-xl font-semibold">One run, measured</h2>
        <p class="mt-3 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
          A complete run of the system, and the one every figure below is read
          from. Measured 2026-08-28; the artefacts are on disk and every number
          here is derived from that run's own trace.
        </p>
        <div class="mt-6 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
          <StatTile v-for="s in RUN" :key="s.label" v-bind="s" />
        </div>
        <p class="mt-5 max-w-3xl rounded-xl border-l-4 border-accent bg-accent-soft
                  px-5 py-4 leading-relaxed">
          The replan is not cosmetic. The Critic read 271 papers against its
          corpus gate, sent the run back, and the Planner produced
          <strong class="font-semibold">12 new queries with zero repeats</strong>
          — which doubled the corpus. That loop is the difference between an
          agent and a pipeline, and you can watch it happen on the run page.
        </p>
      </section>

      <!-- ── the problem ──────────────────────────────────────────────── -->
      <section class="border-b border-paper-line py-12 dark:border-night-line">
        <h2 class="text-xl font-semibold">The problem</h2>
        <p class="mt-3 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
          A literature review takes weeks, and the obvious fix — ask a language
          model — fails in a specific way:
          <strong class="font-semibold text-ink dark:text-night-fg">it cites
          confidently and wrongly.</strong>
          Four independent measurements say a citation is almost no evidence that
          the sentence attached to it is supported.
        </p>

        <div class="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div v-for="s in STUDIES" :key="s.study"
               class="rounded-xl border border-paper-line bg-paper-card p-4
                      shadow-card transition hover:-translate-y-0.5 hover:shadow-lift
                      dark:border-night-line dark:bg-night-card dark:shadow-none">
            <div class="text-[0.72rem] font-semibold uppercase tracking-[0.09em]
                        text-accent dark:text-accent-lite">{{ s.study }}</div>
            <div class="mt-1.5 text-[0.9rem] leading-relaxed">{{ s.finding }}</div>
          </div>
        </div>

        <p class="mt-6 max-w-3xl rounded-xl border-l-4 border-replan bg-replan/10 px-5 py-4
                  leading-relaxed">
          FActScore's sharpest result:
          <strong class="font-semibold">36.0% of supported and 37.6% of unsupported
          sentences carried citations</strong> — statistically indistinguishable.
          The presence of a citation carries almost no information.
        </p>
        <p class="mt-4 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
          So a system that writes a beautifully cited survey has proved nothing.
          The citation has to be <em>checked</em>, claim by claim.
        </p>
      </section>

      <!-- ── how it works ─────────────────────────────────────────────── -->
      <section class="border-b border-paper-line py-12 dark:border-night-line">
        <h2 class="text-xl font-semibold">How it works</h2>
        <p class="mt-3 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
          Six agents on a LangGraph state machine. The
          <strong class="font-semibold text-ink dark:text-night-fg">Critic is
          visited twice per iteration</strong>: once after the Extractor, where
          its cheap gates run <em>before</em> the Writer spends tokens, and again
          after the Verifier, where the grounding gate finally has a score to
          read. It can send the run back for more evidence or a new plan instead
          of pressing on — that loop is what makes it agentic rather than a
          pipeline.
        </p>

        <div class="scroll-soft mt-8 overflow-x-auto rounded-xl border border-paper-line
                    bg-paper-card p-6 dark:border-night-line dark:bg-night-card">
          <svg viewBox="0 0 980 250"
               class="h-auto w-full min-w-[46rem] text-ink-dim dark:text-night-dim"
               role="img"
               aria-label="Planner, Retriever, Ranker, Extractor, Writer and Verifier in a row, with a Critic below that can loop back to the Retriever or the Planner">
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
                      markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
              </marker>
            </defs>

            <g v-for="(s, i) in STAGES" :key="s.name">
              <rect :x="20 + i * 158" y="30" width="130" height="54" rx="12"
                    class="fill-paper stroke-paper-line dark:fill-night dark:stroke-night-line"
                    stroke-width="1.5" />
              <text :x="85 + i * 158" y="54" text-anchor="middle"
                    class="fill-ink text-[14px] font-semibold dark:fill-night-fg">
                {{ s.name }}
              </text>
              <line v-if="i < STAGES.length - 1"
                    :x1="152 + i * 158" y1="57" :x2="174 + i * 158" y2="57"
                    stroke="currentColor" stroke-width="1.5" marker-end="url(#arrow)" />
            </g>

            <rect x="400" y="168" width="180" height="46" rx="12"
                  class="fill-accent-soft stroke-accent" stroke-width="1.5" />
            <text x="490" y="190" text-anchor="middle"
                  class="fill-ink text-[14px] font-semibold dark:fill-night-fg">Critic</text>
            <text x="490" y="205" text-anchor="middle" class="text-[10px] fill-current">
              every gate is arithmetic
            </text>

            <g class="text-accent" fill="none" stroke="currentColor" stroke-width="1.5"
               stroke-dasharray="5 4">
              <path d="M 875 88 L 875 191 L 588 191" marker-end="url(#arrow)" />
              <path d="M 400 191 L 243 191 L 243 92" marker-end="url(#arrow)" />
            </g>
            <text x="318" y="182" text-anchor="middle"
                  class="fill-accent text-[11px] tracking-wide">RETRIEVE / REPLAN</text>
            <text x="700" y="182" text-anchor="middle"
                  class="fill-accent text-[11px] tracking-wide">grounding checked</text>
          </svg>
        </div>

        <ol class="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <li v-for="(s, i) in STAGES" :key="s.name"
              class="flex gap-3 rounded-lg border border-paper-line px-3 py-2.5
                     transition hover:border-accent/40 hover:shadow-card
                     dark:border-night-line">
            <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center
                         rounded-full bg-accent-soft text-[0.7rem] font-bold
                         text-accent dark:text-accent-lite">
              {{ i + 1 }}
            </span>
            <span class="min-w-0">
              <span class="flex items-baseline gap-2">
                <span class="text-[0.86rem] font-semibold">{{ s.name }}</span>
              </span>
              <span class="block text-[0.82rem] leading-relaxed text-ink-dim
                           dark:text-night-dim">{{ s.does }}</span>
            </span>
          </li>
        </ol>

        <p class="mt-6 max-w-3xl leading-relaxed text-ink-dim dark:text-night-dim">
          <strong class="font-semibold text-ink dark:text-night-fg">Two components
          are deterministic on purpose.</strong>
          The Critic makes no model call — every gate is arithmetic, and a loop
          that spends tokens deciding whether to spend tokens is the worst place
          for a generative step. Claim decomposition is rule-based for the same
          reason, plus a sharper one: a model in that seat can <em>invent</em> a
          claim the draft never made.
        </p>
        <p class="mt-4 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
          Every claim the Writer makes is decomposed and scored against the paper
          it cites. Anything that cannot be grounded is
          <strong class="font-semibold text-ink dark:text-night-fg">dropped from
          the review</strong> and listed separately, where a human confirms or
          overrides the decision — the review you read is the part that survived.
        </p>
      </section>

      <!-- ── the machine learning ─────────────────────────────────────── -->
      <section class="border-b border-paper-line py-12 dark:border-night-line">
        <h2 class="text-xl font-semibold">Where the machine learning is</h2>
        <p class="mt-3 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
          Three models, trained on
          Kaggle GPU and both deployed
          <strong class="font-semibold text-ink dark:text-night-fg">quantized to
          int8 on a CPU-only machine.</strong>
          The generative agents are deliberately <em>not</em> fine-tuned. The
          thesis is Valsci's — architecture beats model scale — so the training
          went to the two real bottlenecks: retrieval quality and claim
          grounding.
        </p>

        <div class="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div v-for="m in MODELS" :key="m.name"
               class="rounded-xl border border-paper-line bg-paper-card p-4 shadow-card
                      dark:border-night-line dark:bg-night-card dark:shadow-none">
            <div class="flex items-baseline justify-between gap-2">
              <h3 class="text-[0.95rem] font-semibold">{{ m.name }}</h3>
              <span class="pill-soft">{{ m.data }}</span>
            </div>
            

            <p class="mt-3 text-[0.74rem] uppercase tracking-[0.07em] text-ink-dim
                      dark:text-night-dim">{{ m.metric }}</p>
            <div class="mt-2 space-y-1.5">
              <div class="flex items-center gap-2">
                <span class="h-2.5 flex-1 overflow-hidden rounded-full bg-paper-sunk
                             dark:bg-night-sunk">
                  <!-- `metric_value` is a 0-1 fraction for two of these and a
                       0-100 score for the third, so the bar normalises before
                       it draws and clamps, or a value like 30.81 would render
                       as a 3081% wide fill. -->
                  <span class="block h-full rounded-full bg-accent"
                        :style="{ width: `${Math.min(100, Number(m.metric_value) <= 1
                                    ? Number(m.metric_value) * 100
                                    : Number(m.metric_value))}%` }" />
                </span>
                <span class="w-12 shrink-0 text-right font-mono text-[0.78rem]
                             tabular-nums">{{ m.metric_value }}</span>
              </div>
            </div>
          </div>
        </div>

        
      </section>

      <!-- ── what a run leaves behind ─────────────────────────────────── -->
      <section class="border-b border-paper-line py-12 dark:border-night-line">
        <h2 class="text-xl font-semibold">What a run leaves behind</h2>
        <p class="mt-3 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
          Every run writes a directory of typed artefacts. There is no database
          in the critical path: the artefact directory
          <em>is</em> the record, and the app reconstructs a run from it — which
          is why a finished run replays in the browser exactly as a live one
          streams.
        </p>
        <ul class="mt-5 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          <li v-for="[file, what] in ARTEFACTS" :key="file"
              class="flex items-baseline gap-2.5 rounded-lg border border-paper-line
                     px-3 py-2 dark:border-night-line">
            <code class="shrink-0 font-mono text-[0.78rem] text-accent
                         dark:text-accent-lite">{{ file }}</code>
            <span class="text-[0.82rem] text-ink-dim dark:text-night-dim">{{ what }}</span>
          </li>
        </ul>
        <p class="mt-5 max-w-3xl rounded-xl border-l-4 border-accent bg-accent-soft
                  px-5 py-4 leading-relaxed">
          <code class="tag-mono">trace.jsonl</code> is the single source of truth
          for what happened. The live stream tails it, the human overrides append
          to it, and every figure in the report is derived from it — so a browser
          panel and a report figure cannot disagree.
        </p>
      </section>

      <footer class="border-t border-paper-line pt-8 dark:border-night-line">
        <button class="btn-primary !px-6 !py-3 !text-base shadow-lift" @click="goToRun">
          {{ ctaLabel }}
        </button>
        <p class="mt-5 text-[0.82rem] leading-relaxed text-ink-dim dark:text-night-dim">
          B.Tech major project, GRIET (DSC06).<br />
          Authors: Abrarullah Mohammed, G. Shashivadan Rao, P. Sreekaran Reddy.
        </p>
      </footer>
    </main>
  </div>
</template>
