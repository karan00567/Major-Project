<script setup>
// A flow edge between two ArchBoxes.
//
// The arrowhead is drawn as a path rather than an SVG <marker>, because a
// marker inherits the *stroke* of the line it terminates while these lines
// need a filled head — and a marker defined once in a parent would also have
// to be duplicated per theme. A four-point path costs less than either.
const props = defineProps({
  x1: { type: Number, required: true },
  y1: { type: Number, required: true },
  x2: { type: Number, required: true },
  y2: { type: Number, required: true },
  // 'h' straight horizontal, 'v' straight vertical, 'elbow' one right angle.
  kind: { type: String, default: 'h' },
  dashed: { type: Boolean, default: false },
  soft: { type: Boolean, default: false },
  label: { type: String, default: '' },
  labelAbove: { type: Boolean, default: true },
})

const HEAD = 6

const d = (() => {
  if (props.kind === 'elbow') {
    const midX = (props.x1 + props.x2) / 2
    return `M ${props.x1} ${props.y1} H ${midX} V ${props.y2} H ${props.x2}`
  }
  return `M ${props.x1} ${props.y1} L ${props.x2} ${props.y2}`
})()

// The head points along the final segment, which for an elbow is horizontal.
const head = (() => {
  const { x2, y2, kind, x1, y1 } = props
  const vertical = kind === 'v' || (kind !== 'elbow' && x1 === x2)
  if (vertical) {
    const dir = y2 > y1 ? 1 : -1
    return `M ${x2} ${y2} L ${x2 - HEAD} ${y2 - dir * HEAD * 1.4} `
         + `L ${x2 + HEAD} ${y2 - dir * HEAD * 1.4} Z`
  }
  const dir = x2 >= x1 ? 1 : -1
  return `M ${x2} ${y2} L ${x2 - dir * HEAD * 1.4} ${y2 - HEAD} `
       + `L ${x2 - dir * HEAD * 1.4} ${y2 + HEAD} Z`
})()

const labelX = props.kind === 'elbow' ? (props.x1 + props.x2) / 2 : (props.x1 + props.x2) / 2
const labelY = props.labelAbove ? Math.min(props.y1, props.y2) - 7 : Math.max(props.y1, props.y2) + 14
</script>

<template>
  <g>
    <path :d="d" :class="soft ? 'arch-line-soft' : 'arch-line'"
          :stroke-dasharray="dashed ? '5 4' : undefined" />
    <path :d="head" class="arch-arrowhead" />
    <text v-if="label" :x="labelX" :y="labelY" text-anchor="middle" class="arch-cap">
      {{ label }}
    </text>
  </g>
</template>
