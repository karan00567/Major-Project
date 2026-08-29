<script setup>
// T-613 — /dashboard. What this project is, what it is for, and how it works,
// for someone who has never seen it: an examiner, a reviewer, a co-author.
//
// The numbers here are the project's own citations (README, "the problem"),
// not marketing copy. The whole argument for claim-level verification rests on
// them, so they belong on the page that makes the argument.
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

function goToRun() {
  // A full page load, deliberately: there is no router, and landing on / with
  // an empty question box is the point - the button starts nothing, it just
  // takes you to where you type the question.
  window.location.href = '/'
}
</script>

<template>
  <main class="mx-auto max-w-5xl px-6 pb-20 pt-14">
    <section class="border-b border-paper-line pb-12 dark:border-night-line">
      <span class="inline-block rounded-full bg-accent-soft px-3 py-1 text-[0.7rem]
                   font-semibold uppercase tracking-[0.1em] text-accent">
        B.Tech major project · GRIET
      </span>
      <h1 class="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
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
        <button class="btn-primary !px-6 !py-3 !text-base shadow-lift" @click="goToRun">
          Run literature review →
        </button>
        <p class="text-[0.82rem] text-ink-dim dark:text-night-dim">
          Takes you to the run page. Nothing starts until you say so.
        </p>
      </div>
    </section>

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

      <div class="mt-6 grid gap-3 sm:grid-cols-2">
        <div v-for="s in STUDIES" :key="s.study"
             class="rounded-xl border border-paper-line bg-paper-card p-4
                    shadow-card transition hover:shadow-lift
                    dark:border-night-line dark:bg-night-card dark:shadow-none">
          <div class="text-[0.72rem] font-semibold uppercase tracking-[0.09em]
                      text-accent">{{ s.study }}</div>
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

    <section class="border-b border-paper-line py-12 dark:border-night-line">
      <h2 class="text-xl font-semibold">How it works</h2>
      <p class="mt-3 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
        Six agents in a loop. The Critic reads the state after retrieval and
        again after verification, and can send the run back for more evidence
        or a new plan instead of pressing on — that loop is what makes it
        agentic rather than a pipeline.
      </p>

      <div class="scroll-soft mt-8 overflow-x-auto rounded-xl border border-paper-line
                  bg-paper-card p-6 dark:border-night-line dark:bg-night-card">
        <svg viewBox="0 0 980 250"
             class="h-auto w-full min-w-[46rem] text-ink-dim dark:text-night-dim"
             role="img"
             aria-label="Planner, Retriever, Ranker, Extractor, Writer and Verifier in a row, with a Critic below that can loop back to the Retriever">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
                    markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
            </marker>
          </defs>

          <g v-for="(s, i) in STAGES" :key="s.name">
            <rect :x="20 + i * 158" y="34" width="130" height="46" rx="10"
                  class="fill-paper stroke-paper-line dark:fill-night dark:stroke-night-line"
                  stroke-width="1.5" />
            <text :x="85 + i * 158" y="62" text-anchor="middle"
                  class="fill-ink text-[14px] font-semibold dark:fill-night-fg">
              {{ s.name }}
            </text>
            <line v-if="i < STAGES.length - 1"
                  :x1="152 + i * 158" y1="57" :x2="174 + i * 158" y2="57"
                  stroke="currentColor" stroke-width="1.5" marker-end="url(#arrow)" />
          </g>

          <rect x="400" y="168" width="180" height="46" rx="10"
                class="fill-accent-soft stroke-accent" stroke-width="1.5" />
          <text x="490" y="196" text-anchor="middle"
                class="fill-ink text-[14px] font-semibold dark:fill-night-fg">Critic</text>

          <g class="text-accent" fill="none" stroke="currentColor" stroke-width="1.5"
             stroke-dasharray="5 4">
            <path d="M 875 84 L 875 191 L 588 191" marker-end="url(#arrow)" />
            <path d="M 400 191 L 243 191 L 243 88" marker-end="url(#arrow)" />
          </g>
          <text x="318" y="182" text-anchor="middle"
                class="fill-accent text-[11px] tracking-wide">RETRIEVE / REPLAN</text>
          <text x="700" y="182" text-anchor="middle"
                class="fill-accent text-[11px] tracking-wide">grounding checked</text>
        </svg>
      </div>

      <ol class="mt-6 grid gap-2 sm:grid-cols-2">
        <li v-for="(s, i) in STAGES" :key="s.name"
            class="flex gap-3 rounded-lg border border-paper-line px-3 py-2.5
                   dark:border-night-line">
          <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center
                       rounded-full bg-accent-soft text-[0.7rem] font-bold text-accent">
            {{ i + 1 }}
          </span>
          <span>
            <span class="block text-[0.86rem] font-semibold">{{ s.name }}</span>
            <span class="block text-[0.82rem] leading-relaxed text-ink-dim
                         dark:text-night-dim">{{ s.does }}</span>
          </span>
        </li>
      </ol>

      <p class="mt-6 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
        Every claim the Writer makes is decomposed and scored against the paper
        it cites. Anything that cannot be grounded is
        <strong class="font-semibold text-ink dark:text-night-fg">dropped from
        the review</strong> and listed separately, where a human confirms or
        overrides the decision — the review you read is the part that survived.
      </p>
    </section>

    <section class="py-12">
      <h2 class="text-xl font-semibold">What it does not claim</h2>
      <p class="mt-3 max-w-2xl leading-relaxed text-ink-dim dark:text-night-dim">
        The survey is built from abstracts, so claims are capped at
        <em>partially supported</em> by design — full support needs full text.
        Retrieval quality is the current bottleneck and is measured openly
        against a hand-curated answer key rather than asserted. Both figures
        travel with every run in
        <code class="rounded bg-paper-line/60 px-1 py-0.5 font-mono text-[0.85em]
                     dark:bg-night-line/60">trace.jsonl</code>.
      </p>
    </section>

    <footer class="border-t border-paper-line pt-8 dark:border-night-line">
      <button class="btn-primary !px-6 !py-3 !text-base shadow-lift" @click="goToRun">
        Run literature review →
      </button>
      <p class="mt-4 text-[0.82rem] text-ink-dim dark:text-night-dim">
        B.Tech major project, GRIET (DSC06).
        Authors: Abrarullah Mohammed, G. Shashivadan Rao, P. Sreekaran Reddy.
      </p>
    </footer>
  </main>
</template>
