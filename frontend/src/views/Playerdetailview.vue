<template>
  <div class="player-detail">

    <div class="search-header">
      <div class="search-box">
        <div class="search-input-wrapper">
          <span class="search-icon">🔍</span>
          <input 
            type="text" 
            v-model="searchQuery" 
            @input="onSearch" 
            placeholder="Cerca un calciatore (es. Dybala)..." 
          />
        </div>
        <ul v-if="searchResults.length" class="autocomplete-list">
          <li v-for="res in searchResults" :key="res.id" @click="goToPlayer(res.id)">
            {{ res.name }} <span class="text-muted">({{ res.position }})</span>
          </li>
        </ul>
      </div>
    </div>

    <div v-if="!player && !loading && !error && !route.params.id" class="welcome-state">
      <h2>Benvenuto nello Scouting</h2>
      <p>Cerca un calciatore usando la barra qui sopra per visualizzare la sua scheda.</p>
    </div>

    <div v-if="loading" class="spinner-wrap"><div class="spinner"></div></div>
    <div v-if="error" class="error-msg">⚠️ {{ error }}</div>

    <div class="tabs-and-filters" v-if="player && !loading">
      
        <div class="competition-filter">
        <label>Competizione:</label>
        <select v-model="selectedCompetition">
            <option v-for="comp in availableCompetitions" :key="comp" :value="comp">
            {{ comp }}
            </option>
        </select>
        </div>

        <div class="tabs">
        <button class="tab-btn" :class="{ active: activeTab === 'stats' }" @click="activeTab = 'stats'">📊 Statistiche</button>
        <button class="tab-btn" :class="{ active: activeTab === 'matches' }" @click="activeTab = 'matches'">🗓 Partite</button>
        <button class="tab-btn" :class="{ active: activeTab === 'career' }" @click="activeTab = 'career'">🔄 Carriera</button>
      </div>
    </div>

    <div v-if="player && !loading" class="player-hero">
      <div class="hero-avatar">
        <div class="avatar-circle">
          <span class="avatar-initial">{{ player.name?.charAt(0) }}</span>
        </div>
        <div class="player-badge-pos">{{ player.position ?? '—' }}</div>
      </div>
      <div class="hero-info">
        <h1 class="hero-name">{{ player.name }}</h1>
        <div class="hero-meta">
          <span class="meta-club">🏟 {{ player.club ?? '—' }}</span>
          <span class="meta-sep">·</span>
          <span>{{ player.nationality ?? '—' }}</span>
          <span class="meta-sep">·</span>
          <span>{{ player.age ?? '—' }} anni</span>
          <span v-if="player.preferred_foot" class="meta-sep">·</span>
          <span v-if="player.preferred_foot">
            {{ player.preferred_foot === 'Left' ? '🦶 Mancino' : player.preferred_foot === 'Right' ? '🦶 Destro' : player.preferred_foot }}
          </span>
        </div>
        <div class="hero-stats-row">
          <div class="hero-stat">
            <span class="hero-stat-val">{{ player.height ? player.height + ' cm' : '—' }}</span>
            <span class="hero-stat-lbl">Altezza</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-val">{{ player.weight ? player.weight + ' kg' : '—' }}</span>
            <span class="hero-stat-lbl">Peso</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-val">{{ player.jersey_number ? '#' + player.jersey_number : '—' }}</span>
            <span class="hero-stat-lbl">Maglia</span>
          </div>
          <div class="hero-stat" v-if="player.market_value">
            <span class="hero-stat-val">{{ player.market_value }}M €</span>
            <span class="hero-stat-lbl">Valore</span>
          </div>
          <div class="hero-stat" v-if="player.sofascore_rating">
            <span class="hero-stat-val rating-val">{{ player.sofascore_rating }}</span>
            <span class="hero-stat-lbl">Rating</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'stats' && player && !loading">
      <div class="card score-card" v-if="hasScores">
        <h3 class="section-title">📊 Profilo prestativo</h3>
        <div class="score-grid">
          <div v-for="s in scoreItems" :key="s.key" class="score-item">
            <div class="score-bar-wrap">
              <div class="score-bar-fill" :style="{ width: (player.scores[s.key] || 0) + '%', background: scoreColor(player.scores[s.key]) }"></div>
            </div>
            <div class="score-labels">
              <span class="score-lbl">{{ s.label }}</span>
              <span class="score-val" :style="{ color: scoreColor(player.scores[s.key]) }">
                {{ player.scores[s.key] != null ? player.scores[s.key].toFixed(1) : '—' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div v-for="comp in filteredCompetitions" :key="comp.id" class="card comp-card">
        <div class="comp-header">
          <div>
            <span class="comp-league">{{ comp.league }}</span>
            <span class="comp-season">{{ comp.season }}</span>
          </div>
          <div class="comp-rating" v-if="comp.sofascore_rating">
            <span class="rating-badge">{{ comp.sofascore_rating.toFixed(2) }}</span>
          </div>
        </div>

        <div class="presence-row">
          <div class="pres-stat"><span>{{ comp.appearances ?? '—' }}</span><label>Presenze</label></div>
          <div class="pres-stat"><span>{{ comp.matches_started ?? '—' }}</span><label>Titolare</label></div>
          <div class="pres-stat"><span>{{ comp.minutes_played != null ? comp.minutes_played + "'" : '—' }}</span><label>Minuti</label></div>
          <div class="pres-stat"><span class="goals-val">{{ comp.goals ?? '—' }}</span><label>Gol</label></div>
          <div class="pres-stat"><span class="assists-val">{{ comp.assists ?? '—' }}</span><label>Assist</label></div>
        </div>

        <div class="stat-sections">
          <div class="stat-section">
            <div class="stat-section-title">⚽ Tiro</div>
            <div class="stat-row" v-if="comp.shots_total != null"><span class="stat-lbl">Tiri totali</span><span class="stat-val">{{ comp.shots_total }}</span></div>
            <div class="stat-row" v-if="comp.shots_on_target != null"><span class="stat-lbl">In porta</span><span class="stat-val">{{ comp.shots_on_target }}</span></div>
            <div class="stat-row" v-if="comp.big_chances_created != null"><span class="stat-lbl">Big chances create</span><span class="stat-val">{{ comp.big_chances_created }}</span></div>
            <div class="stat-row" v-if="comp.xg != null"><span class="stat-lbl">xG</span><span class="stat-val">{{ comp.xg }}</span></div>
            <div class="stat-row" v-if="comp.xg_per90 != null"><span class="stat-lbl">xG/90</span><span class="stat-val">{{ comp.xg_per90 }}</span></div>
            <div class="stat-row" v-if="comp.goal_conversion_pct != null"><span class="stat-lbl">Conversione gol</span><span class="stat-val">{{ comp.goal_conversion_pct }}%</span></div>
          </div>

          <div class="stat-section">
            <div class="stat-section-title">🎯 Passaggi</div>
            <div class="stat-row" v-if="comp.accurate_passes != null"><span class="stat-lbl">Acc./Tot.</span><span class="stat-val">{{ comp.accurate_passes }}/{{ comp.total_passes }}</span></div>
            <div class="stat-row" v-if="comp.pass_accuracy_pct != null"><span class="stat-lbl">Precisione</span><span class="stat-val">{{ comp.pass_accuracy_pct }}%</span></div>
            <div class="stat-row" v-if="comp.key_passes != null"><span class="stat-lbl">Passaggi chiave</span><span class="stat-val">{{ comp.key_passes }}</span></div>
            <div class="stat-row" v-if="comp.xa != null"><span class="stat-lbl">xA</span><span class="stat-val">{{ comp.xa }}</span></div>
            <div class="stat-row" v-if="comp.xa_per90 != null"><span class="stat-lbl">xA/90</span><span class="stat-val">{{ comp.xa_per90 }}</span></div>
            <div class="stat-row" v-if="comp.accurate_crosses != null"><span class="stat-lbl">Traversoni acc.</span><span class="stat-val">{{ comp.accurate_crosses }}</span></div>
            <div class="stat-row" v-if="comp.accurate_long_balls != null"><span class="stat-lbl">Lanci lunghi acc.</span><span class="stat-val">{{ comp.accurate_long_balls }}</span></div>
          </div>

          <div class="stat-section">
            <div class="stat-section-title">💪 Duelli</div>
            <div class="stat-row" v-if="comp.total_duels_won_pct != null"><span class="stat-lbl">Duelli vinti</span><span class="stat-val">{{ comp.total_duels_won_pct }}%</span></div>
            <div class="stat-row" v-if="comp.aerial_duels_won != null"><span class="stat-lbl">Aerei vinti</span><span class="stat-val">{{ comp.aerial_duels_won }}</span></div>
            <div class="stat-row" v-if="comp.aerial_duels_won_pct != null"><span class="stat-lbl">% Aerei</span><span class="stat-val">{{ comp.aerial_duels_won_pct }}%</span></div>
            <div class="stat-row" v-if="comp.successful_dribbles != null"><span class="stat-lbl">Dribbling riusciti</span><span class="stat-val">{{ comp.successful_dribbles }}</span></div>
            <div class="stat-row" v-if="comp.dribble_success_pct != null"><span class="stat-lbl">% Dribbling</span><span class="stat-val">{{ comp.dribble_success_pct }}%</span></div>
          </div>

          <div class="stat-section" v-if="comp.tackles != null || comp.interceptions != null">
            <div class="stat-section-title">🛡 Difesa</div>
            <div class="stat-row" v-if="comp.tackles != null"><span class="stat-lbl">Tackle</span><span class="stat-val">{{ comp.tackles }}</span></div>
            <div class="stat-row" v-if="comp.tackles_won_pct != null"><span class="stat-lbl">% Tackle vinti</span><span class="stat-val">{{ comp.tackles_won_pct }}%</span></div>
            <div class="stat-row" v-if="comp.interceptions != null"><span class="stat-lbl">Intercetti</span><span class="stat-val">{{ comp.interceptions }}</span></div>
            <div class="stat-row" v-if="comp.clearances != null"><span class="stat-lbl">Respinte</span><span class="stat-val">{{ comp.clearances }}</span></div>
            <div class="stat-row" v-if="comp.ball_recovery != null"><span class="stat-lbl">Palloni recuperati</span><span class="stat-val">{{ comp.ball_recovery }}</span></div>
          </div>

          <div class="stat-section">
            <div class="stat-section-title">🟨 Disciplina</div>
            <div class="stat-row"><span class="stat-lbl">Ammonizioni</span><span class="stat-val">{{ comp.yellow_cards ?? 0 }}</span></div>
            <div class="stat-row"><span class="stat-lbl">Espulsioni</span><span class="stat-val">{{ comp.red_cards ?? 0 }}</span></div>
            <div class="stat-row" v-if="comp.fouls_committed != null"><span class="stat-lbl">Falli commessi</span><span class="stat-val">{{ comp.fouls_committed }}</span></div>
            <div class="stat-row" v-if="comp.fouls_won != null"><span class="stat-lbl">Falli subiti</span><span class="stat-val">{{ comp.fouls_won }}</span></div>
          </div>

          <div class="stat-section" v-if="comp.saves != null">
            <div class="stat-section-title">🧤 Portiere</div>
            <div class="stat-row"><span class="stat-lbl">Parate</span><span class="stat-val">{{ comp.saves }}</span></div>
            <div class="stat-row" v-if="comp.goals_conceded != null"><span class="stat-lbl">Gol subiti</span><span class="stat-val">{{ comp.goals_conceded }}</span></div>
            <div class="stat-row" v-if="comp.clean_sheets != null"><span class="stat-lbl">Clean sheet</span><span class="stat-val">{{ comp.clean_sheets }}</span></div>
          </div>
        </div>
      </div>

      <div v-if="!filteredCompetitions.length" class="empty-state">
        <p>Nessuna statistica stagionale disponibile per questa competizione.</p>
      </div>
    </div>

    <div v-if="activeTab === 'matches' && player && !loading">
      <div class="card" style="margin-top: 1rem;">
        <h3 class="section-title">🗓 Ultime partite</h3>
        <div v-if="loadingMatches" class="spinner"></div>
        <div v-else-if="filteredMatches.length">
          <div v-for="m in filteredMatches" :key="m.event_id" class="match-row">
            <div class="match-date">{{ formatDate(m.date) }}</div>
            <div class="match-tournament">{{ m.tournament }}</div>
            <div class="match-teams">
              <span :class="{ 'bold': isHome(m, player.club) }">{{ m.home_team }}</span>
              <span class="match-score">{{ m.home_score ?? '?' }} - {{ m.away_score ?? '?' }}</span>
              <span :class="{ 'bold': !isHome(m, player.club) }">{{ m.away_team }}</span>
            </div>
            <div class="match-perf">
              <span v-if="m.rating" class="rating-badge small" :class="ratingClass(m.rating)">{{ m.rating }}</span>
              <span v-if="m.minutes_played" class="match-mins">{{ m.minutes_played }}'</span>
              <span v-if="m.goals" class="match-goal">⚽ × {{ m.goals }}</span>
              <span v-if="m.assists" class="match-assist">🎯 × {{ m.assists }}</span>
              <span v-if="m.yellow_card" class="card-yellow">🟨</span>
              <span v-if="m.red_card" class="card-red">🟥</span>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">Nessuna partita disponibile per la competizione selezionata.</div>
      </div>
    </div>

    <div v-if="activeTab === 'career' && player && !loading">
      <div class="card" style="margin-top: 1rem;">
        <h3 class="section-title">🔄 Storico trasferimenti</h3>
        <div v-if="player.career.length" class="career-timeline">
          <div v-for="(c, idx) in player.career" :key="idx" class="career-item">
            <div class="career-dot"></div>
            <div class="career-content">
              <div class="career-teams">
                <span class="career-from">{{ c.from_team || '?' }}</span>
                <span class="career-arrow">→</span>
                <span class="career-to">{{ c.to_team }}</span>
              </div>
              <div class="career-meta">
                <span class="career-date">{{ formatDateShort(c.transfer_date) }}</span>
                <span v-if="c.transfer_type" class="career-type">{{ c.transfer_type }}</span>
                <span v-if="c.fee && c.fee > 0" class="career-fee">{{ formatFee(c.fee) }}</span>
                <span v-else-if="c.fee === 0 && c.transfer_type === 'Free'" class="career-free">Svincolato</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">Nessuna informazione sulla carriera.</div>
      </div>

      <div class="card" style="margin-top: 1rem;" v-if="player.national_stats?.length">
        <h3 class="section-title">🌍 Nazionale</h3>
        <div v-for="n in player.national_stats" :key="n.national_team" class="national-row">
          <div class="national-team">🏳 {{ n.national_team }}</div>
          <div class="national-stats">
            <div class="pres-stat"><span>{{ n.appearances ?? '—' }}</span><label>Presenze</label></div>
            <div class="pres-stat"><span class="goals-val">{{ n.goals ?? '—' }}</span><label>Gol</label></div>
            <div class="pres-stat"><span class="assists-val">{{ n.assists ?? '—' }}</span><label>Assist</label></div>
            <div class="pres-stat" v-if="n.rating"><span class="rating-val">{{ n.rating }}</span><label>Rating</label></div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const route = useRoute()
const router = useRouter() 

const player = ref(null)
const matches = ref([])
const loading = ref(false)
const loadingMatches = ref(false)
const error = ref(null)
const activeTab = ref('stats')


const scoreItems = [
  { key: 'finishing_pct',   label: 'Finalizzazione' },
  { key: 'creativity_pct',  label: 'Creatività' },
  { key: 'pressing_pct',    label: 'Pressing' },
  { key: 'carrying_pct',    label: 'Conduzione' },
  { key: 'defending_pct',   label: 'Difesa' },
  { key: 'buildup_pct',     label: 'Costruzione' },
]

const hasScores = computed(() =>
  player.value?.scores && Object.values(player.value.scores).some(v => v != null)
)

function scoreColor(val) {
  if (val == null) return '#666'
  if (val >= 75) return '#22c55e'
  if (val >= 50) return '#f59e0b'
  return '#ef4444'
}

async function loadPlayer() {
  const id = route.params.id
  
  if (!id) {
    player.value = null
    matches.value = []
    loading.value = false
    return
  }

  loading.value = true
  error.value = null
  try {
    const res = await axios.get(`${API}/players/${id}/detail`)
    player.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Errore caricamento giocatore'
  } finally {
    loading.value = false
  }
}

async function loadMatches() {
  const id = route.params.id
  if (!id) {
    matches.value = []
    return
  }

  loadingMatches.value = true
  try {
    const res = await axios.get(`${API}/players/${id}/matches`, { params: { limit: 50 } })
    matches.value = res.data.matches || []
  } catch (e) {
    matches.value = []
  } finally {
    loadingMatches.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'matches' && !matches.value.length && route.params.id) {
    loadMatches()
  }
})

watch(() => route.params.id, (newId) => {
  if (newId) {
    loadPlayer()
    if (activeTab.value === 'matches') {
      loadMatches()
    }
  } else {
    player.value = null
    matches.value = []
    activeTab.value = 'stats'
  }
})

onMounted(() => {
  loadPlayer()
})

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })
}

function formatDateShort(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('it-IT', { month: 'short', year: 'numeric' })
}

function formatFee(fee) {
  if (!fee || fee <= 0) return 'Gratuito'
  if (fee >= 1) return fee.toFixed(1) + 'M €'
  return (fee * 1000).toFixed(0) + 'K €'
}

function isHome(match, club) {
  return match.home_team?.toLowerCase().includes(club?.toLowerCase() || '')
}

function ratingClass(r) {
  if (r >= 8) return 'rating-great'
  if (r >= 7) return 'rating-good'
  if (r >= 6) return 'rating-ok'
  return 'rating-bad'
}

// --- LOGICA DI RICERCA ---
const searchQuery = ref('')
const searchResults = ref([])
let searchTimeout = null

const onSearch = () => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(async () => {
    if (searchQuery.value.length < 3) {
      searchResults.value = []
      return
    }
    try {
      const res = await axios.get(`${API}/scouting/autocomplete?q=${searchQuery.value}`)
      searchResults.value = res.data
    } catch (err) {
      console.error("Errore nella ricerca", err)
    }
  }, 300)
}
const goToPlayer = (id) => {
  searchQuery.value = ''
  searchResults.value = []
  router.push(`/players/${id}`)
}

// --- LOGICA FILTRO COMPETIZIONI ---
const selectedCompetition = ref('')

const availableCompetitions = computed(() => {
  const comps = new Set()
  
  if (player.value?.competitions) {
    player.value.competitions.forEach(c => {
      if (c.league) comps.add(c.league)
    })
  }
  
  if (matches.value) {
    matches.value.forEach(m => {
      if (m.tournament) comps.add(m.tournament)
    })
  }
  
  return Array.from(comps).filter(Boolean)
})

// Auto-seleziona la prima competizione non appena i dati sono disponibili
watch(availableCompetitions, (newComps) => {
  if (newComps.length > 0 && !newComps.includes(selectedCompetition.value)) {
    selectedCompetition.value = newComps[0]
  }
}, { immediate: true })

const filteredCompetitions = computed(() => {
  if (!player.value || !player.value.competitions) return []
  if (!selectedCompetition.value) return player.value.competitions
  return player.value.competitions.filter(c => c.league === selectedCompetition.value)
})

const filteredMatches = computed(() => {
  if (!selectedCompetition.value) return matches.value
  return matches.value.filter(m => m.tournament === selectedCompetition.value)
})

</script>

<style scoped>
/* Ingrandito il font-size base e la larghezza della pagina */
.player-detail {
  max-width: 1000px;
  margin: 0 auto;
  padding: 1rem;
  font-size: 1.05rem; 
}

/* ─── Search Header (Sostituisce il tasto indietro) ─────────────────────────────── */
.search-header {
  margin-bottom: 2rem;
}
.search-box {
  position: relative;
}
.search-input-wrapper {
  display: flex;
  align-items: center;
  background: var(--color-surface, #1e1e2e);
  border: 1px solid var(--color-border, #333);
  border-radius: 12px;
  padding: 0.4rem 1rem;
}
.search-icon {
  font-size: 1.2rem;
  margin-right: 0.8rem;
  color: #888;
}
.search-box input {
  border: none !important;
  background: transparent !important;
  font-size: 1.15rem;
  padding: 0.8rem 0;
  width: 100%;
  color: var(--color-text, #fff);
  outline: none;
}
.welcome-state {
  text-align: center;
  padding: 4rem 1rem;
  color: #888;
}
.welcome-state h2 {
  color: #fff;
  font-size: 2rem;
  margin-bottom: 1rem;
}
.welcome-state p {
  font-size: 1.1rem;
}

.spinner-wrap { display: flex; justify-content: center; padding: 3rem; }

/* ─── Hero ─────────────────────────────────── */
.player-hero {
  display: flex;
  gap: 1.5rem;
  align-items: flex-start;
  padding: 1.5rem;
  background: var(--color-surface, #1e1e2e);
  border-radius: 12px;
  margin-bottom: 1.5rem;
  border: 1px solid var(--color-border, #333);
}

.hero-avatar { text-align: center; }

.avatar-circle {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.6rem;
  font-weight: 700;
  color: white;
  margin: 0 auto;
}

.player-badge-pos {
  margin-top: .4rem;
  background: var(--color-accent, #3b82f6);
  color: white;
  border-radius: 4px;
  font-size: .8rem;
  font-weight: 700;
  padding: 4px 8px;
  display: inline-block;
}

.hero-info { flex: 1; }

.hero-name {
  font-size: 2.2rem;
  font-weight: 800;
  color: var(--color-text, #fff);
  margin: 0 0 .4rem 0;
}

.hero-meta {
  color: var(--color-muted, #888);
  font-size: 1rem;
  margin-bottom: 1.2rem;
  display: flex;
  flex-wrap: wrap;
  gap: .4rem;
  align-items: center;
}

.meta-sep { opacity: .4; }
.meta-club { font-weight: 600; color: var(--color-text, #ccc); }

.hero-stats-row {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
}

.hero-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.hero-stat-val {
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--color-text, #fff);
}
.hero-stat-lbl {
  font-size: .8rem;
  color: var(--color-muted, #888);
  text-transform: uppercase;
  letter-spacing: .05em;
}

.rating-val { color: #22c55e !important; }

/* ─── Tabs Nuove e Filtri ───────────────────── */
.tabs-and-filters {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 2px solid var(--color-border, #333);
  margin-bottom: 2rem;
  padding-bottom: 0.8rem;
}

.tabs {
  display: flex;
  gap: 0.5rem;
}

.tab-btn {
  background: transparent;
  border: none;
  color: var(--color-muted, #888);
  cursor: pointer;
  padding: .6rem 1.2rem;
  font-size: 1rem;
  border-radius: 6px;
  transition: all .15s;
}
.tab-btn:hover { background: var(--color-hover, rgba(255,255,255,.06)); color: var(--color-text, #fff); }
.tab-btn.active { background: var(--color-accent, #3b82f6); color: white; font-weight: 600; }

.competition-filter {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  font-size: 1rem;
}

.competition-filter select {
  padding: 0.5rem 1.2rem;
  font-size: 1.05rem;
  background: var(--color-surface, #1e1e2e);
  color: var(--color-text, #fff);
  border: 1px solid var(--color-border, #333);
  border-radius: 8px;
  outline: none;
}

/* ─── Score Card ────────────────────────────── */
.score-card { margin-top: 1rem; }

.score-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

.score-item { display: flex; flex-direction: column; gap: .3rem; }

.score-bar-wrap {
  height: 8px;
  background: var(--color-border, #333);
  border-radius: 4px;
  overflow: hidden;
}
.score-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width .4s ease;
}

.score-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.score-lbl { font-size: .9rem; color: var(--color-muted, #888); }
.score-val { font-size: .95rem; font-weight: 700; }

/* ─── Competition Card ──────────────────────── */
.comp-card { margin-top: 1rem; background: var(--color-surface, #1e1e2e); border: 1px solid var(--color-border, #333); border-radius: 8px; padding: 1.5rem; }

.comp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.comp-league { font-weight: 700; color: var(--color-text, #fff); font-size: 1.2rem; }
.comp-season { color: var(--color-muted, #888); font-size: .9rem; margin-left: .5rem; }

.rating-badge {
  background: #22c55e;
  color: white;
  font-weight: 700;
  font-size: 1rem;
  padding: 4px 10px;
  border-radius: 6px;
}
.rating-badge.small { font-size: .85rem; padding: 3px 8px; }
.rating-great { background: #22c55e !important; }
.rating-good  { background: #3b82f6 !important; }
.rating-ok    { background: #f59e0b !important; }
.rating-bad   { background: #ef4444 !important; }

.presence-row {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
  padding: 1rem;
  background: var(--color-hover, rgba(255,255,255,.04));
  border-radius: 8px;
  margin-bottom: 1.5rem;
}
.pres-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: .2rem;
}
.pres-stat > span {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text, #fff);
}
.pres-stat > label {
  font-size: .75rem;
  color: var(--color-muted, #888);
  text-transform: uppercase;
}
.goals-val   { color: #22c55e !important; }
.assists-val { color: #3b82f6 !important; }

.stat-sections {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
}

.stat-section-title {
  font-weight: 600;
  font-size: .95rem;
  color: var(--color-muted, #888);
  text-transform: uppercase;
  letter-spacing: .05em;
  margin-bottom: .6rem;
  padding-bottom: .3rem;
  border-bottom: 1px solid var(--color-border, #333);
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: .3rem 0;
  font-size: .95rem;
}
.stat-lbl { color: var(--color-muted, #888); }
.stat-val  { font-weight: 600; color: var(--color-text, #fff); }

/* ─── Match Row ─────────────────────────────── */
.match-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: .8rem .5rem;
  border-bottom: 1px solid var(--color-border, #2a2a3a);
  font-size: 1rem;
  flex-wrap: wrap;
}
.match-date      { color: var(--color-muted, #888); min-width: 90px; }
.match-tournament{ color: var(--color-muted, #888); min-width: 110px; font-size: .85rem; }
.match-teams     { flex: 1; display: flex; gap: .8rem; align-items: center; }
.match-score     { font-weight: 700; color: var(--color-text, #fff); padding: 0 .4rem; font-size: 1.1rem;}
.bold            { font-weight: 700; }
.match-perf      { display: flex; gap: .6rem; align-items: center; }
.match-mins      { color: var(--color-muted, #888); font-size: .85rem; }
.match-goal      { color: #22c55e; font-size: .9rem; }
.match-assist    { color: #3b82f6; font-size: .9rem; }
.card-yellow     { font-size: 1rem; }
.card-red        { font-size: 1rem; }

/* ─── Career Timeline ───────────────────────── */
.career-timeline { position: relative; padding-left: 1.5rem; }
.career-item {
  position: relative;
  display: flex;
  gap: 1.2rem;
  padding: .8rem 0;
  border-bottom: 1px solid var(--color-border, #2a2a3a);
  font-size: 1rem;
}
.career-dot {
  position: absolute;
  left: -1.5rem;
  top: 50%;
  transform: translateY(-50%);
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--color-accent, #3b82f6);
}
.career-teams { display: flex; align-items: center; gap: .6rem; font-weight: 600; }
.career-from  { color: var(--color-muted, #888); }
.career-to    { color: var(--color-text, #fff); }
.career-arrow { color: var(--color-accent, #3b82f6); }
.career-meta  { display: flex; gap: 1rem; font-size: .9rem; color: var(--color-muted, #888); margin-top: .2rem; flex-wrap: wrap; }
.career-type  { color: #f59e0b; }
.career-fee   { color: #22c55e; font-weight: 600; }
.career-free  { color: #888; }

/* ─── National ──────────────────────────────── */
.national-row {
  display: flex;
  flex-direction: column;
  gap: .6rem;
  padding: 1rem 0;
  border-bottom: 1px solid var(--color-border, #333);
}
.national-team { font-weight: 700; color: var(--color-text, #fff); font-size: 1.1rem; }
.national-stats { display: flex; gap: 2rem; }

/* ─── Empty ─────────────────────────────────── */
.empty-state {
  text-align: center;
  color: var(--color-muted, #888);
  padding: 2rem;
  font-size: 1rem;
}

/* ─── Autocomplete ──────────────────────────── */
.autocomplete-list {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: var(--color-surface, #1e1e2e);
  border: 1px solid var(--color-border, #333);
  border-radius: 8px;
  list-style: none;
  padding: 0;
  margin-top: 0.5rem;
  z-index: 100;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  max-height: 250px; 
  overflow-y: auto;
}
.autocomplete-list li {
  padding: 1rem 1.2rem;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border, #333);
  text-align: left;
  color: #fff; 
  font-size: 1.05rem;
}
.autocomplete-list li:last-child { border-bottom: none; }
.autocomplete-list li:hover { background: var(--color-accent, #3b82f6); }

.autocomplete-list::-webkit-scrollbar { width: 8px; }
.autocomplete-list::-webkit-scrollbar-track { background: transparent; }
.autocomplete-list::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
</style>