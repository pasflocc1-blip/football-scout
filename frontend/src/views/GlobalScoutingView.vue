<!-- 
  GlobalScoutingView.vue — aggiornato:
  - I nomi dei giocatori nella tabella sono ora cliccabili → /players/:id
  - La colonna "Minuti" è stata rimossa (i dati vengono da PlayerSeasonStats)
  - Aggiunto link "Dettaglio" per ogni riga
-->
<template>
  <div>
    <h1 class="page-title">🔥 Scouting Globale</h1>
    <p style="color: var(--color-muted); margin-bottom: 1.5rem; font-size: .9rem;">
      Esplora liberamente il database, scopri talenti nascosti e confronta giocatori.
    </p>

    <!-- Tab bar -->
    <div class="tab-bar">
      <button v-for="tab in TABS" :key="tab.id" class="tab-btn" :class="{ active: activeTab === tab.id }" @click="switchTab(tab.id)">
        {{ tab.label }}
      </button>
    </div>

    <!-- TAB: RICERCA -->
    <div v-if="activeTab === 'search'" class="card" style="margin-top:1.5rem">
      <h2 class="section-title">🔍 Ricerca avanzata</h2>
      <div class="filters-grid">
        <div class="filter-group">
          <label>Testo libero</label>
          <input v-model="searchFilters.q" placeholder="Nome, club, nazionalità…" />
        </div>
        <div class="filter-group">
          <label>Ruolo</label>
          <select v-model="searchFilters.position">
            <option v-for="opt in posOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label>Nazionalità</label>
          <input v-model="searchFilters.nationality" placeholder="Es: italian" />
        </div>
        <div class="filter-group">
          <label>Club</label>
          <input v-model="searchFilters.club" placeholder="Es: juventus" />
        </div>
        <div class="filter-group">
          <label>Età min</label>
          <input v-model.number="searchFilters.min_age" type="number" placeholder="16" />
        </div>
        <div class="filter-group">
          <label>Età max</label>
          <input v-model.number="searchFilters.max_age" type="number" placeholder="35" />
        </div>
        <div class="filter-group">
          <label>xG/90 min</label>
          <input v-model.number="searchFilters.min_xg" type="number" step="0.05" placeholder="0.0" />
        </div>
        <div class="filter-group">
          <label>xA/90 min</label>
          <input v-model.number="searchFilters.min_xa" type="number" step="0.05" placeholder="0.0" />
        </div>
        <div class="filter-group">
          <label>Piede</label>
          <select v-model="searchFilters.preferred_foot">
            <option value="">Tutti</option>
            <option value="left">Mancino</option>
            <option value="right">Destro</option>
          </select>
        </div>
        <div class="filter-group">
          <label>Ordina per</label>
          <select v-model="searchFilters.sort_by">
            <option value="name">Nome</option>
            <option value="xg_per90">xG/90</option>
            <option value="xa_per90">xA/90</option>
            <option value="npxg_per90">npxG/90</option>
            <option value="age">Età</option>
            <option value="finishing_score">Finishing score</option>
            <option value="creativity_score">Creativity score</option>
            <option value="pressing_score">Pressing score</option>
            <option value="carrying_score">Carrying score</option>
            <option value="finishing_pct">Finishing %ile</option>
            <option value="creativity_pct">Creativity %ile</option>
            <option value="minutes_season">Minuti</option>
            <option value="goals_season">Goal</option>
          </select>
        </div>
        <div class="filter-group">
          <label>Direzione</label>
          <select v-model="searchFilters.sort_dir">
            <option value="asc">↑ Crescente</option>
            <option value="desc">↓ Decrescente</option>
          </select>
        </div>
        <div class="filter-group">
          <label>Risultati</label>
          <select v-model.number="searchFilters.limit">
            <option :value="25">25</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
          </select>
        </div>
      </div>
      <div style="margin-top:1rem; display:flex; gap:.75rem; flex-wrap:wrap;">
        <button class="btn btn-primary" @click="runSearch" :disabled="loading">
          {{ loading ? '⏳ Ricerca…' : '🔍 Cerca' }}
        </button>
        <button class="btn btn-ghost" @click="resetSearch">Reset</button>
      </div>
    </div>

    <!-- TAB: RANKING -->
    <div v-if="activeTab === 'ranking'" class="card" style="margin-top:1.5rem">
      <h2 class="section-title">🏆 Classifiche</h2>
      <div class="ranking-controls">
        <div class="filter-group" style="max-width:220px">
          <label>Filtra ruolo</label>
          <select v-model="rankFilters.position">
            <option v-for="opt in posOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>
        <div class="filter-group" style="max-width:160px">
          <label>Minuti min</label>
          <input v-model.number="rankFilters.min_minutes" type="number" />
        </div>
        <div class="filter-group" style="max-width:120px">
          <label>Top N</label>
          <select v-model.number="rankFilters.limit">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
        </div>
      </div>
      <div class="ranking-buttons">
        <button class="btn btn-primary"  @click="runTopXG"          :disabled="loading">🎯 Top xG/90</button>
        <button class="btn btn-success"  @click="runOverperforming"  :disabled="loading">📈 Overperforming</button>
        <button class="btn btn-danger"   @click="runUnderperforming" :disabled="loading">📉 Underperforming</button>
      </div>
      <p v-if="rankingMode" class="rank-mode-label">
        Modalità: <strong>{{ rankingModeLabel }}</strong>
        <span v-if="rankingMode === 'over' || rankingMode === 'under'">— delta = goal segnati − xG stimati</span>
      </p>
    </div>

    <!-- TAB: CONFRONTO -->
    <div v-if="activeTab === 'compare'" class="card" style="margin-top:1.5rem">
      <h2 class="section-title">⚔️ Confronto giocatori</h2>
      <p style="color:var(--color-muted); font-size:.88rem; margin-bottom:1rem;">
        Inserisci il nome (o parte del nome) di due giocatori per confrontarli.
      </p>
      <div style="display:flex; gap:1rem; flex-wrap:wrap; align-items:flex-end;">
        <div class="filter-group" style="flex:1; min-width:180px">
          <label>Giocatore 1</label>
          <input v-model="compareName1" placeholder="Es: Mbappe" />
        </div>
        <div class="filter-group" style="flex:1; min-width:180px">
          <label>Giocatore 2</label>
          <input v-model="compareName2" placeholder="Es: Vinicius" />
        </div>
        <button class="btn btn-hot" @click="runCompare" :disabled="loading || !compareName1 || !compareName2">
          ⚔️ Confronta
        </button>
      </div>
    </div>

    <!-- Spinner -->
    <div v-if="loading" class="spinner" style="margin-top:2rem"></div>

    <!-- Errore -->
    <div v-if="error" class="error-msg" style="margin-top:1rem">⚠️ {{ error }}</div>

    <!-- Risultato COMPARE -->
    <div v-if="compareResult && !loading && activeTab === 'compare'" class="card" style="margin-top:1.5rem">
      <h3 class="section-title">Risultato confronto</h3>
      <div style="display:flex; gap:.5rem; margin-bottom:.75rem;">
        <router-link v-if="compareResult.player1.id" :to="`/players/${compareResult.player1.id}`" class="btn btn-ghost btn-sm">
          👤 Scheda {{ compareResult.player1.name }}
        </router-link>
        <router-link v-if="compareResult.player2.id" :to="`/players/${compareResult.player2.id}`" class="btn btn-ghost btn-sm">
          👤 Scheda {{ compareResult.player2.name }}
        </router-link>
      </div>
      <div class="compare-grid">
        <div class="compare-header">Metrica</div>
        <div class="compare-header player-col">{{ compareResult.player1.name }}</div>
        <div class="compare-header player-col">{{ compareResult.player2.name }}</div>
        <template v-for="row in compareRows" :key="row.key">
          <div class="compare-metric">{{ row.label }}</div>
          <div class="compare-val" :class="cellClass(row.key, 'p1')">{{ fmtVal(compareResult.player1[row.key]) }}</div>
          <div class="compare-val" :class="cellClass(row.key, 'p2')">{{ fmtVal(compareResult.player2[row.key]) }}</div>
        </template>
      </div>
    </div>

    <!-- Tabella risultati (search + ranking) -->
    <div v-if="players.length && !loading && activeTab !== 'compare'" class="card" style="margin-top:1.5rem; overflow-x:auto">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
        <h3 class="section-title" style="margin-bottom:0">{{ players.length }} risultati</h3>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Nome</th>
            <th>Ruolo</th>
            <th>Club</th>
            <th>Naz.</th>
            <th>Età</th>
            <th>xG/90</th>
            <th>xA/90</th>
            <th v-if="showDeltaCol">Goal</th>
            <th v-if="showDeltaCol">xG est.</th>
            <th v-if="showDeltaCol">Delta</th>
            <th>Minuti</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in players" :key="p.id ?? p.name">
            <td class="name-cell">
              <router-link v-if="p.id" :to="`/players/${p.id}`" class="player-link">{{ p.name }}</router-link>
              <span v-else>{{ p.name }}</span>
            </td>
            <td>
              <div class="pos-cell">
                <span class="badge badge-blue pos-code">{{ p.position ?? '—' }}</span>
                <span class="pos-desc">{{ posLabel(p.position) }}</span>
              </div>
            </td>
            <td>{{ p.club ?? '—' }}</td>
            <td>{{ p.nationality ?? '—' }}</td>
            <td>{{ p.age ?? '—' }}</td>
            <td class="stat-cell">{{ fmtStat(p.xg_per90) }}</td>
            <td class="stat-cell">{{ fmtStat(p.xa_per90) }}</td>
            <template v-if="showDeltaCol">
              <td class="stat-cell">{{ p.goals ?? '—' }}</td>
              <td class="stat-cell">{{ p.xg_estimated ?? '—' }}</td>
              <td class="stat-cell" :class="deltaClass(p.delta)">
                {{ p.delta != null ? (p.delta > 0 ? '+' : '') + p.delta : '—' }}
              </td>
            </template>
            <td class="stat-cell">{{ p.minutes ?? p.minutes_season ?? '—' }}</td>
            <td>
              <router-link v-if="p.id" :to="`/players/${p.id}`" class="btn btn-ghost btn-xs">👤</router-link>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Placeholder vuoto -->
    <div v-if="!players.length && !compareResult && !loading && !error" class="card empty-state" style="margin-top:1.5rem; text-align:center; color:var(--color-muted); padding:3rem;">
      <div style="font-size:3rem; margin-bottom:.5rem">🔭</div>
      <p>Usa i filtri in alto per esplorare il database dei giocatori.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { globalScoutingApi } from '@/api/client'
import { posLabel, posOptions } from '@/utils/positions.js'

const TABS = [
  { id: 'search',  label: '🔍 Ricerca' },
  { id: 'ranking', label: '🏆 Ranking' },
  { id: 'compare', label: '⚔️ Confronto' },
]
const activeTab = ref('search')

function switchTab(id) {
  activeTab.value = id
  error.value = null
}

const players       = ref([])
const compareResult = ref(null)
const loading       = ref(false)
const error         = ref(null)
const rankingMode   = ref('')

const searchFilters = ref({
  q: '', position: '', nationality: '', club: '',
  min_age: null, max_age: null, min_xg: null, min_xa: null,
  preferred_foot: '', sort_by: 'name', sort_dir: 'asc', limit: 50,
})

const rankFilters = ref({ position: '', min_minutes: 300, limit: 20 })
const compareName1 = ref('')
const compareName2 = ref('')

const showDeltaCol = computed(() => rankingMode.value === 'over' || rankingMode.value === 'under')
const rankingModeLabel = computed(() => ({
  topxg: 'Top xG/90', over: 'Overperforming', under: 'Underperforming',
}[rankingMode.value] ?? ''))

const compareRows = [
  { key: 'position',            label: 'Ruolo' },
  { key: 'club',                label: 'Club' },
  { key: 'nationality',         label: 'Nazionalità' },
  { key: 'age',                 label: 'Età' },
  { key: 'xg_per90',            label: 'xG/90' },
  { key: 'xa_per90',            label: 'xA/90' },
  { key: 'npxg_per90',          label: 'npxG/90' },
  { key: 'xgchain_per90',       label: 'xGChain/90' },
  { key: 'xgbuildup_per90',     label: 'xGBuildup/90' },
  { key: 'finishing_score',     label: 'Finishing score' },
  { key: 'creativity_score',    label: 'Creativity score' },
  { key: 'pressing_score',      label: 'Pressing score' },
  { key: 'carrying_score',      label: 'Carrying score' },
  { key: 'defending_obj_score', label: 'Defending score' },
  { key: 'buildup_obj_score',   label: 'Build-up score' },
  { key: 'finishing_pct',       label: 'Finishing %ile' },
  { key: 'creativity_pct',      label: 'Creativity %ile' },
  { key: 'pressing_pct',        label: 'Pressing %ile' },
  { key: 'carrying_pct',        label: 'Carrying %ile' },
  { key: 'defending_pct',       label: 'Defending %ile' },
]

async function runSearch() {
  loading.value = true
  error.value = null
  rankingMode.value = ''
  try {
    const params = {}
    const f = searchFilters.value
    if (f.q)             params.q = f.q
    if (f.position)      params.position = f.position
    if (f.nationality)   params.nationality = f.nationality
    if (f.club)          params.club = f.club
    if (f.min_age)       params.min_age = f.min_age
    if (f.max_age)       params.max_age = f.max_age
    if (f.min_xg)        params.min_xg = f.min_xg
    if (f.min_xa)        params.min_xa = f.min_xa
    if (f.preferred_foot) params.preferred_foot = f.preferred_foot
    params.sort_by  = f.sort_by
    params.sort_dir = f.sort_dir
    params.limit    = f.limit
    const data = await globalScoutingApi.search(params)
    players.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Errore ricerca'
  } finally {
    loading.value = false
  }
}

async function runTopXG() {
  loading.value = true
  error.value = null
  rankingMode.value = 'topxg'
  try {
    const data = await globalScoutingApi.topXG(rankFilters.value)
    players.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Errore'
  } finally {
    loading.value = false
  }
}

async function runOverperforming() {
  loading.value = true
  error.value = null
  rankingMode.value = 'over'
  try {
    const data = await globalScoutingApi.overperforming(rankFilters.value)
    players.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Errore'
  } finally {
    loading.value = false
  }
}

async function runUnderperforming() {
  loading.value = true
  error.value = null
  rankingMode.value = 'under'
  try {
    const data = await globalScoutingApi.underperforming(rankFilters.value)
    players.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Errore'
  } finally {
    loading.value = false
  }
}

async function runCompare() {
  if (!compareName1.value || !compareName2.value) return
  loading.value = true
  error.value = null
  players.value = []
  try {
    const data = await globalScoutingApi.compare(compareName1.value, compareName2.value)
    compareResult.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Errore confronto'
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  searchFilters.value = {
    q: '', position: '', nationality: '', club: '',
    min_age: null, max_age: null, min_xg: null, min_xa: null,
    preferred_foot: '', sort_by: 'name', sort_dir: 'asc', limit: 50,
  }
  players.value = []
  error.value = null
  rankingMode.value = ''
}

function fmtStat(v) {
  if (v == null) return '—'
  return Number(v).toFixed(3)
}

function fmtVal(v) {
  if (v == null) return '—'
  if (typeof v === 'number') return v % 1 === 0 ? v : v.toFixed(2)
  return v
}

function deltaClass(d) {
  if (d == null) return ''
  return d > 0 ? 'delta-pos' : d < 0 ? 'delta-neg' : ''
}

function cellClass(key, player) {
  if (!compareResult.value) return ''
  const v1 = compareResult.value.player1[key]
  const v2 = compareResult.value.player2[key]
  if (v1 == null || v2 == null || typeof v1 !== 'number') return ''
  if (player === 'p1') return v1 > v2 ? 'cell-win' : v1 < v2 ? 'cell-loss' : ''
  return v2 > v1 ? 'cell-win' : v2 < v1 ? 'cell-loss' : ''
}
</script>

<style scoped>
.player-link {
  color: var(--color-accent, #3b82f6);
  text-decoration: none;
  font-weight: 600;
}
.player-link:hover { text-decoration: underline; }

.btn-xs {
  font-size: .72rem;
  padding: 2px 6px;
}
.btn-sm {
  font-size: .8rem;
  padding: 4px 10px;
}

.ranking-controls { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
.ranking-buttons  { display: flex; gap: .75rem; flex-wrap: wrap; margin-bottom: 1rem; }
.rank-mode-label  { color: var(--color-muted); font-size: .85rem; }

.compare-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: .2rem .5rem;
}
.compare-header { font-weight: 700; color: var(--color-muted); font-size: .8rem; padding: .4rem 0; border-bottom: 1px solid var(--color-border, #333); }
.compare-metric { font-size: .83rem; color: var(--color-muted); padding: .25rem 0; border-bottom: 1px solid var(--color-border, #2a2a3a); }
.compare-val    { font-size: .83rem; font-weight: 600; text-align: center; padding: .25rem 0; border-bottom: 1px solid var(--color-border, #2a2a3a); }
.cell-win  { color: #22c55e; }
.cell-loss { color: #ef4444; }
.delta-pos { color: #22c55e; font-weight: 600; }
.delta-neg { color: #ef4444; font-weight: 600; }

.stat-cell { text-align: right; font-variant-numeric: tabular-nums; }
.name-cell { font-weight: 600; }
.pos-cell  { display: flex; gap: .3rem; align-items: center; }
.pos-desc  { font-size: .75rem; color: var(--color-muted); }
</style>