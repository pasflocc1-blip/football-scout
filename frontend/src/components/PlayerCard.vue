<template>
  <div class="player-card card">

    <div class="player-header">
      <div class="player-info">
        <h3 class="player-name">{{ player.name }}</h3>
        <p class="player-sub">{{ player.club || 'Club N/D' }} · {{ player.nationality || '?' }}</p>
      </div>
      <div class="player-meta">
        <!-- Badge: testo leggibile, tooltip con codice tecnico -->
        <span class="badge badge-blue pos-badge" :title="positionCode">
          {{ positionLabel }}
        </span>
        <p class="player-age">{{ player.age }} anni · {{ footLabel }}</p>
      </div>
    </div>

    <!-- Stats: il tooltip è gestito dentro StatBar (cursor: help) -->
    <div class="stats-grid">
      <StatBar v-for="s in baseStats" :key="s.label" :label="s.label" :value="s.value" />
    </div>

    <div v-if="hasScores" class="scores-row">
      <ScorePill v-if="player.heading_score"   label="🎯 Testa"   :value="player.heading_score" />
      <ScorePill v-if="player.build_up_score"  label="⬆ Gioco"  :value="player.build_up_score" />
      <ScorePill v-if="player.defensive_score" label="🛡 Difesa" :value="player.defensive_score" />
    </div>

    <div v-if="player.xg_per90 || player.xa_per90" class="xg-row">
      <span v-if="player.xg_per90">xG/90: <strong>{{ player.xg_per90.toFixed(2) }}</strong></span>
      <span v-if="player.xa_per90">xA/90: <strong>{{ player.xa_per90.toFixed(2) }}</strong></span>
    </div>

  </div>
</template>

<script setup>
import { computed } from 'vue'
import StatBar   from '@/components/StatBar.vue'
import ScorePill from '@/components/ScorePill.vue'
import { POSITION_LABELS } from '@/utils/positions.js'

const props = defineProps({
  player: { type: Object, required: true },
})

// Codice tecnico (es. "ST") usato come tooltip sul badge
const positionCode  = computed(() => props.player.position
  ? `Codice: ${props.player.position}`
  : '')

// Etichetta leggibile (es. "Centravanti")
const positionLabel = computed(() =>
  POSITION_LABELS[props.player.position] ?? props.player.position ?? '?'
)

const footLabel = computed(() => {
  const map = { Left: 'Mancino', Right: 'Destro' }
  return map[props.player.preferred_foot] ?? '?'
})

const baseStats = computed(() => [
  { label: 'PAC', value: props.player.pace },
  { label: 'TIR', value: props.player.shooting },
  { label: 'PAS', value: props.player.passing },
  { label: 'DRI', value: props.player.dribbling },
  { label: 'DIF', value: props.player.defending },
  { label: 'FIS', value: props.player.physical },
])

const hasScores = computed(() =>
  props.player.heading_score || props.player.build_up_score || props.player.defensive_score
)
</script>

<style scoped>
.player-card { transition: transform .15s, box-shadow .15s; cursor: default; }
.player-card:hover { transform: translateY(-3px); box-shadow: 0 8px 30px rgba(0,0,0,.5); }

.player-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
}
.player-name { font-size: 1rem; font-weight: 700; }
.player-sub  { font-size: .75rem; color: var(--color-muted); margin-top: .15rem; }
.player-meta { text-align: right; }
.player-age  { font-size: .75rem; color: var(--color-muted); margin-top: .25rem; }

.pos-badge {
  cursor: help;
  font-size: .7rem;
  max-width: 150px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-block;
}

.stats-grid  { display: grid; grid-template-columns: repeat(3, 1fr); gap: .4rem; margin-bottom: .75rem; }
.scores-row  { display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: .5rem; }
/* ─── PlayerCard: xG/xA row leggibile ─── */
.xg-row {
  display: flex;
  gap: 1rem;
  font-size: .82rem;             /* ← era .8rem */
  color: var(--color-text);      /* ← era var(--color-muted) */
  font-weight: 600;              /* ← aggiunto */
  margin-top: .5rem;
}
.xg-row strong {
  color: var(--color-text);
  font-weight: 800;
}
</style>