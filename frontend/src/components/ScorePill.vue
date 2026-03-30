<template>
  <div class="score-pill" :style="{ borderColor: color, color }">
    <span>{{ label }}</span>
    <strong>{{ value ? value.toFixed(0) : '—' }}</strong>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: Number, default: null },
})

const color = computed(() => {
  const v = props.value ?? 0
  if (v >= 80) return 'var(--color-success)'
  if (v >= 65) return 'var(--color-warning)'
  return 'var(--color-danger)'
})
</script>

<style scoped>
.score-pill {
  display: inline-flex;
  align-items: center;
  gap: .3rem;
  padding: .2rem .55rem;
  border-radius: 999px;
  border: 2px solid;
  font-size: .78rem;
  background: rgba(255,255,255,.04);
}
.score-pill strong { font-size: .85rem; }
</style>
