<script setup>
// One block in a model-architecture diagram.
//
// Geometry is hand-placed rather than laid out, because these are three
// *specific* architectures and an auto-layout would put the residual arcs
// somewhere arbitrary. Keeping the box a component means the three diagrams
// cannot drift apart in corner radius, text baseline or stroke weight.
//
// `stack` draws two offset cards behind the front one — the visual shorthand
// for "this block repeats N times", which is the single most important thing
// to read correctly about a transformer.
const props = defineProps({
  x: { type: Number, required: true },
  y: { type: Number, required: true },
  w: { type: Number, required: true },
  h: { type: Number, default: 74 },
  title: { type: String, default: '' },
  // Up to three lines under the title. Strings ending in `~` render monospaced,
  // which is how token sequences and tensor shapes are marked.
  lines: { type: Array, default: () => [] },
  tone: { type: String, default: 'plain' },
  stack: { type: Boolean, default: false },
  badge: { type: String, default: '' },
})

const TONE = {
  plain: 'arch-box',
  muted: 'arch-box-muted',
  accent: 'arch-box-accent',
  good: 'arch-box-good',
  warn: 'arch-box-warn',
  bad: 'arch-box-bad',
  alt: 'arch-box-alt',
}

const cls = TONE[props.tone] || TONE.plain
const cx = props.x + props.w / 2
// Title sits higher when there are lines under it, centred when it is alone.
const titleY = props.lines.length ? props.y + 24 : props.y + props.h / 2 + 4.5
const lineY = (i) => props.y + 42 + i * 15
const isMono = (s) => s.endsWith('~')
const text = (s) => (isMono(s) ? s.slice(0, -1) : s)
</script>

<template>
  <g>
    <template v-if="stack">
      <rect :x="x + 9" :y="y - 9" :width="w" :height="h" rx="10" :class="cls" opacity="0.45" />
      <rect :x="x + 4.5" :y="y - 4.5" :width="w" :height="h" rx="10" :class="cls" opacity="0.7" />
    </template>
    <rect :x="x" :y="y" :width="w" :height="h" rx="10" :class="cls" />

    <text v-if="title" :x="cx" :y="titleY" text-anchor="middle" class="arch-title">
      {{ title }}
    </text>
    <text
      v-for="(l, i) in lines" :key="i"
      :x="cx" :y="lineY(i)" text-anchor="middle"
      :class="isMono(l) ? 'arch-mono' : 'arch-sub'"
    >{{ text(l) }}</text>

    <!-- The repeat count rides the top-right corner of the front card, where a
         reader looking at the stack effect is already looking. -->
    <g v-if="badge">
      <rect :x="x + w - 42" :y="y - 11" width="38" height="20" rx="10" :class="cls" />
      <text :x="x + w - 23" :y="y + 3" text-anchor="middle" class="arch-title"
            style="font-size: 11px">{{ badge }}</text>
    </g>
  </g>
</template>
