<script setup>
// Three states rather than two, because "follow the OS" is a real answer and a
// two-state switch silently discards it the first time it is touched.
import { computed } from 'vue'
import { mode, setMode } from '../lib/theme.js'

const OPTIONS = [
  { value: 'light', label: 'Light', glyph: '☀' },
  { value: 'system', label: 'System', glyph: '◐' },
  { value: 'dark', label: 'Dark', glyph: '☾' },
]

const current = computed(() => mode.value)
</script>

<template>
  <div
    class="flex items-center gap-0.5 rounded-lg border border-paper-line
           bg-paper-card p-0.5 dark:border-night-line dark:bg-night-card"
    role="radiogroup"
    aria-label="Colour theme"
  >
    <button
      v-for="o in OPTIONS"
      :key="o.value"
      type="button"
      role="radio"
      :aria-checked="current === o.value"
      :title="`${o.label} theme`"
      class="grid h-6 w-7 place-items-center rounded-md text-[0.8rem] leading-none
             transition"
      :class="current === o.value
        ? 'bg-accent text-white shadow-card'
        : 'text-ink-dim hover:bg-paper-sunk hover:text-ink dark:text-night-dim dark:hover:bg-night-sunk dark:hover:text-night-fg'"
      @click="setMode(o.value)"
    >
      <span aria-hidden="true">{{ o.glyph }}</span>
      <span class="sr-only">{{ o.label }}</span>
    </button>
  </div>
</template>
