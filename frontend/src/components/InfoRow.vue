<template>
  <div class="info-row">
    <span class="info-label">{{ label }}</span>
    <span class="info-value">{{ value || '—' }}</span>
  </div>
</template>

<script setup>
defineProps({ label: String, value: [String, Number] })
</script>

<style scoped>
.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: .45rem 0;
  border-bottom: 1px solid var(--color-border);
  font-size: .9rem;
}
.info-row:last-child { border-bottom: none; }
.info-label { color: var(--color-muted); }
.info-value { font-weight: 600; }
</style>
