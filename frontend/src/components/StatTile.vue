<script setup>
// One metric. Used in a grid on the run page and on the dashboard, so the two
// cannot render the same number in two different sizes.
//
// `hint` is a title, not a tooltip component: every number on this app's
// metric strip is derived from something, and a reader who wants to know WHAT
// should not have to open trace.jsonl to find out.
defineProps({
  value: { type: [String, Number], default: '—' },
  label: { type: String, required: true },
  hint: { type: String, default: '' },
  tone: { type: String, default: 'plain' },   // plain | good | warn | bad | accent
  sub: { type: String, default: '' },
})

const TONE = {
  plain: 'text-ink dark:text-night-fg',
  good: 'text-supported dark:text-supported-lite',
  warn: 'text-replan dark:text-replan-lite',
  bad: 'text-unsupported dark:text-unsupported-lite',
  accent: 'text-accent dark:text-accent-lite',
}
</script>

<template>
  <div class="stat" :title="hint || undefined">
    <span class="stat-value" :class="TONE[tone] || TONE.plain">{{ value }}</span>
    <span class="stat-label">{{ label }}</span>
    <span v-if="sub"
          class="mt-0.5 block truncate text-[0.68rem] text-ink-faint dark:text-night-faint">
      {{ sub }}
    </span>
  </div>
</template>
