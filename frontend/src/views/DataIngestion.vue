<template>
  <div class="ingest-page">
    <div class="page-header">
      <h1>🔄 Gestione Dati</h1>
      <p class="subtitle">Importa e aggiorna i dati dei calciatori da tutte le sorgenti</p>
    </div>

    <!-- Configurazione globale -->
    <div class="config-panel card">
      <h2>⚙️ Configurazione</h2>
      <div class="config-grid">
        <div class="config-group">
          <label>Campionato (API-Football / Football-Data)</label>
          <select v-model="config.league_id">
            <option :value="135">Serie A</option>
            <option :value="39">Premier League</option>
            <option :value="140">La Liga</option>
            <option :value="78">Bundesliga</option>
            <option :value="61">Ligue 1</option>
          </select>
        </div>
        <div class="config-group">
          <label>Stagione</label>
          <select v-model="config.season">
            <option v-for="y in seasons" :key="y" :value="y">{{ y }}/{{ y + 1 }}</option>
          </select>
        </div>
        <div class="config-group">
          <label>FBref — Campionato</label>
          <select v-model="config.fbref_league">
            <option value="serie_a">Serie A</option>
            <option value="premier_league">Premier League</option>
            <option value="la_liga">La Liga</option>
            <option value="bundesliga">Bundesliga</option>
            <option value="ligue_1">Ligue 1</option>
            <option value="champions_league">Champions League</option>
          </select>
        </div>
        <div class="config-group">
          <label>FBref — Stagione</label>
          <input v-model="config.fbref_season" placeholder="es. 2023-2024" />
        </div>
        <div class="config-group">
          <label>StatsBomb — Competition ID</label>
          <input v-model.number="config.statsbomb_comp" type="number" placeholder="12" />
          <small>
            <a href="#" @click.prevent="loadStatsBombComps">Vedi disponibili →</a>
          </small>
        </div>
        <div class="config-group">
          <label>StatsBomb — Season ID</label>
          <input v-model.number="config.statsbomb_season_id" type="number" placeholder="27" />
        </div>
        <div class="config-group">
          <label>Kaggle CSV — Path nel container</label>
          <input v-model="config.kaggle_file" placeholder="/app/data/players_22.csv" />
        </div>
        <div class="config-group">
          <label>Max giocatori Kaggle</label>
          <input v-model.number="config.kaggle_limit" type="number" placeholder="2000" />
        </div>
        <div class="config-group">
          <label>Football-Data — Competition Code</label>
          <select v-model="config.fd_comp">
            <option value="SA">SA — Serie A</option>
            <option value="PL">PL — Premier League</option>
            <option value="PD">PD — La Liga</option>
            <option value="BL1">BL1 — Bundesliga</option>
            <option value="FL1">FL1 — Ligue 1</option>
            <option value="CL">CL — Champions League</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Pulsante: tutti i siti -->
    <div class="card run-all-card">
      <div class="run-all-info">
        <h2>🚀 Importa da tutte le sorgenti</h2>
        <p>Esegue Kaggle → API-Football → StatsBomb → FBref → Football-Data in sequenza.</p>
      </div>
      <button
        class="btn btn-all"
        :disabled="isAnyRunning"
        @click="runAll"
      >
        <span v-if="jobs.all?.status === 'running'">⏳ In esecuzione…</span>
        <span v-else>▶ Avvia tutto</span>
      </button>
    </div>

    <!-- Griglia sorgenti -->
    <div class="sources-grid">

      <!-- Kaggle -->
      <div class="source-card card" :class="statusClass('kaggle')">
        <div class="source-header">
          <div class="source-icon">📊</div>
          <div>
            <h3>Kaggle FIFA</h3>
            <span class="badge badge-free">Gratis</span>
          </div>
        </div>
        <p class="source-desc">
          ~18.000 giocatori con PAC, TIR, PAS, DRI, DIF, FIS da FIFA 22/23.
          Perfetto per sviluppo e prototipo.
        </p>
        <div class="source-params">
          <span>📁 {{ config.kaggle_file }}</span>
          <span>📦 max {{ config.kaggle_limit }}</span>
        </div>
        <div class="source-status" v-if="jobs.kaggle">
          <JobStatus :job="jobs.kaggle" />
        </div>
        <button
          class="btn btn-source"
          :disabled="jobs.kaggle?.status === 'running'"
          @click="runSource('kaggle')"
        >
          <span v-if="jobs.kaggle?.status === 'running'">⏳ Importando…</span>
          <span v-else>▶ Importa</span>
        </button>
      </div>

      <!-- API-Football -->
      <div class="source-card card" :class="statusClass('api_football')">
        <div class="source-header">
          <div class="source-icon">⚽</div>
          <div>
            <h3>API-Football</h3>
            <span class="badge badge-key">Richiede API key</span>
          </div>
        </div>
        <p class="source-desc">
          Dati live: giocatori attivi, squadre reali, statistiche stagione.
          Free tier: 100 req/giorno.
        </p>
        <div class="source-params">
          <span>🏆 {{ leagueName(config.league_id) }}</span>
          <span>📅 {{ config.season }}</span>
        </div>
        <div class="source-status" v-if="jobs.api_football">
          <JobStatus :job="jobs.api_football" />
        </div>
        <button
          class="btn btn-source"
          :disabled="jobs.api_football?.status === 'running'"
          @click="runSource('api-football')"
        >
          <span v-if="jobs.api_football?.status === 'running'">⏳ Importando…</span>
          <span v-else>▶ Importa</span>
        </button>
      </div>

      <!-- StatsBomb -->
      <div class="source-card card" :class="statusClass('statsbomb')">
        <div class="source-header">
          <div class="source-icon">📈</div>
          <div>
            <h3>StatsBomb</h3>
            <span class="badge badge-free">Open Data</span>
          </div>
        </div>
        <p class="source-desc">
          Event data dettagliato: xG per tiro, xA per key pass.
          Arricchisce i giocatori già importati con statistiche avanzate.
        </p>
        <div class="source-params">
          <span>🏷 comp_id: {{ config.statsbomb_comp }}</span>
          <span>📅 season_id: {{ config.statsbomb_season_id }}</span>
        </div>
        <div class="source-status" v-if="jobs.statsbomb">
          <JobStatus :job="jobs.statsbomb" />
        </div>
        <button
          class="btn btn-source"
          :disabled="jobs.statsbomb?.status === 'running'"
          @click="runSource('statsbomb')"
        >
          <span v-if="jobs.statsbomb?.status === 'running'">⏳ In esecuzione…</span>
          <span v-else>▶ Arricchisci xG/xA</span>
        </button>
      </div>

      <!-- FBref -->
      <div class="source-card card" :class="statusClass('fbref')">
        <div class="source-header">
          <div class="source-icon">🌐</div>
          <div>
            <h3>FBref</h3>
            <span class="badge badge-free">Scraping</span>
          </div>
        </div>
        <p class="source-desc">
          Alternativa gratuita a StatsBomb. Standard Stats con xG, xAG, minuti.
          Attenzione: rate limit FBref — non abusare.
        </p>
        <div class="source-params">
          <span>🏆 {{ config.fbref_league }}</span>
          <span>📅 {{ config.fbref_season }}</span>
        </div>
        <div class="source-status" v-if="jobs.fbref">
          <JobStatus :job="jobs.fbref" />
        </div>
        <button
          class="btn btn-source"
          :disabled="jobs.fbref?.status === 'running'"
          @click="runSource('fbref')"
        >
          <span v-if="jobs.fbref?.status === 'running'">⏳ Scraping…</span>
          <span v-else>▶ Scraping xG/xA</span>
        </button>
      </div>

      <!-- Football-Data.org -->
      <div class="source-card card" :class="statusClass('football_data')">
        <div class="source-header">
          <div class="source-icon">🏛</div>
          <div>
            <h3>Football-Data.org</h3>
            <span class="badge badge-key">Richiede API key</span>
          </div>
        </div>
        <p class="source-desc">
          Struttura campionati, rose ufficiali, classifiche.
          Aggiorna il campo club nei giocatori importati.
        </p>
        <div class="source-params">
          <span>🏆 {{ config.fd_comp }}</span>
          <span>📅 {{ config.season }}</span>
        </div>
        <div class="source-status" v-if="jobs.football_data">
          <JobStatus :job="jobs.football_data" />
        </div>
        <button
          class="btn btn-source"
          :disabled="jobs.football_data?.status === 'running'"
          @click="runSource('football-data')"
        >
          <span v-if="jobs.football_data?.status === 'running'">⏳ Sincronizzando…</span>
          <span v-else>▶ Sincronizza club</span>
        </button>
      </div>

    </div>

    <!-- Modale competizioni StatsBomb -->
    <div v-if="showSbModal" class="modal-overlay" @click.self="showSbModal = false">
      <div class="modal card">
        <div class="modal-header">
          <h3>StatsBomb — Competizioni disponibili</h3>
          <button class="btn-close" @click="showSbModal = false">✕</button>
        </div>
        <div class="modal-body">
          <input v-model="sbSearch" placeholder="Filtra per nome…" class="search-input" />
          <table class="sb-table">
            <thead>
              <tr>
                <th>Comp ID</th>
                <th>Season ID</th>
                <th>Competizione</th>
                <th>Stagione</th>
                <th>Paese</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="c in filteredSbComps"
                :key="`${c.competition_id}-${c.season_id}`"
              >
                <td>{{ c.competition_id }}</td>
                <td>{{ c.season_id }}</td>
                <td>{{ c.name }}</td>
                <td>{{ c.season }}</td>
                <td>{{ c.country }}</td>
                <td>
                  <button class="btn-select" @click="selectSbComp(c)">Usa</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
//import api from '@/services/api'
import api from '@/api/client'

// ── Config ─────────────────────────────────────────────────────
const currentYear = new Date().getFullYear()
const seasons = Array.from({ length: 8 }, (_, i) => currentYear - i)

const config = ref({
  league_id: 135,
  season: currentYear,
  fbref_league: 'serie_a',
  fbref_season: '2023-2024',
  statsbomb_comp: 12,
  statsbomb_season_id: 27,
  kaggle_file: '/app/data/players_22.csv',
  kaggle_limit: 2000,
  fd_comp: 'SA',
})

const LEAGUE_NAMES = {
  135: 'Serie A', 39: 'Premier League', 140: 'La Liga', 78: 'Bundesliga', 61: 'Ligue 1',
}
const leagueName = (id) => LEAGUE_NAMES[id] || `Lega ${id}`

// ── Job status ──────────────────────────────────────────────────
const jobs = ref({})
let pollingInterval = null

const isAnyRunning = computed(() =>
  Object.values(jobs.value).some(j => j?.status === 'running')
)

async function loadStatus() {
  try {
    const { data } = await api.get('/ingest/status')
    jobs.value = data
  } catch (e) {
    // silenzioso
  }
}

onMounted(() => {
  loadStatus()
  pollingInterval = setInterval(loadStatus, 3000)
})
onUnmounted(() => clearInterval(pollingInterval))

// ── Run handlers ─────────────────────────────────────────────────
async function runAll() {
  await api.post('/ingest/all', {
    kaggle_file: config.value.kaggle_file,
    kaggle_limit: config.value.kaggle_limit,
    api_league: config.value.league_id,
    season: config.value.season,
    statsbomb_comp: config.value.statsbomb_comp,
    statsbomb_season_id: config.value.statsbomb_season_id,
    statsbomb_max_matches: 50,
    fbref_league: config.value.fbref_league,
    fbref_season: config.value.fbref_season,
    football_data_comp: config.value.fd_comp,
  })
  await loadStatus()
}

async function runSource(source) {
  const payloads = {
    'kaggle': {
      file_path: config.value.kaggle_file,
      limit: config.value.kaggle_limit,
    },
    'api-football': {
      league_id: config.value.league_id,
      season: config.value.season,
    },
    'statsbomb': {
      competition_id: config.value.statsbomb_comp,
      season_id: config.value.statsbomb_season_id,
      max_matches: 50,
    },
    'fbref': {
      league_key: config.value.fbref_league,
      season: config.value.fbref_season,
    },
    'football-data': {
      competition_code: config.value.fd_comp,
      season: config.value.season,
    },
  }
  await api.post(`/ingest/${source}`, payloads[source])
  await loadStatus()
}

// ── StatsBomb competitions modal ─────────────────────────────────
const showSbModal = ref(false)
const sbComps = ref([])
const sbSearch = ref('')

const filteredSbComps = computed(() => {
  const q = sbSearch.value.toLowerCase()
  return sbComps.value.filter(c =>
    !q || c.name.toLowerCase().includes(q) || c.country.toLowerCase().includes(q) || c.season.toLowerCase().includes(q)
  )
})

async function loadStatsBombComps() {
  showSbModal.value = true
  if (sbComps.value.length) return
  const { data } = await api.get('/ingest/statsbomb/competitions')
  sbComps.value = data
}

function selectSbComp(c) {
  config.value.statsbomb_comp = c.competition_id
  config.value.statsbomb_season_id = c.season_id
  showSbModal.value = false
}

// ── Helpers ───────────────────────────────────────────────────────
function statusClass(key) {
  const s = jobs.value[key]?.status
  return { 'status-running': s === 'running', 'status-done': s === 'done', 'status-error': s === 'error' }
}
</script>

<!-- Sub-component inline: JobStatus -->
<script>
export default {
  components: {
    JobStatus: {
      props: ['job'],
      template: `
        <div class="job-status">
          <span v-if="job.status === 'running'" class="status-badge running">⏳ In esecuzione…</span>
          <span v-else-if="job.status === 'done'" class="status-badge done">
            ✅ Completato {{ job.finished_at ? formatTime(job.finished_at) : '' }}
            <span v-if="job.result" class="result-detail">
              — {{ formatResult(job.result) }}
            </span>
          </span>
          <span v-else-if="job.status === 'error'" class="status-badge error" :title="job.error">
            ❌ Errore — {{ truncate(job.error) }}
          </span>
          <span v-else class="status-badge idle">⬜ Non eseguito</span>
        </div>
      `,
      methods: {
        formatTime(iso) {
          return new Date(iso).toLocaleTimeString('it-IT')
        },
        formatResult(r) {
          if (r?.imported != null) return `${r.imported} giocatori importati`
          if (r?.players_enriched != null) return `${r.players_enriched} giocatori arricchiti`
          if (r?.players_updated != null) return `${r.players_updated} giocatori aggiornati`
          return JSON.stringify(r).slice(0, 60)
        },
        truncate(s) { return s ? s.slice(0, 80) : '' },
      },
    },
  },
}
</script>

<style scoped>
.ingest-page {
  padding: 1.5rem 2rem;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header { margin-bottom: 1.5rem; }
.page-header h1 { font-size: 1.6rem; font-weight: 700; margin: 0; }
.subtitle { color: var(--text-muted, #4b5563); margin-top: 0.3rem; }

.card {
  background: var(--surface, #fff);
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.25rem;
}

/* Config panel */
.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}
.config-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.config-group label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted, #4b5563);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.config-group input,
.config-group select {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 6px;
  font-size: 0.875rem;
  background: var(--bg, #ffffff);
}
.config-group small a {
  font-size: 0.75rem;
  color: var(--primary, #3b82f6);
  text-decoration: none;
}

/* Run all */
.run-all-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  background: linear-gradient(135deg, #1d4ed8 0%, #7c3aed 100%);
  color: #fff;
  border: none;
}
.run-all-card h2 { margin: 0; }
.run-all-card p { margin: 0.25rem 0 0; opacity: 0.85; font-size: 0.9rem; }

.btn-all {
  padding: 0.65rem 1.75rem;
  background: rgba(255,255,255,0.2);
  color: #fff;
  border: 2px solid rgba(255,255,255,0.4);
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.2s;
}
.btn-all:hover:not(:disabled) { background: rgba(255,255,255,0.35); }
.btn-all:disabled { opacity: 0.5; cursor: not-allowed; }

/* Sources grid */
.sources-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.source-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  transition: border-color 0.2s;
}
.source-card.status-running { border-color: #f59e0b; }
.source-card.status-done    { border-color: #10b981; }
.source-card.status-error   { border-color: #ef4444; }

.source-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.source-icon { font-size: 1.75rem; }
.source-header h3 { margin: 0; font-size: 1rem; font-weight: 700; }

.badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 20px;
  font-size: 0.7rem;
  font-weight: 600;
  margin-top: 0.2rem;
}
.badge-free { background: #bbf7d0; color: #064e3b; }
.badge-key  { background: #fde68a; color: #78350f; }

.source-desc {
  font-size: 0.85rem;
  color: var(--text-muted, #374151);
  margin: 0;
  line-height: 1.4;
}
.source-params {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: var(--text-muted, #4b5563);
}
.source-params span {
  background: var(--bg, #f3f4f6);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.btn-source {
  width: 100%;
  padding: 0.55rem;
  background: var(--primary, #3b82f6);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  margin-top: auto;
  transition: background 0.2s, opacity 0.2s;
}
.btn-source:hover:not(:disabled) { background: #1d4ed8; }
.btn-source:disabled { opacity: 0.5; cursor: not-allowed; }

/* Job status badges */
.job-status { font-size: 0.8rem; }
.status-badge { padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 500; }
.status-badge.running { background: #fde68a; color: #78350f; }
.status-badge.done    { background: #86efac; color: #14532d; }
.status-badge.error   { background: #fca5a5; color: #7f1d1d; }
.status-badge.idle    { background: var(--bg, #f3f4f6); color: var(--text-muted, #4b5563); }
.result-detail { opacity: 0.8; }

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  width: min(900px, 95vw);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.modal-header h3 { margin: 0; }
.btn-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: var(--text-muted, #4b5563);
}
.modal-body { overflow-y: auto; }
.search-input {
  width: 100%;
  padding: 0.45rem 0.75rem;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 6px;
  margin-bottom: 0.75rem;
  box-sizing: border-box;
}
.sb-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.sb-table th {
  text-align: left;
  padding: 0.5rem;
  border-bottom: 2px solid var(--border, #e5e7eb);
  font-weight: 600;
  color: var(--text-muted, #4b5563);
  font-size: 0.75rem;
  text-transform: uppercase;
}
.sb-table td { padding: 0.4rem 0.5rem; border-bottom: 1px solid var(--border, #f3f4f6); }
.btn-select {
  padding: 0.25rem 0.75rem;
  background: var(--primary, #3b82f6);
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
}
</style>