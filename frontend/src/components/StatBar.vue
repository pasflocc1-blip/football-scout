<template>
  <div class="stat-bar">
    <span class="stat-label">{{ label }}</span>
    <div class="bar-track">
      <div class="bar-fill" :style="{ width: pct, background: color }" />
    </div>
    <span class="stat-val">{{ display }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: Number, default: null },
})

const display = computed(() => props.value != null ? props.value : '—')
const pct     = computed(() => props.value != null ? `${props.value}%` : '0%')
const color   = computed(() => {
  const v = props.value ?? 0
  if (v >= 80) return 'var(--color-success)'
  if (v >= 65) return 'var(--color-warning)'
  return 'var(--color-danger)'
})
</script>

<style scoped>
.stat-bar {
  display: flex;
  align-items: center;
  gap: .35rem;
  font-size: .75rem;
}
.stat-label {
  width: 26px;
  text-align: right;
  color: var(--color-muted);
  font-weight: 600;
  flex-shrink: 0;
}
.bar-track {
  flex: 1;
  height: 5px;
  background: var(--color-border);
  border-radius: 3px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width .4s ease;
}
.stat-val {
  width: 24px;
  text-align: right;
  color: var(--color-text);
  font-weight: 700;
}
</style>
