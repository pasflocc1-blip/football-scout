<template>
  <div>
    <!-- ── Header ─────────────────────────────────────────────── -->
    <h1 class="page-title">🔥 Scouting Globale</h1>
    <p style="color: var(--color-muted); margin-bottom: 1.5rem; font-size: .9rem;">
      Esplora liberamente il database, scopri talenti nascosti e confronta giocatori.
    </p>

    <!-- ── Tab bar ────────────────────────────────────────────── -->
    <div class="tab-bar">
      <button
        v-for="tab in TABS"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="switchTab(tab.id)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- ════════════════════════════════════════════════════════ -->
    <!-- TAB: RICERCA ────────────────────────────────────────── -->
    <!-- ════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'search'" class="card" style="margin-top:1.5rem">
      <h2 class="section-title">🔍 Ricerca avanzata</h2>

      <div class="filters-grid">
        <div class="filter-group">
          <label>Testo libero</label>
          <input v-model="searchFilters.q" placeholder="Nome, club, nazionalità…" />
        </div>
        <div class="filter-group">
          <label>Ruolo</label>
          <input v-model="searchFilters.position" placeholder="Es: ST, CM, CB, GK" />
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
            <option value="age">Età</option>
            <option value="pace">Velocità</option>
            <option value="shooting">Tiro</option>
            <option value="passing">Passaggi</option>
            <option value="dribbling">Dribbling</option>
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

    <!-- ════════════════════════════════════════════════════════ -->
    <!-- TAB: RANKING ────────────────────────────────────────── -->
    <!-- ════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'ranking'" class="card" style="margin-top:1.5rem">
      <h2 class="section-title">🏆 Classifiche</h2>

      <div class="ranking-controls">
        <div class="filter-group" style="max-width:180px">
          <label>Filtra ruolo</label>
          <input v-model="rankFilters.position" placeholder="ST, CM, CB…" />
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
        <button class="btn btn-primary"  @click="runTopXG"         :disabled="loading">🎯 Top xG/90</button>
        <button class="btn btn-success"  @click="runOverperforming" :disabled="loading">📈 Overperforming</button>
        <button class="btn btn-danger"   @click="runUnderperforming":disabled="loading">📉 Underperforming</button>
      </div>

      <p v-if="rankingMode" class="rank-mode-label">
        Modalità: <strong>{{ rankingModeLabel }}</strong>
        <span v-if="rankingMode === 'over' || rankingMode === 'under'">
          — delta = goal segnati − xG stimati
        </span>
      </p>
    </div>

    <!-- ════════════════════════════════════════════════════════ -->
    <!-- TAB: CONFRONTO ──────────────────────────────────────── -->
    <!-- ════════════════════════════════════════════════════════ -->
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

    <!-- ════════════════════════════════════════════════════════ -->
    <!-- AREA RISULTATI ──────────────────────────────────────── -->
    <!-- ════════════════════════════════════════════════════════ -->

    <!-- Spinner -->
    <div v-if="loading" class="spinner" style="margin-top:2rem"></div>

    <!-- Errore -->
    <div v-if="error" class="error-msg" style="margin-top:1rem">⚠️ {{ error }}</div>

    <!-- Risultato COMPARE ──────────────────────────────────── -->
    <div v-if="compareResult && !loading && activeTab === 'compare'" class="card" style="margin-top:1.5rem">
      <h3 class="section-title">Risultato confronto</h3>
      <div class="compare-grid">
        <!-- Intestazione -->
        <div class="compare-header">Metrica</div>
        <div class="compare-header player-col">{{ compareResult.player1.name }}</div>
        <div class="compare-header player-col">{{ compareResult.player2.name }}</div>

        <!-- Riga info -->
        <template v-for="row in compareRows" :key="row.key">
          <div class="compare-metric">{{ row.label }}</div>
          <div class="compare-val" :class="cellClass(row.key, 'p1')">
            {{ fmtVal(compareResult.player1[row.key]) }}
          </div>
          <div class="compare-val" :class="cellClass(row.key, 'p2')">
            {{ fmtVal(compareResult.player2[row.key]) }}
          </div>
        </template>
      </div>
    </div>

    <!-- Tabella risultati (search + ranking) ───────────────── -->
    <div
      v-if="players.length && !loading && activeTab !== 'compare'"
      class="card"
      style="margin-top:1.5rem; overflow-x:auto"
    >
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
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in players" :key="p.id ?? p.name">
            <td class="name-cell">{{ p.name }}</td>
            <td><span class="badge badge-blue">{{ p.position ?? '—' }}</span></td>
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
            <td class="stat-cell">{{ p.minutes ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Placeholder vuoto -->
    <div
      v-if="!players.length && !compareResult && !loading && !error"
      class="card empty-state"
      style="margin-top:1.5rem; text-align:center; color:var(--color-muted); padding:3rem;"
    >
      <div style="font-size:3rem; margin-bottom:.5rem">🔭</div>
      <p>Usa i filtri in alto per esplorare il database dei giocatori.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { globalScoutingApi } from '@/api/client'

// ── Tab ──────────────────────────────────────────────────────────
const TABS = [
  { id: 'search',  label: '🔍 Ricerca' },
  { id: 'ranking', label: '🏆 Ranking' },
  { id: 'compare', label: '⚔️ Confronto' },
]
const activeTab = ref('search')

function switchTab(id) {
  activeTab.value = id
  error.value     = null
  // Non svuota i risultati per permettere confronto tra tab
}

// ── State ────────────────────────────────────────────────────────
const players       = ref([])
const compareResult = ref(null)
const loading       = ref(false)
const error         = ref(null)
const rankingMode   = ref('')   // '' | 'topxg' | 'over' | 'under'

// ── Filtri ricerca ────────────────────────────────────────────────
const searchFilters = ref({
  q:             '',
  position:      '',
  nationality:   '',
  club:          '',
  min_age:       null,
  max_age:       null,
  min_xg:        null,
  min_xa:        null,
  preferred_foot:'',
  sort_by:       'name',
  sort_dir:      'asc',
  limit:         50,
})

// ── Filtri ranking ────────────────────────────────────────────────
const rankFilters = ref({
  position:    '',
  min_minutes: 300,
  limit:       20,
})

// ── Filtri confronto ──────────────────────────────────────────────
const compareName1 = ref('')
const compareName2 = ref('')

// ── Computed ──────────────────────────────────────────────────────
const showDeltaCol = computed(
  () => rankingMode.value === 'over' || rankingMode.value === 'under'
)

const rankingModeLabel = computed(() => ({
  topxg: 'Top xG/90',
  over:  'Overperforming',
  under: 'Underperforming',
}[rankingMode.value] ?? ''))

// ── Righe per la tabella compare ──────────────────────────────────
const compareRows = [
  { key: 'position',             label: 'Ruolo' },
  { key: 'club',                 label: 'Club' },
  { key: 'nationality',          label: 'Nazionalità' },
  { key: 'age',                  label: 'Età' },
  { key: 'pace',                 label: 'Velocità' },
  { key: 'shooting',             label: 'Tiro' },
  { key: 'passing',              label: 'Passaggi' },
  { key: 'dribbling',            label: 'Dribbling' },
  { key: 'defending',            label: 'Difesa' },
  { key: 'physical',             label: 'Fisico' },
  { key: 'xg_per90',             label: 'xG/90' },
  { key: 'xa_per90',             label: 'xA/90' },
  { key: 'heading_score',        label: 'Testa' },
  { key: 'build_up_score',       label: 'Build-up' },
  { key: 'defensive_score',      label: 'Score difensivo' },
  { key: 'aerial_duels_won_pct', label: 'Duelli aerei %' },
]

// ── Helpers UI ────────────────────────────────────────────────────
function fmtStat(v) {
  if (v == null) return '—'
  return typeof v === 'number' ? v.toFixed(2) : v
}

function fmtVal(v) {
  if (v == null) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? v : v.toFixed(2)
  return v
}

function deltaClass(delta) {
  if (delta == null) return ''
  return delta > 0 ? 'delta-positive' : delta < 0 ? 'delta-negative' : ''
}

// Colora la cella del confronto: verde = valore più alto
function cellClass(key, side) {
  if (!compareResult.value) return ''
  const numericKeys = [
    'pace','shooting','passing','dribbling','defending','physical',
    'xg_per90','xa_per90','heading_score','build_up_score',
    'defensive_score','aerial_duels_won_pct','progressive_passes',
  ]
  if (!numericKeys.includes(key)) return ''
  const v1 = compareResult.value.player1[key]
  const v2 = compareResult.value.player2[key]
  if (v1 == null || v2 == null) return ''
  if (side === 'p1') return v1 > v2 ? 'cell-win' : v1 < v2 ? 'cell-lose' : ''
  if (side === 'p2') return v2 > v1 ? 'cell-win' : v2 < v1 ? 'cell-lose' : ''
  return ''
}

// ── Azioni API ────────────────────────────────────────────────────
async function runSearch() {
  loading.value  = true
  error.value    = null
  compareResult.value = null
  rankingMode.value   = ''
  try {
    // Pulisce i parametri vuoti/null prima di inviare
    const params = Object.fromEntries(
      Object.entries(searchFilters.value).filter(
        ([, v]) => v !== null && v !== '' && v !== undefined
      )
    )
    const { data } = await globalScoutingApi.search(params)
    players.value = data
  } catch (e) {
    error.value = e.message
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
  error.value   = null
}

async function runTopXG() {
  loading.value = true
  error.value   = null
  compareResult.value = null
  rankingMode.value   = 'topxg'
  try {
    const { data } = await globalScoutingApi.topXg({
      limit:       rankFilters.value.limit,
      min_minutes: rankFilters.value.min_minutes,
      position:    rankFilters.value.position || undefined,
    })
    players.value = data
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function runOverperforming() {
  loading.value = true
  error.value   = null
  compareResult.value = null
  rankingMode.value   = 'over'
  try {
    const { data } = await globalScoutingApi.overperforming({
      limit:       rankFilters.value.limit,
      min_minutes: rankFilters.value.min_minutes,
      position:    rankFilters.value.position || undefined,
    })
    players.value = data
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function runUnderperforming() {
  loading.value = true
  error.value   = null
  compareResult.value = null
  rankingMode.value   = 'under'
  try {
    const { data } = await globalScoutingApi.underperforming({
      limit:       rankFilters.value.limit,
      min_minutes: rankFilters.value.min_minutes,
      position:    rankFilters.value.position || undefined,
    })
    players.value = data
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function runCompare() {
  if (!compareName1.value || !compareName2.value) return
  loading.value  = true
  error.value    = null
  players.value  = []
  compareResult.value = null
  try {
    const { data } = await globalScoutingApi.compare(
      compareName1.value,
      compareName2.value
    )
    compareResult.value = data
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ── Tab bar ─────────────────────────────────────────────────── */
.tab-bar {
  display: flex;
  gap: .5rem;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 0;
}

.tab-btn {
  padding: .55rem 1.3rem;
  border: none;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--color-muted);
  font-size: .92rem;
  font-weight: 600;
  cursor: pointer;
  transition: color .15s, border-color .15s;
  border-radius: var(--radius) var(--radius) 0 0;
}
.tab-btn:hover { color: var(--color-text); }
.tab-btn.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

/* ── Sezioni ─────────────────────────────────────────────────── */
.section-title {
  font-size: 1.05rem;
  font-weight: 700;
  margin-bottom: 1rem;
  color: var(--color-text);
}

/* ── Filtri ──────────────────────────────────────────────────── */
.filters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: .75rem;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: .3rem;
}
.filter-group label {
  font-size: .78rem;
  font-weight: 600;
  color: var(--color-muted);
  text-transform: uppercase;
  letter-spacing: .04em;
}

/* ── Ranking ─────────────────────────────────────────────────── */
.ranking-controls {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.ranking-buttons {
  display: flex;
  gap: .75rem;
  flex-wrap: wrap;
  margin-top: .75rem;
}

.rank-mode-label {
  margin-top: .75rem;
  font-size: .85rem;
  color: var(--color-muted);
}

/* ── Tabella ─────────────────────────────────────────────────── */
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: .875rem;
}

.data-table th {
  text-align: left;
  padding: .6rem .9rem;
  background: rgba(255,255,255,.04);
  color: var(--color-muted);
  font-size: .75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

.data-table td {
  padding: .6rem .9rem;
  border-bottom: 1px solid rgba(255,255,255,.04);
  vertical-align: middle;
}

.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: rgba(255,255,255,.02); }

.name-cell { font-weight: 600; }
.stat-cell { font-family: 'Fira Code', monospace; font-size: .82rem; }

.delta-positive { color: var(--color-success); font-weight: 700; }
.delta-negative { color: var(--color-danger);  font-weight: 700; }

/* ── Compare table ───────────────────────────────────────────── */
.compare-grid {
  display: grid;
  grid-template-columns: 1.5fr 1fr 1fr;
  gap: 0;
  font-size: .88rem;
}

.compare-header {
  padding: .65rem 1rem;
  font-size: .75rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--color-muted);
  letter-spacing: .05em;
  background: rgba(255,255,255,.04);
  border-bottom: 1px solid var(--color-border);
}

.compare-metric {
  padding: .55rem 1rem;
  color: var(--color-muted);
  font-size: .82rem;
  border-bottom: 1px solid rgba(255,255,255,.04);
}

.compare-val {
  padding: .55rem 1rem;
  font-family: 'Fira Code', monospace;
  font-size: .82rem;
  border-bottom: 1px solid rgba(255,255,255,.04);
  border-left: 1px solid rgba(255,255,255,.04);
  text-align: center;
}

.player-col { text-align: center; font-weight: 700; color: var(--color-text); }

.cell-win  { color: var(--color-success); font-weight: 700; }
.cell-lose { color: var(--color-danger); }
</style>