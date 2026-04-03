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
        <button class="tab-btn" :class="{ active: activeTab === 'heatmap' }" @click="activeTab = 'heatmap'">🗺 Heatmap</button>
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

    <!-- ══════════════════════ TAB HEATMAP & ATTRIBUTI ══════════════════════ -->
    <div v-if="activeTab === 'heatmap' && player && !loading">

      <!-- Radar attributi -->
      <div class="card" style="margin-top: 1rem;" v-if="playerAttributes">
        <h3 class="section-title">🎯 Panoramica attributi</h3>
        <div class="attributes-layout">
          <div class="radar-wrap">
            <svg class="radar-svg" viewBox="0 0 260 260" xmlns="http://www.w3.org/2000/svg">
              <!-- Griglia di sfondo -->
              <polygon v-for="level in [1,0.75,0.5,0.25]" :key="level"
                :points="radarPoints(level)"
                fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>
              <!-- Assi -->
              <line v-for="(axis, i) in radarAxes" :key="'ax'+i"
                x1="130" y1="130"
                :x2="130 + 110 * Math.cos((i * 2 * Math.PI / radarAxes.length) - Math.PI/2)"
                :y2="130 + 110 * Math.sin((i * 2 * Math.PI / radarAxes.length) - Math.PI/2)"
                stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
              <!-- Media (arancio) -->
              <polygon v-if="averageAttributes"
                :points="radarDataPoints(averageAttributes)"
                fill="rgba(245,158,11,0.15)" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3"/>
              <!-- Giocatore (verde) -->
              <polygon
                :points="radarDataPoints(playerAttributes)"
                fill="rgba(34,197,94,0.2)" stroke="#22c55e" stroke-width="2"/>
              <!-- Dots giocatore -->
              <circle v-for="(pt, i) in radarDots(playerAttributes)" :key="'dot'+i"
                :cx="pt.x" :cy="pt.y" r="4" fill="#22c55e"/>
              <!-- Label assi -->
              <text v-for="(axis, i) in radarAxes" :key="'lbl'+i"
                :x="radarLabelPos(i).x" :y="radarLabelPos(i).y"
                text-anchor="middle" dominant-baseline="middle"
                fill="rgba(255,255,255,0.7)" font-size="10" font-family="monospace">
                {{ axis.label }}
              </text>
              <!-- Valori giocatore -->
              <text v-for="(axis, i) in radarAxes" :key="'val'+i"
                :x="radarValuePos(i, playerAttributes).x" :y="radarValuePos(i, playerAttributes).y"
                text-anchor="middle" dominant-baseline="middle"
                fill="#22c55e" font-size="11" font-weight="700" font-family="monospace">
                {{ playerAttributes[axis.key] ?? '—' }}
              </text>
            </svg>
          </div>
          <div class="attr-bars">
            <div v-for="axis in radarAxes" :key="axis.key" class="attr-bar-row">
              <span class="attr-bar-lbl">{{ axis.label }}</span>
              <div class="attr-bar-track">
                <div class="attr-bar-fill" :style="{
                  width: ((playerAttributes[axis.key] || 0) / 99 * 100) + '%',
                  background: attrColor(playerAttributes[axis.key])
                }"></div>
              </div>
              <span class="attr-bar-val" :style="{ color: attrColor(playerAttributes[axis.key]) }">
                {{ playerAttributes[axis.key] ?? '—' }}
              </span>
              <span class="attr-avg-val" v-if="averageAttributes">
                ⌀ {{ averageAttributes[axis.key] ?? '—' }}
              </span>
            </div>
            <p class="attr-note">🟠 Media SofaScore &nbsp;|&nbsp; 🟢 Giocatore</p>
          </div>
        </div>
      </div>
      <div class="card empty-state" style="margin-top: 1rem;" v-else>
        <p>Dati attributi non disponibili per questo giocatore.</p>
      </div>

      <!-- Heatmap per competizione -->
      <div v-for="comp in heatmapCompetitions" :key="comp.competition_id" class="card" style="margin-top: 1rem;">
        <h3 class="section-title">
          🗺 Heatmap — {{ comp.competition_name }}
          <span class="heat-meta">{{ comp.heatmap_points?.length ?? 0 }} posizioni · {{ comp.appearances ?? '?' }} presenze</span>
        </h3>
        <div class="heatmap-outer">
          <div class="heatmap-pitch-wrap">
            <!-- Campo da calcio SVG -->
            <svg class="pitch-svg" viewBox="0 0 100 100" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
              <!-- Manto erboso -->
              <rect x="0" y="0" width="100" height="100" fill="#1a4a1a"/>
              <rect x="0" y="0" width="50" height="100" fill="#1e541e"/>
              <!-- Linee campo -->
              <rect x="2" y="2" width="96" height="96" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="0.5"/>
              <line x1="50" y1="2" x2="50" y2="98" stroke="rgba(255,255,255,0.5)" stroke-width="0.5"/>
              <!-- Cerchio centrocampo -->
              <circle cx="50" cy="50" r="9.15" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="0.5"/>
              <circle cx="50" cy="50" r="0.8" fill="rgba(255,255,255,0.6)"/>
              <!-- Area di rigore sx -->
              <rect x="2" y="21.1" width="16.5" height="57.8" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="0.5"/>
              <!-- Piccola area sx -->
              <rect x="2" y="36.8" width="5.5" height="26.4" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="0.5"/>
              <!-- Area di rigore dx -->
              <rect x="81.5" y="21.1" width="16.5" height="57.8" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="0.5"/>
              <!-- Piccola area dx -->
              <rect x="92.5" y="36.8" width="5.5" height="26.4" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="0.5"/>
              <!-- Punti rigore -->
              <circle cx="11" cy="50" r="0.6" fill="rgba(255,255,255,0.5)"/>
              <circle cx="89" cy="50" r="0.6" fill="rgba(255,255,255,0.5)"/>
            </svg>
            <!-- Canvas overlay per heatmap -->
            <canvas
              :ref="el => heatmapCanvases[comp.competition_id] = el"
              class="heatmap-canvas"
              width="600" height="600">
            </canvas>
          </div>
        </div>
      </div>

      <div v-if="!heatmapCompetitions.length" class="card empty-state" style="margin-top: 1rem;">
        <p>Nessun dato heatmap disponibile. Rilanciare l'RPA per scaricare i dati.</p>
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
import { ref, computed, onMounted, watch, nextTick } from 'vue'
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

// ══════════════════════════════════════════════
// HEATMAP & ATTRIBUTI
// ══════════════════════════════════════════════

const heatmapCanvases = ref({})

// Competizioni con heatmap disponibile
const heatmapCompetitions = computed(() => {
  if (!player.value?.competitions) return []
  return player.value.competitions.filter(c => c.heatmap_points?.length > 0)
})

// Attributi del giocatore (prende il più recente: yearShift più alto o primo elemento)
const playerAttributes = computed(() => {
  const attrs = player.value?.sofascore_attributes
  if (!attrs) return null
  // Struttura: array di {attacking, technical, tactical, defending, creativity, ...}
  if (Array.isArray(attrs) && attrs.length > 0) {
    // Prende quello con yearShift più alto (più recente)
    return attrs.reduce((best, curr) => 
      (curr.yearShift ?? 0) > (best.yearShift ?? 0) ? curr : best
    )
  }
  // Fallback: struttura piatta già come oggetto (attr_attacking, ecc.)
  if (typeof attrs === 'object' && !Array.isArray(attrs)) {
    const mapped = {}
    for (const [k, v] of Object.entries(attrs)) {
      if (k.startsWith('attr_') && !k.startsWith('attr_title_') && !k.startsWith('attr_avg_')) {
        mapped[k.replace('attr_', '')] = v
      }
    }
    return Object.keys(mapped).length ? mapped : null
  }
  return null
})

// Media attributi (averageAttributeOverviews)
const averageAttributes = computed(() => {
  const raw = player.value?.sofascore_attributes_avg
  if (!raw) return null
  if (Array.isArray(raw) && raw.length > 0) return raw[0]
  return null
})

// Assi del radar
const radarAxes = [
  { key: 'attacking',  label: 'ATT' },
  { key: 'technical',  label: 'TEC' },
  { key: 'tactical',   label: 'TAC' },
  { key: 'defending',  label: 'DEF' },
  { key: 'creativity', label: 'CRE' },
]

function radarPoints(scale = 1) {
  const cx = 130, cy = 130, r = 110 * scale, n = radarAxes.length
  return radarAxes.map((_, i) => {
    const angle = (i * 2 * Math.PI / n) - Math.PI / 2
    return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`
  }).join(' ')
}

function radarDataPoints(attrs) {
  const cx = 130, cy = 130, r = 110, n = radarAxes.length, MAX = 99
  return radarAxes.map((axis, i) => {
    const val = (attrs[axis.key] ?? 0) / MAX
    const angle = (i * 2 * Math.PI / n) - Math.PI / 2
    return `${cx + r * val * Math.cos(angle)},${cy + r * val * Math.sin(angle)}`
  }).join(' ')
}

function radarDots(attrs) {
  const cx = 130, cy = 130, r = 110, n = radarAxes.length, MAX = 99
  return radarAxes.map((axis, i) => {
    const val = (attrs[axis.key] ?? 0) / MAX
    const angle = (i * 2 * Math.PI / n) - Math.PI / 2
    return { x: cx + r * val * Math.cos(angle), y: cy + r * val * Math.sin(angle) }
  })
}

function radarLabelPos(i) {
  const cx = 130, cy = 130, r = 128, n = radarAxes.length
  const angle = (i * 2 * Math.PI / n) - Math.PI / 2
  return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) }
}

function radarValuePos(i, attrs) {
  const cx = 130, cy = 130, r = 110, n = radarAxes.length, MAX = 99
  const val = (attrs[radarAxes[i].key] ?? 0) / MAX
  const angle = (i * 2 * Math.PI / n) - Math.PI / 2
  // Posiziona il valore leggermente più esterno del punto
  const dist = Math.max(r * val - 14, 20)
  return { x: cx + dist * Math.cos(angle), y: cy + dist * Math.sin(angle) }
}

function attrColor(val) {
  if (val == null) return '#666'
  if (val >= 75) return '#22c55e'
  if (val >= 55) return '#3b82f6'
  if (val >= 40) return '#f59e0b'
  return '#ef4444'
}

// Disegna la heatmap su canvas quando la tab viene attivata
function drawHeatmaps() {
  nextTick(() => {
    heatmapCompetitions.value.forEach(comp => {
      const canvas = heatmapCanvases.value[comp.competition_id]
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      const W = canvas.width, H = canvas.height
      ctx.clearRect(0, 0, W, H)

      const points = comp.heatmap_points || []
      if (!points.length) return

      // Trova max count per normalizzare l'intensità
      const maxCount = Math.max(...points.map(p => p.count || 1), 1)

      points.forEach(pt => {
        // SofaScore: x=avanzamento (0=porta sx, 100=porta dx), y=larghezza (0=sotto, 100=sopra)
        const px = (pt.x / 100) * W
        const py = (1 - pt.y / 100) * H
        const intensity = Math.min((pt.count || 1) / maxCount, 1)
        const radius = 22 + intensity * 18

        const grad = ctx.createRadialGradient(px, py, 0, px, py, radius)
        const alpha = 0.15 + intensity * 0.55
        grad.addColorStop(0, `rgba(255, ${Math.round(50 + intensity * 150)}, 0, ${alpha})`)
        grad.addColorStop(0.5, `rgba(255, ${Math.round(100 + intensity * 100)}, 0, ${alpha * 0.5})`)
        grad.addColorStop(1, 'rgba(255, 100, 0, 0)')

        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.arc(px, py, radius, 0, Math.PI * 2)
        ctx.fill()
      })
    })
  })
}

watch(activeTab, (tab) => {
  if (tab === 'heatmap') drawHeatmaps()
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

/* ─── Heatmap & Attributi ───────────────────── */
.heat-meta {
  font-size: .78rem;
  color: var(--color-muted, #888);
  font-weight: 400;
  margin-left: .6rem;
}

.heatmap-outer {
  display: flex;
  justify-content: center;
  padding: .5rem 0 1rem;
}

.heatmap-pitch-wrap {
  position: relative;
  width: 100%;
  max-width: 560px;
  aspect-ratio: 1 / 1;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}

.pitch-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.heatmap-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

/* Radar + barre fianco a fianco */
.attributes-layout {
  display: flex;
  gap: 2rem;
  align-items: center;
  flex-wrap: wrap;
  padding: .5rem 0;
}

.radar-wrap {
  flex: 0 0 260px;
}

.radar-svg {
  width: 260px;
  height: 260px;
}

.attr-bars {
  flex: 1;
  min-width: 200px;
  display: flex;
  flex-direction: column;
  gap: .7rem;
}

.attr-bar-row {
  display: flex;
  align-items: center;
  gap: .6rem;
}

.attr-bar-lbl {
  width: 36px;
  font-size: .8rem;
  font-weight: 700;
  color: var(--color-muted, #888);
  text-transform: uppercase;
  letter-spacing: .05em;
  flex-shrink: 0;
}

.attr-bar-track {
  flex: 1;
  height: 8px;
  background: rgba(255,255,255,0.08);
  border-radius: 4px;
  overflow: hidden;
}

.attr-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width .5s ease;
}

.attr-bar-val {
  width: 28px;
  font-size: .9rem;
  font-weight: 700;
  text-align: right;
  flex-shrink: 0;
}

.attr-avg-val {
  width: 48px;
  font-size: .78rem;
  color: #f59e0b;
  flex-shrink: 0;
}

.attr-note {
  font-size: .75rem;
  color: var(--color-muted, #666);
  margin-top: .4rem;
}

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