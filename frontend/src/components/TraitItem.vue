<template>
  <div class="trait-item">
    <div style="display:flex; align-items:center; gap:.5rem; flex:1">
      <span class="priority-dot" :style="`background:${priorityColor}`" />
      <span style="font-size:.9rem">{{ trait.description }}</span>
    </div>
    <button class="del-btn" @click="$emit('delete', trait)">✕</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ trait: Object })
defineEmits(['delete'])

const priorityColor = computed(() => {
  const colors = { 1: 'var(--color-danger)', 2: 'var(--color-warning)', 3: 'var(--color-success)' }
  return colors[props.trait.priority] ?? 'var(--color-muted)'
})
</script>

<style scoped>
.trait-item {
  display: flex;
  align-items: center;
  gap: .5rem;
  padding: .55rem .6rem;
  border-radius: 8px;
  margin-bottom: .35rem;
  background: rgba(255,255,255,.03);
  border: 1px solid var(--color-border);
}
.priority-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.del-btn {
  background: transparent;
  border: none;
  color: var(--color-muted);
  cursor: pointer;
  font-size: .85rem;
  padding: .1rem .4rem;
  border-radius: 4px;
  transition: color .15s, background .15s;
}
.del-btn:hover { color: var(--color-danger); background: rgba(239,68,68,.1); }
</style>
