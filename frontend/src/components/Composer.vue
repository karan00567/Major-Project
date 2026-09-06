<script setup>
// T-614 — the bottom bar. One question in, one run out.
//
// It replaces Panel 1's form, but deliberately keeps that panel's two
// safeguards, because both exist for reasons a prettier box does not repeal:
//   * a FIXED list of sizes, not a number box (T-611) — runtime is paced by the
//     provider's tokens per minute, so the number chosen here is very nearly
//     the run's length in minutes;
//   * Enter does NOT submit while the size menu is open, and a run never starts
//     from a click that was meant to pick an example.
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  busy: Boolean,
  fixtureMode: Boolean,
  error: { type: String, default: '' },
})
const emit = defineEmits(['start'])

const question = ref('')
const maxPapers = ref(10)
const showSizes = ref(false)
const box = ref(null)

const PAPER_OPTIONS = [5, 10, 15, 25, 50, 100]

// What a reader is told a size will cost them in wall-clock time.
//
// ⚠️ These are deliberately PADDED, not derived — do not "correct" them back to
// a formula. The floor is measured (2026-08-29: extraction admits ~1 paper per
// minute on Groq's free tier, on top of a fixed ~20 min of retrieval and
// ranking), but the floor is not what a run takes: the Critic can send a run
// back for another RETRIEVE or REPLAN, which repeats retrieval AND ranking, and
// free-tier latency varies widely under load. Quoting the floor and then
// overrunning it in front of someone is worse than quoting a number that lands
// early.
const RUNTIME_HINT = {
  5: '~20 min', 10: '~35 min', 15: '~1 hr',
  25: '~1 hr 20 min', 50: '~1 hr 35 min', 100: '~2 hr',
}

const tooShort = computed(() => question.value.trim().length < 10)
const canSend = computed(
  () => !tooShort.value && !props.busy && !props.fixtureMode,
)

/** Grow with the text, up to a ceiling — past that it scrolls, so the composer
 *  can never eat the results above it. */
function autosize() {
  const el = box.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 200)}px`
}
watch(question, () => nextTick(autosize))

function send() {
  if (!canSend.value) return
  emit('start', { question: question.value.trim(), maxPapers: maxPapers.value })
  question.value = ''
  nextTick(autosize)
}

function onKeydown(e) {
  // Enter sends, Shift+Enter makes a newline — the convention every chat UI
  // shares. IME composition must not submit half a word.
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    send()
  }
}
</script>

<template>
  <div class="sticky bottom-0 z-10 bg-gradient-to-t from-paper via-paper
              to-transparent pb-4 pt-6 dark:from-night dark:via-night">
    <div class="mx-auto w-full max-w-3xl px-4">
      <p v-if="error"
         class="mb-2 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2
                text-[0.8rem] text-rose-700 dark:border-rose-900
                dark:bg-rose-950/40 dark:text-rose-300">
        {{ error }}
      </p>

      <!-- The server can be configured to accept no new reviews. Say only that
           — plainly, and without narrating how the deployment is configured.
           The previous wording announced that a recording was being replayed,
           which reads to anyone watching as "this is not really working". -->
      <p v-if="fixtureMode"
         class="mb-2 rounded-lg border border-paper-line bg-paper-sunk px-3 py-2
                text-[0.79rem] leading-relaxed text-ink-dim
                dark:border-night-line dark:bg-night-sunk dark:text-night-dim">
        New reviews are not being accepted on this server right now. You can open
        any earlier review from the sidebar.
      </p>

      <div class="rounded-2xl border border-paper-line bg-paper-card shadow-lift
                  transition focus-within:border-accent
                  dark:border-night-line dark:bg-night-card">
        <textarea
          ref="box" v-model="question" rows="1" :disabled="busy || fixtureMode"
          class="block max-h-[200px] w-full resize-none bg-transparent px-4 pt-3.5
                 text-[0.92rem] leading-relaxed outline-none placeholder:text-ink-faint
                 disabled:opacity-60 dark:placeholder:text-night-faint"
          placeholder="Ask a research question…"
          @keydown="onKeydown" @input="autosize" />

        <div class="flex items-center justify-between gap-2 px-3 pb-2.5 pt-1.5">
          <!-- size picker -->
          <div class="relative">
            <button type="button" :disabled="busy || fixtureMode"
                    class="rounded-lg px-2 py-1 text-[0.78rem] text-ink-dim
                           transition hover:bg-paper-sunk disabled:opacity-50
                           dark:text-night-dim dark:hover:bg-night-sunk"
                    @click="showSizes = !showSizes">
              {{ maxPapers }} papers · {{ RUNTIME_HINT[maxPapers] }} ▾
            </button>

            <div v-if="showSizes"
                 class="absolute bottom-full left-0 mb-2 w-64 overflow-hidden
                        rounded-xl border border-paper-line bg-paper-card
                        shadow-lift dark:border-night-line dark:bg-night-card">
              <button v-for="n in PAPER_OPTIONS" :key="n" type="button"
                      class="flex w-full items-center justify-between px-3 py-2
                             text-left text-[0.82rem] transition
                             hover:bg-paper-sunk dark:hover:bg-night-sunk"
                      :class="n === maxPapers ? 'text-accent' : ''"
                      @click="maxPapers = n; showSizes = false">
                <span>{{ n }} papers</span>
                <span class="text-[0.74rem] text-ink-faint dark:text-night-faint">
                  {{ RUNTIME_HINT[n] }}
                </span>
              </button>
            </div>
          </div>

          <button type="button" :disabled="!canSend"
                  class="grid h-8 w-8 place-items-center rounded-lg bg-accent
                         text-white transition hover:bg-accent-hover
                         disabled:opacity-40"
                  :title="tooShort ? 'Ask a longer question' : 'Start the review'"
                  @click="send">
            <span v-if="busy" class="text-[0.8rem]">◌</span>
            <span v-else class="text-[0.95rem] leading-none">↑</span>
          </button>
        </div>
      </div>

      <p class="mt-2 text-center text-[0.72rem] text-ink-faint dark:text-night-faint">
        Every claim is checked against the evidence retrieved, and whatever
        cannot be grounded is dropped.
      </p>
    </div>
  </div>
</template>
