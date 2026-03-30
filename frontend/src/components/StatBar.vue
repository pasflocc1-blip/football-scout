<template>
  <!-- title="..." usa il tooltip nativo del browser — funziona su tutti i browser -->
  <div class="stat-bar" :title="fullLabel">
    <span class="stat-label">{{ label }}</span>
    <div class="bar-track">
      <div
        v-if="props.value != null"
        class="bar-fill"
        :style="{ width: pct, background: color }"
      />
      <div v-else class="bar-empty" />
    </div>
    <span class="stat-val" :class="{ 'nd': props.value == null }">{{ display }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/* Tooltip nativo (title=""): appare dopo ~1s di hover su tutti i browser.
   Non serve libreria esterna. */
const FULL_LABELS = {
  PAC: 'Velocità — Pace',
  TIR: 'Tiro — Shooting',
  PAS: 'Passaggio — Passing',
  DRI: 'Dribbling',
  DIF: 'Difesa — Defending',
  FIS: 'Fisico — Physical',
}

const props = defineProps({
  label: { type: String, required: true },
  value: { type: Number, default: null },
})

const fullLabel = computed(() => FULL_LABELS[props.label] ?? props.label)
const display   = computed(() => props.value != null ? props.value : 'N/D')
const pct       = computed(() => props.value != null ? `${Math.min(props.value, 100)}%` : '0%')
const color     = computed(() => {
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
  cursor: help;   /* cursore a punto interrogativo → indica tooltip disponibile */
}
.stat-bar-wrap {
  display: flex;
  align-items: center;
  gap: .4rem;
}
.stat-label {
  font-size: .68rem;
  font-weight: 700;
  color: var(--color-text);     /* ← era var(--color-muted) */
  width: 2.2rem;
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
.bar-empty {
  height: 100%;
  width: 100%;
  background: repeating-linear-gradient(
    90deg,
    var(--color-border) 0px,
    var(--color-border) 4px,
    transparent 4px,
    transparent 8px
  );
  opacity: 0.5;
}
.stat-val {
  width: 28px;
  text-align: right;
  color: var(--color-text);
  font-weight: 700;
}
.stat-value {
  font-size: .72rem;
  font-weight: 700;
  color: var(--color-text);     /* ← era var(--color-muted) con opacity .6 */
  /* opacity: 0.6  ← RIMUOVERE questa riga */
  min-width: 2rem;
  text-align: right;
}
.stat-val.nd {
  font-size: .68rem;
  font-weight: 500;
  color: var(--color-muted);
  opacity: 0.6;
}
</style>