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
import AppHeader from './AppHeader.vue'
import StatTile from './StatTile.vue'

const STUDIES = [
  { study: 'Sarol et al.', finding: '39.18% of citation instances contain accuracy errors' },
  { study: 'ALCE', finding: 'best models “lack complete citation support 50% of the time”' },
  { study: 'FActScore', finding: 'ChatGPT factually correct on 58% of atomic claims' },
  { study: 'SurveyGen', finding: '35.84% citation accuracy' },
]

const STAGES = [
  { name: 'Planner', does: 'splits the question into sub-questions and search terms',
    llm: true },
  { name: 'Retriever', does: 'searches OpenAlex and arXiv, dedups by DOI and title',
    llm: false },
  { name: 'Ranker', does: 'hybrid dense + BM25 retrieval, then a cross-encoder',
    llm: false },
  { name: 'Extractor', does: 'pulls method, datasets, metrics and critique per paper',
    llm: true },
  { name: 'Writer', does: 'drafts the survey with inline citations', llm: true },
  { name: 'Verifier', does: 'checks every claim against the paper it cites',
    llm: false },
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
    base: 'deberta-v3-small · 44M',
    data: 'SciFact',
    metric: 'held-out macro-F1',
    stock: 0.516,
    tuned: 0.769,
  },
  {
    name: 'Cross-encoder reranker',
    base: 'MiniLM-L-6 · 22M',
    data: 'SciReviewGen',
    metric: 'Recall@20, own bibliography',
    stock: 0.4815,
    tuned: 0.5926,
  },
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

const LIMITS = [
  {
    head: 'Abstracts, not full text',
    body: 'The corpus is built from abstracts, so a claim is capped at PARTIALLY '
        + 'SUPPORTED by design. Full support needs full text. Reporting these as '
        + 'partial is the ceiling being honest, not the verifier being weak.',
  },
  {
    head: 'Retrieval is the bottleneck',
    body: 'Corpus recall is measured against a hand-curated answer key rather '
        + 'than asserted, and it is the weakest number in the project. That is '
        + 'why the reranker is one of the two things that got trained.',
  },
  {
    head: 'Sentence-level claims',
    body: 'Decomposition is rule-based and sentence-level, so a compound '
        + 'sentence asserting two facts is verified against its strongest '
        + 'evidence and a half-supported sentence can pass. Sub-sentence '
        + 'decomposition needs a generative pass, which was rejected: a model '
        + 'in that seat can invent a claim the draft never made.',
  },
  {
    head: 'A human is in the loop, and is counted',
    body: 'Every dropped claim can be confirmed or disputed by a reviewer, and '
        + 'the judgement is appended to the run trace — including when a human '
        + 'disagrees with the system.',
  },
]

function goToRun() {
  // A full page load, deliberately: there is no router, and landing on / with
  // an empty question box is the point - the button starts nothing, it just
  // takes you to where you type the question.
  window.location.href = '/'
}
</script>

<template>
  <div class="min-h-screen">
    <AppHeader route="/dashboard" />

    <main class="mx-auto max-w-5xl px-5 pb-20 pt-10 sm:px-6">
      <!-- ── hero ─────────────────────────────────────────────────────── -->
      <section class="border-b border-paper-line pb-12 dark:border-night-line">
        <div class="flex flex-wrap items-center gap-2">
          <span class="pill bg-accent-soft text-accent dark:text-accent-lite">
            B.Tech major project · GRIET
          </span>
          <span class="pill-soft">six agents · LangGraph</span>
          <span class="pill-soft">two fine-tuned models · 66M params</span>
          <span class="pill-soft">$0, by construction</span>
        </div>

        <h1 class="mt-5 text-4xl font-semibold tracking-tight sm:text-5xl">
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
            Open the run page →
          </button>
          <p class="text-[0.82rem] text-ink-dim dark:text-night-dim">
            Takes you to the question box. Nothing starts until you say so.
          </p>
        </div>
      </section>

      <!-- ── the recorded run, in numbers ─────────────────────────────── -->
      <section class="border-b border-paper-line py-12 dark:border-night-line">
        <h2 class="text-xl font-semibold">One run, measured</h2>
        <p class="mt-3 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
          The recorded showcase run — the one the demo replays, and the one
          every figure below is read from. Measured 2026-08-28 from
          <code class="tag-mono">outputs/runs/fixture/</code>.
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
              <text :x="85 + i * 158" y="71" text-anchor="middle"
                    class="text-[10px]"
                    :class="s.llm ? 'fill-accent' : 'fill-current'">
                {{ s.llm ? 'LLM' : 'deterministic' }}
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
              no LLM — every gate is arithmetic
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
                <span class="pill-soft !text-[0.62rem]">
                  {{ s.llm ? 'LLM' : 'no LLM' }}
                </span>
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
          Two fine-tuned models, about 66M parameters combined, both trained on
          free Kaggle GPU and both deployed
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
            <p class="mt-0.5 font-mono text-[0.72rem] text-ink-dim dark:text-night-dim">
              {{ m.base }}
            </p>

            <p class="mt-3 text-[0.74rem] uppercase tracking-[0.07em] text-ink-dim
                      dark:text-night-dim">{{ m.metric }}</p>
            <div class="mt-2 space-y-1.5">
              <div class="flex items-center gap-2">
                <span class="w-16 shrink-0 text-[0.74rem] text-ink-dim
                             dark:text-night-dim">stock</span>
                <span class="h-2.5 flex-1 overflow-hidden rounded-full bg-paper-sunk
                             dark:bg-night-sunk">
                  <span class="block h-full rounded-full bg-ink-faint dark:bg-night-faint"
                        :style="{ width: `${m.stock * 100}%` }" />
                </span>
                <span class="w-12 shrink-0 text-right font-mono text-[0.78rem]
                             tabular-nums">{{ m.stock.toFixed(3) }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="w-16 shrink-0 text-[0.74rem] font-semibold">tuned</span>
                <span class="h-2.5 flex-1 overflow-hidden rounded-full bg-paper-sunk
                             dark:bg-night-sunk">
                  <span class="block h-full rounded-full bg-supported"
                        :style="{ width: `${m.tuned * 100}%` }" />
                </span>
                <span class="w-12 shrink-0 text-right font-mono text-[0.78rem]
                             font-semibold tabular-nums text-supported
                             dark:text-supported-lite">{{ m.tuned.toFixed(3) }}</span>
              </div>
            </div>
            <p class="mt-2.5 text-[0.78rem] text-ink-dim dark:text-night-dim">
              +{{ ((m.tuned - m.stock) * 100).toFixed(1) }} points over the stock
              checkpoint on the same held-out data.
            </p>
          </div>
        </div>

        <p class="mt-6 max-w-3xl rounded-xl border-l-4 border-supported
                  bg-supported/10 px-5 py-4 leading-relaxed">
          <strong class="font-semibold">$0 by construction.</strong>
          Only free, open-weight models, enforced in code rather than by
          discipline: <code class="tag-mono">core/llm.py</code> checks an
          <code class="tag-mono">ALLOWED_MODELS</code> constant before any HTTP
          request is even constructed. There is no second line of defence, and
          that is intentional — a second one would make the first optional.
        </p>
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

      <!-- ── limits ───────────────────────────────────────────────────── -->
      <section class="py-12">
        <h2 class="text-xl font-semibold">What it does not claim</h2>
        <p class="mt-3 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
          Stated here because these read far worse when a reviewer finds them
          first. Both figures travel with every run in
          <code class="tag-mono">trace.jsonl</code>.
        </p>
        <div class="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div v-for="l in LIMITS" :key="l.head"
               class="rounded-xl border border-paper-line bg-paper-card p-4
                      dark:border-night-line dark:bg-night-card">
            <h3 class="text-[0.9rem] font-semibold">{{ l.head }}</h3>
            <p class="mt-1.5 text-[0.84rem] leading-relaxed text-ink-dim
                      dark:text-night-dim">{{ l.body }}</p>
          </div>
        </div>
      </section>

      <footer class="border-t border-paper-line pt-8 dark:border-night-line">
        <button class="btn-primary !px-6 !py-3 !text-base shadow-lift" @click="goToRun">
          Open the run page →
        </button>
        <p class="mt-5 text-[0.82rem] leading-relaxed text-ink-dim dark:text-night-dim">
          B.Tech major project, GRIET (DSC06).<br />
          Authors: Abrarullah Mohammed, G. Shashivadan Rao, P. Sreekaran Reddy.
        </p>
      </footer>
    </main>
  </div>
</template>
