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

    <!-- ══════════════════════ TAB STATISTICHE ══════════════════════ -->
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

      <!-- FIX 1: una sola scheda per competizione selezionata (bestCompetition) -->
      <div v-if="bestCompetition" class="card comp-card">
        <div class="comp-header">
          <div>
            <span class="comp-league">{{ bestCompetition.league }}</span>
            <span class="comp-season">{{ bestCompetition.season }}</span>
          </div>
          <div class="comp-rating" v-if="bestCompetition.sofascore_rating">
            <span class="rating-badge">{{ bestCompetition.sofascore_rating.toFixed(2) }}</span>
          </div>
        </div>

        <div class="presence-row">
          <div class="pres-stat"><span>{{ bestCompetition.appearances ?? '—' }}</span><label>Presenze</label></div>
          <div class="pres-stat"><span>{{ bestCompetition.matches_started ?? '—' }}</span><label>Titolare</label></div>
          <div class="pres-stat"><span>{{ bestCompetition.minutes_played != null ? bestCompetition.minutes_played + "'" : '—' }}</span><label>Minuti</label></div>
          <div class="pres-stat"><span class="goals-val">{{ bestCompetition.goals ?? '—' }}</span><label>Gol</label></div>
          <div class="pres-stat"><span class="assists-val">{{ bestCompetition.assists ?? '—' }}</span><label>Assist</label></div>
        </div>

        <div class="stat-sections">
          <div class="stat-section">
            <div class="stat-section-title">⚽ Tiro</div>
            <div class="stat-row" v-if="bestCompetition.shots_total != null"><span class="stat-lbl">Tiri totali</span><span class="stat-val">{{ bestCompetition.shots_total }}</span></div>
            <div class="stat-row" v-if="bestCompetition.shots_on_target != null"><span class="stat-lbl">In porta</span><span class="stat-val">{{ bestCompetition.shots_on_target }}</span></div>
            <div class="stat-row" v-if="bestCompetition.big_chances_created != null"><span class="stat-lbl">Big chances create</span><span class="stat-val">{{ bestCompetition.big_chances_created }}</span></div>
            <div class="stat-row" v-if="bestCompetition.xg != null"><span class="stat-lbl">xG</span><span class="stat-val">{{ bestCompetition.xg }}</span></div>
            <div class="stat-row" v-if="bestCompetition.xg_per90 != null"><span class="stat-lbl">xG/90</span><span class="stat-val">{{ bestCompetition.xg_per90 }}</span></div>
            <div class="stat-row" v-if="bestCompetition.goal_conversion_pct != null"><span class="stat-lbl">Conversione gol</span><span class="stat-val">{{ bestCompetition.goal_conversion_pct }}%</span></div>
          </div>

          <div class="stat-section">
            <div class="stat-section-title">🎯 Passaggi</div>
            <div class="stat-row" v-if="bestCompetition.accurate_passes != null"><span class="stat-lbl">Acc./Tot.</span><span class="stat-val">{{ bestCompetition.accurate_passes }}/{{ bestCompetition.total_passes }}</span></div>
            <div class="stat-row" v-if="bestCompetition.pass_accuracy_pct != null"><span class="stat-lbl">Precisione</span><span class="stat-val">{{ bestCompetition.pass_accuracy_pct }}%</span></div>
            <div class="stat-row" v-if="bestCompetition.key_passes != null"><span class="stat-lbl">Passaggi chiave</span><span class="stat-val">{{ bestCompetition.key_passes }}</span></div>
            <div class="stat-row" v-if="bestCompetition.xa != null"><span class="stat-lbl">xA</span><span class="stat-val">{{ bestCompetition.xa }}</span></div>
            <div class="stat-row" v-if="bestCompetition.xa_per90 != null"><span class="stat-lbl">xA/90</span><span class="stat-val">{{ bestCompetition.xa_per90 }}</span></div>
            <div class="stat-row" v-if="bestCompetition.accurate_crosses != null"><span class="stat-lbl">Traversoni acc.</span><span class="stat-val">{{ bestCompetition.accurate_crosses }}</span></div>
            <div class="stat-row" v-if="bestCompetition.accurate_long_balls != null"><span class="stat-lbl">Lanci lunghi acc.</span><span class="stat-val">{{ bestCompetition.accurate_long_balls }}</span></div>
          </div>

          <div class="stat-section">
            <div class="stat-section-title">💪 Duelli</div>
            <div class="stat-row" v-if="bestCompetition.total_duels_won_pct != null"><span class="stat-lbl">Duelli vinti</span><span class="stat-val">{{ bestCompetition.total_duels_won_pct }}%</span></div>
            <div class="stat-row" v-if="bestCompetition.aerial_duels_won != null"><span class="stat-lbl">Aerei vinti</span><span class="stat-val">{{ bestCompetition.aerial_duels_won }}</span></div>
            <div class="stat-row" v-if="bestCompetition.aerial_duels_won_pct != null"><span class="stat-lbl">% Aerei</span><span class="stat-val">{{ bestCompetition.aerial_duels_won_pct }}%</span></div>
            <div class="stat-row" v-if="bestCompetition.successful_dribbles != null"><span class="stat-lbl">Dribbling riusciti</span><span class="stat-val">{{ bestCompetition.successful_dribbles }}</span></div>
            <div class="stat-row" v-if="bestCompetition.dribble_success_pct != null"><span class="stat-lbl">% Dribbling</span><span class="stat-val">{{ bestCompetition.dribble_success_pct }}%</span></div>
          </div>

          <div class="stat-section" v-if="bestCompetition.tackles != null || bestCompetition.interceptions != null">
            <div class="stat-section-title">🛡 Difesa</div>
            <div class="stat-row" v-if="bestCompetition.tackles != null"><span class="stat-lbl">Tackle</span><span class="stat-val">{{ bestCompetition.tackles }}</span></div>
            <div class="stat-row" v-if="bestCompetition.tackles_won_pct != null"><span class="stat-lbl">% Tackle vinti</span><span class="stat-val">{{ bestCompetition.tackles_won_pct }}%</span></div>
            <div class="stat-row" v-if="bestCompetition.interceptions != null"><span class="stat-lbl">Intercetti</span><span class="stat-val">{{ bestCompetition.interceptions }}</span></div>
            <div class="stat-row" v-if="bestCompetition.clearances != null"><span class="stat-lbl">Respinte</span><span class="stat-val">{{ bestCompetition.clearances }}</span></div>
            <div class="stat-row" v-if="bestCompetition.ball_recovery != null"><span class="stat-lbl">Palloni recuperati</span><span class="stat-val">{{ bestCompetition.ball_recovery }}</span></div>
          </div>

          <div class="stat-section">
            <div class="stat-section-title">🟨 Disciplina</div>
            <div class="stat-row"><span class="stat-lbl">Ammonizioni</span><span class="stat-val">{{ bestCompetition.yellow_cards ?? 0 }}</span></div>
            <div class="stat-row"><span class="stat-lbl">Espulsioni</span><span class="stat-val">{{ bestCompetition.red_cards ?? 0 }}</span></div>
            <div class="stat-row" v-if="bestCompetition.fouls_committed != null"><span class="stat-lbl">Falli commessi</span><span class="stat-val">{{ bestCompetition.fouls_committed }}</span></div>
            <div class="stat-row" v-if="bestCompetition.fouls_won != null"><span class="stat-lbl">Falli subiti</span><span class="stat-val">{{ bestCompetition.fouls_won }}</span></div>
          </div>

          <div class="stat-section" v-if="bestCompetition.saves != null">
            <div class="stat-section-title">🧤 Portiere</div>
            <div class="stat-row"><span class="stat-lbl">Parate</span><span class="stat-val">{{ bestCompetition.saves }}</span></div>
            <div class="stat-row" v-if="bestCompetition.goals_conceded != null"><span class="stat-lbl">Gol subiti</span><span class="stat-val">{{ bestCompetition.goals_conceded }}</span></div>
            <div class="stat-row" v-if="bestCompetition.clean_sheets != null"><span class="stat-lbl">Clean sheet</span><span class="stat-val">{{ bestCompetition.clean_sheets }}</span></div>
            <div class="stat-row" v-if="bestCompetition.penalty_saved != null"><span class="stat-lbl">Rigori parati</span><span class="stat-val">{{ bestCompetition.penalty_saved }}</span></div>
          </div>
        </div>
      </div>

      <div v-if="!bestCompetition" class="empty-state">
        <p>Nessuna statistica stagionale disponibile per questa competizione.</p>
      </div>
    </div>

    <!-- ══════════════════════ TAB PARTITE ══════════════════════ -->
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
              <polygon v-for="level in [1,0.75,0.5,0.25]" :key="level"
                :points="radarPoints(level)"
                fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>
              <line v-for="(axis, i) in radarAxes" :key="'ax'+i"
                x1="130" y1="130"
                :x2="130 + 110 * Math.cos((i * 2 * Math.PI / radarAxes.length) - Math.PI/2)"
                :y2="130 + 110 * Math.sin((i * 2 * Math.PI / radarAxes.length) - Math.PI/2)"
                stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
              <polygon v-if="averageAttributes"
                :points="radarDataPoints(averageAttributes)"
                fill="rgba(245,158,11,0.15)" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3"/>
              <polygon
                :points="radarDataPoints(playerAttributes)"
                fill="rgba(34,197,94,0.2)" stroke="#22c55e" stroke-width="2"/>
              <circle v-for="(pt, i) in radarDots(playerAttributes)" :key="'dot'+i"
                :cx="pt.x" :cy="pt.y" r="4" fill="#22c55e"/>
              <text v-for="(axis, i) in radarAxes" :key="'lbl'+i"
                :x="radarLabelPos(i).x" :y="radarLabelPos(i).y"
                text-anchor="middle" dominant-baseline="middle"
                fill="rgba(255,255,255,0.7)" font-size="10" font-family="monospace">
                {{ axis.label }}
              </text>
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

      <!-- FIX 2 + FIX 3: heatmap solo della competizione selezionata, campo rettangolare -->
      <div v-if="selectedHeatmapComp" class="card" style="margin-top: 1rem;">
        <h3 class="section-title">
          🗺 Heatmap — {{ selectedHeatmapComp.competition_name }}
          <span class="heat-meta">
            {{ selectedHeatmapComp.heatmap_points?.length ?? 0 }} posizioni
            · {{ selectedHeatmapComp.appearances ?? '?' }} presenze
          </span>
        </h3>
        <div class="heatmap-outer">
          <!-- FIX 3: larghezza massima ridotta + aspect-ratio rettangolare (105:68 ≈ 1.54) -->
          <div class="heatmap-pitch-wrap">
            <svg class="pitch-svg" viewBox="0 0 100 65" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
              <!-- Manto erboso -->
              <rect x="0" y="0" width="100" height="65" fill="#1a4a1a"/>
              <rect x="0" y="0" width="50" height="65" fill="#1e541e"/>
              <!-- Linee campo -->
              <rect x="1.5" y="1.5" width="97" height="62" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <line x1="50" y1="1.5" x2="50" y2="63.5" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <!-- Cerchio centrocampo -->
              <circle cx="50" cy="32.5" r="8.5" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <circle cx="50" cy="32.5" r="0.7" fill="rgba(255,255,255,0.65)"/>
              <!-- Area di rigore sx (16.5m × 40.3m su campo 105×68) -->
              <rect x="1.5" y="13.8" width="15.7" height="37.4" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <!-- Piccola area sx (5.5m × 18.3m) -->
              <rect x="1.5" y="24" width="5.2" height="17" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <!-- Area di rigore dx -->
              <rect x="82.8" y="13.8" width="15.7" height="37.4" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <!-- Piccola area dx -->
              <rect x="93.3" y="24" width="5.2" height="17" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <!-- Punti rigore -->
              <circle cx="10.5" cy="32.5" r="0.55" fill="rgba(255,255,255,0.55)"/>
              <circle cx="89.5" cy="32.5" r="0.55" fill="rgba(255,255,255,0.55)"/>
              <!-- Arco area (approssimato) -->
              <path d="M 17.2 24.5 A 9.15 9.15 0 0 0 17.2 40.5" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="0.5"/>
              <path d="M 82.8 24.5 A 9.15 9.15 0 0 1 82.8 40.5" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="0.5"/>
              <!-- Porte -->
              <rect x="0" y="27.5" width="1.5" height="10.5" fill="none" stroke="rgba(255,255,255,0.65)" stroke-width="0.5"/>
              <rect x="98.5" y="27.5" width="1.5" height="10.5" fill="none" stroke="rgba(255,255,255,0.65)" stroke-width="0.5"/>
            </svg>
            <canvas
              ref="heatmapCanvas"
              class="heatmap-canvas"
              width="700" height="455">
            </canvas>
          </div>
        </div>
      </div>

      <div v-else class="card empty-state" style="margin-top: 1rem;">
        <p>Nessun dato heatmap disponibile per {{ selectedCompetition || 'questa competizione' }}. Rilanciare l'RPA per scaricare i dati.</p>
      </div>
    </div>

    <!-- ══════════════════════ TAB CARRIERA ══════════════════════ -->
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
  if (!id) { matches.value = []; return }
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
// FILTRO COMPETIZIONI
// ══════════════════════════════════════════════

const selectedCompetition = ref('')

// Competizioni uniche disponibili (da league)
const availableCompetitions = computed(() => {
  const comps = new Set()
  if (player.value?.competitions) {
    player.value.competitions.forEach(c => { if (c.league) comps.add(c.league) })
  }
  if (matches.value) {
    matches.value.forEach(m => { if (m.tournament) comps.add(m.tournament) })
  }
  return Array.from(comps).filter(Boolean)
})

// Auto-seleziona la prima competizione disponibile
watch(availableCompetitions, (newComps) => {
  if (newComps.length > 0 && !newComps.includes(selectedCompetition.value)) {
    selectedCompetition.value = newComps[0]
  }
}, { immediate: true })

// FIX 1: bestCompetition → una sola scheda per competizione selezionata.
// Se ci sono più righe con la stessa league (es. sofascore + api_football),
// prendiamo quella con più minuti giocati (fonte più completa).
const bestCompetition = computed(() => {
  if (!player.value?.competitions || !selectedCompetition.value) return null
  const matching = player.value.competitions.filter(c => c.league === selectedCompetition.value)
  if (!matching.length) return null
  // Preferisci quella con più minuti giocati; a parità, la prima (più recente per fetched_at)
  return matching.reduce((best, curr) =>
    (curr.minutes_played ?? 0) > (best.minutes_played ?? 0) ? curr : best
  )
})

const filteredMatches = computed(() => {
  if (!selectedCompetition.value) return matches.value
  return matches.value.filter(m => m.tournament === selectedCompetition.value)
})

// ══════════════════════════════════════════════
// HEATMAP
// ══════════════════════════════════════════════

// Ref per il singolo canvas (non più un dizionario)
const heatmapCanvas = ref(null)

// FIX 2: heatmap solo della competizione selezionata
const selectedHeatmapComp = computed(() => {
  if (!player.value?.competitions || !selectedCompetition.value) return null
  // Cerca la competition con la league selezionata che abbia heatmap_points
  const matching = player.value.competitions.filter(
    c => c.league === selectedCompetition.value && c.heatmap_points?.length > 0
  )
  if (!matching.length) return null
  // Se più righe, prendi quella con più punti heatmap
  return matching.reduce((best, curr) =>
    (curr.heatmap_points?.length ?? 0) > (best.heatmap_points?.length ?? 0) ? curr : best
  )
})

function drawHeatmap() {
  nextTick(() => {
    const canvas = heatmapCanvas.value
    if (!canvas || !selectedHeatmapComp.value) return

    const ctx = canvas.getContext('2d')
    const W = canvas.width
    const H = canvas.height
    ctx.clearRect(0, 0, W, H)

    const points = selectedHeatmapComp.value.heatmap_points || []
    if (!points.length) return

    const maxCount = Math.max(...points.map(p => p.count || 1), 1)

    points.forEach(pt => {
      const px = (pt.x / 100) * W
      const py = (1 - pt.y / 100) * H
      const intensity = Math.min((pt.count || 1) / maxCount, 1)
      const radius = 18 + intensity * 14

      const grad = ctx.createRadialGradient(px, py, 0, px, py, radius)
      const alpha = 0.18 + intensity * 0.55
      grad.addColorStop(0,   `rgba(255, ${Math.round(50 + intensity * 150)}, 0, ${alpha})`)
      grad.addColorStop(0.5, `rgba(255, ${Math.round(100 + intensity * 100)}, 0, ${alpha * 0.5})`)
      grad.addColorStop(1,   'rgba(255, 100, 0, 0)')

      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(px, py, radius, 0, Math.PI * 2)
      ctx.fill()
    })
  })
}

// Ridisegna quando cambia tab, competizione o dati
watch(activeTab, (tab) => {
  if (tab === 'heatmap') drawHeatmap()
  if (tab === 'matches' && !matches.value.length && route.params.id) loadMatches()
})
watch(selectedCompetition, () => {
  if (activeTab.value === 'heatmap') drawHeatmap()
})
watch(selectedHeatmapComp, () => {
  if (activeTab.value === 'heatmap') drawHeatmap()
})

watch(() => route.params.id, (newId) => {
  if (newId) {
    loadPlayer()
    if (activeTab.value === 'matches') loadMatches()
  } else {
    player.value = null
    matches.value = []
    activeTab.value = 'stats'
  }
})

onMounted(() => { loadPlayer() })

// ══════════════════════════════════════════════
// ATTRIBUTI SOFASCORE
// ══════════════════════════════════════════════

const playerAttributes = computed(() => {
  const attrs = player.value?.sofascore_attributes
  if (!attrs) return null
  if (Array.isArray(attrs) && attrs.length > 0) {
    return attrs.reduce((best, curr) => 
      (curr.yearShift ?? 0) > (best.yearShift ?? 0) ? curr : best
    )
  }
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

// CORRETTO — stessa logica di playerAttributes
const averageAttributes = computed(() => {
  const raw = player.value?.sofascore_attributes_avg
  if (!raw) return null
  // Formato oggetto piatto (RPA v9)
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const mapped = {}
    for (const [k, v] of Object.entries(raw)) {
      if (k.startsWith('attr_') && !k.startsWith('attr_title_') && !k.startsWith('attr_avg_')) {
        mapped[k.replace('attr_', '')] = v
      }
    }
    return Object.keys(mapped).length ? mapped : null
  }
  // Formato array legacy
  if (Array.isArray(raw) && raw.length > 0) return raw[0]
  return null
})

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

// ══════════════════════════════════════════════
// UTILITY
// ══════════════════════════════════════════════

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

// --- RICERCA ---
const searchQuery = ref('')
const searchResults = ref([])
let searchTimeout = null
const onSearch = () => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(async () => {
    if (searchQuery.value.length < 3) { searchResults.value = []; return }
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
</script>

<style scoped>
.player-detail {
  max-width: 1000px;
  margin: 0 auto;
  padding: 1rem;
  font-size: 1.05rem; 
}
.player-header {
  padding: 2rem;
  background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.8));
  border-bottom: 1px solid rgba(255,255,255,0.1);
  color: #ffffff; /* Assicura che tutto il testo dentro l'header sia bianco di base */
}
/* ─── Search Header ──────────────────────────────── */
.search-header { margin-bottom: 2rem; }
.search-box { position: relative; }
.search-input-wrapper {
  display: flex;
  align-items: center;
  background: var(--color-surface, #1e1e2e);
  border: 1px solid var(--color-border, #333);
  border-radius: 12px;
  padding: 0.4rem 1rem;
}
.search-icon { font-size: 1.2rem; margin-right: 0.8rem; color: #888; }
.search-box input {
  border: none !important;
  background: transparent !important;
  font-size: 1.15rem;
  padding: 0.8rem 0;
  width: 100%;
  color: var(--color-text, #fff);
  outline: none;
}

/* ─── Tabs & Filters ─────────────────────────────── */
.tabs-and-filters {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.competition-badge {
  background: rgba(59, 130, 246, 0.2); /* Sfondo blu trasparente */
  color: #60a5fa; /* Blu chiaro */
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(96, 165, 250, 0.3);
}
.competition-filter {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.95rem;
  color: var(--color-muted, #888);
}
.competition-filter select {
  background: var(--color-surface, #1e1e2e);
  border: 1px solid var(--color-border, #444);
  border-radius: 8px;
  padding: 0.35rem 0.7rem;
  color: var(--color-text, #fff);
  font-size: 0.95rem;
  cursor: pointer;
}
.tabs { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.tab-btn {
  background: var(--color-surface, #1e1e2e);
  border: 1px solid var(--color-border, #444);
  border-radius: 8px;
  color: var(--color-muted, #aaa);
  cursor: pointer;
  font-size: 0.95rem;
  padding: 0.4rem 0.9rem;
  transition: all 0.15s;
}
.tab-btn.active {
  background: var(--color-accent, #3b82f6);
  border-color: var(--color-accent, #3b82f6);
  color: #fff;
}

/* ─── Hero ───────────────────────────────────────── */
.player-hero {
  display: flex;
  align-items: flex-start;
  gap: 1.5rem;
  background: var(--color-surface, #1e1e2e);
  border-radius: 16px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  border: 1px solid var(--color-border, #333);
}
.hero-avatar { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; }
.avatar-circle {
  width: 72px; height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-accent, #3b82f6), #6366f1);
  display: flex; align-items: center; justify-content: center;
}
.avatar-initial { font-size: 2rem; font-weight: 700; color: #fff; }
/* Il badge della posizione (Difensore, etc) */
.player-badge-pos {
  background: var(--color-accent, #3b82f6);
  color: #FFFFFF;
  border-radius: 6px;
  padding: 0.15rem 0.5rem;
  font-size: 0.8rem;
  font-weight: bold;
}

.hero-info { flex: 1; }
/* Nome del giocatore (Leonardo Spinazzola) */
.hero-name {
  color: #FFFFFF !important;
  font-size: 2.2rem !important;
  font-weight: 800 !important;
  margin: 0 0 0.5rem 0 !important;
  text-shadow: 0 2px 10px rgba(0,0,0,0.8) !important;
}
.hero-meta { display: flex; flex-wrap: wrap; gap: 0.4rem; color: var(--color-muted, #F8FAFC); font-size: 0.95rem; margin-bottom: 0.8rem; }

.meta-sep { color: var(--color-border, #555); }
.meta-club { color: var(--color-text, #fff); }
.hero-stats-row { display: flex; gap: 1.2rem; flex-wrap: wrap; }
.hero-stat { display: flex; flex-direction: column; align-items: center; gap: 0.1rem; }

/* I valori delle statistiche (Altezza, Peso, Maglia, Rating) */
.hero-stat-val {
  color: #FFFFFF !important;
  font-size: 1.2rem !important;
  font-weight: 700 !important;
  display: block !important;
}
/* .hero-stat-lbl { font-size: 0.75rem; color: var(--color-muted, #8381a7); } */
/* Le etichette sotto i valori (Altezza, Peso, Maglia) */
.hero-stat-lbl {
  color: #94A3B8 !important; /* Azzurro polvere leggibile */
  font-size: 0.8rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.5px !important;
}
/* .rating-val { color: #22c55e; } */
/* Speciale per il valore del Rating se vuoi che sia giallo/oro */
.rating-val {
  color: #FBBF24 !important; /* Giallo ambra per farlo risaltare */
}
/* ─── Card ───────────────────────────────────────── */
.card {
  background: var(--color-surface, #1e1e2e);
  border: 1px solid var(--color-border, #333);
  border-radius: 14px;
  padding: 1.2rem 1.4rem;
  margin-top: 1rem;
}
.section-title {
  font-size: 1.05rem;
  font-weight: 700;
  margin: 0 0 1rem;
  border-bottom: 1px solid rgba(96,165,250,0.2);
  padding-bottom: 4px;
  color: var(--color-text, #60A5FA); /* Titoli sezioni in blu chiaro per ordine visivo */
}

/* ─── Score card ─────────────────────────────────── */
.score-card { margin-top: 0; }
.score-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.8rem;
}
.score-item { display: flex; flex-direction: column; gap: 0.3rem; }
.score-bar-wrap {
  height: 8px;
  background: rgba(255,255,255,0.08);
  border-radius: 4px;
  overflow: hidden;
}
.score-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
.score-labels { display: flex; justify-content: space-between; font-size: 0.88rem; }
.score-lbl { color: var(--color-muted, #aaa); }
.score-val { font-weight: 700; }

/* ─── Comp card ──────────────────────────────────── */
.comp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.8rem;
}
.comp-league { color: #fff; font-weight: 750; font-size: 1.5rem; margin-right: 0.5rem; }
.comp-season { font-size: 0.95rem; color: var(--color-muted, #fff); }
.rating-badge {
  background: #22c55e;
  color: #fff;
  border-radius: 8px;
  padding: 0.2rem 0.6rem;
  font-weight: 700;
  font-size: 0.95rem;
}
.rating-badge.small { font-size: 0.82rem; padding: 0.1rem 0.4rem; }
.rating-great { background: #22c55e; }
.rating-good  { background: #3b82f6; }
.rating-ok    { background: #f59e0b; }
.rating-bad   { background: #ef4444; }

.presence-row {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  padding-bottom: 0.8rem;
  border-bottom: 1px solid var(--color-border, #333);
}
/* I numeri devono essere bianchi */
.pres-stat { color: #FFFFFF !important; display: flex; flex-direction: column; align-items: center; gap: 0.2rem; }
.pres-stat span { font-size: 1.2rem; font-weight: 700; }
.pres-stat label { font-size: 0.75rem; color: var(--color-muted, #888); }
.goals-val  { color: #22c55e; }
.assists-val{ color: #3b82f6; }

.stat-sections {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1.2rem;
}
.stat-section-title {
  font-size: 0.82rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-muted, #888);
  margin-bottom: 0.5rem;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.9rem;
  padding: 0.2rem 0;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.stat-lbl { color: var(--color-muted, #94A3B8); }
.stat-val  { font-weight: 600; color: #FFFFFF !important; /* I numeri devono essere bianchi */ }

/* ─── Match rows ─────────────────────────────────── */
/* 4. RIGHE PARTITE (Match History) */
.match-row {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--color-border, #f3f0f0);
  flex-wrap: wrap;
  font-size: 0.9rem;
}
.match-date     { color: var(--color-muted, #94A3B8); min-width: 80px; }
.match-tournament{ color: var(--color-muted, #94A3B8); font-size: 0.82rem; min-width: 80px; }
.match-teams    { display: flex; align-items: center; gap: 0.4rem; flex: 1; }
.match-score    { color: #FFFFFF !important; font-weight: 700; padding: 2px 6px; border-radius: 4px;}
.match-perf     { display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }
.match-mins     { color: var(--color-muted, #888); font-size: 0.85rem; }
.match-goal     { color: #22c55e; font-size: 0.85rem; }
.match-assist   { color: #3b82f6; font-size: 0.85rem; }
.bold           { font-weight: 700; }

/* ─── Career ─────────────────────────────────────── */
.career-timeline { display: flex; flex-direction: column; gap: 0; }
.career-item {
  display: flex;
  gap: 1rem;
  padding: 0.8rem 0;
  border-bottom: 1px solid var(--color-border, #333);
}
.career-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: var(--color-accent, #3b82f6);
  margin-top: 5px;
  flex-shrink: 0;
}
.career-teams { display: flex; align-items: center; gap: .6rem; font-weight: 600; }
.career-from  { color: var(--color-muted, #94A3B8); }
.career-to    { color: var(--color-text, #fff); font-weight: 700 !important;}
.career-arrow { color: var(--color-accent, #3b82f6); }
.career-meta  { display: flex; gap: 1rem; font-size: .9rem; color: var(--color-muted, #CBD5E1); margin-top: .2rem; flex-wrap: wrap; }
.career-type  { color: #f59e0b; }
.career-fee   { color: #4ADE80; font-weight: 600; }
.career-free  { color: #888; }

/* ─── National ───────────────────────────────────── */
.national-row {
  display: flex; flex-direction: column; gap: .6rem;
  padding: 1rem 0;
  border-bottom: 1px solid var(--color-border, #333);
}
.national-team  { font-weight: 700; color: var(--color-text, #fff); font-size: 1.1rem; }
.national-stats { display: flex; gap: 2rem; }

/* ─── Empty / Welcome ────────────────────────────── */
.empty-state {
  text-align: center;
  color: var(--color-muted, #888);
  padding: 2rem;
  font-size: 1rem;
}
.welcome-state {
  text-align: center;
  padding: 4rem 2rem;
  color: var(--color-muted, #888);
}
.spinner-wrap { display: flex; justify-content: center; padding: 3rem; }
.spinner {
  width: 40px; height: 40px;
  border: 3px solid var(--color-border, #333);
  border-top-color: var(--color-accent, #3b82f6);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #ef4444; padding: 1rem; text-align: center; }

/* ─── Heatmap ────────────────────────────────────── */
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

/* FIX 3: campo rettangolare, max-width ridotto */
.heatmap-pitch-wrap {
  position: relative;
  width: 100%;
  max-width: 380px;          /* era 560px — rimpicciolito */
  aspect-ratio: 105 / 68;   /* proporzioni reali campo da calcio */
  border-radius: 6px;
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

/* ─── Attributi radar ────────────────────────────── */
.attributes-layout {
  display: flex;
  gap: 2rem;
  align-items: center;
  flex-wrap: wrap;
  padding: .5rem 0;
}
.radar-wrap { flex: 0 0 260px; }
.radar-svg  { width: 260px; height: 260px; }
.attr-bars  { flex: 1; min-width: 200px; display: flex; flex-direction: column; gap: .7rem; }
.attr-bar-row { display: flex; align-items: center; gap: .6rem; }
.attr-bar-lbl {
  width: 36px; font-size: .8rem; font-weight: 700;
  color: var(--color-muted, #888);
  text-transform: uppercase; letter-spacing: .05em; flex-shrink: 0;
}
.attr-bar-track {
  flex: 1; height: 8px;
  background: rgba(255,255,255,0.08);
  border-radius: 4px; overflow: hidden;
}
.attr-bar-fill { height: 100%; border-radius: 4px; transition: width .5s ease; }
.attr-bar-val  { width: 28px; font-size: .9rem; font-weight: 700; text-align: right; flex-shrink: 0; }
.attr-avg-val  { width: 48px; font-size: .78rem; color: #f59e0b; flex-shrink: 0; }
.attr-note     { font-size: .75rem; color: var(--color-muted, #666); margin-top: .4rem; }

/* ─── Autocomplete ───────────────────────────────── */
.autocomplete-list {
  position: absolute;
  top: 100%; left: 0; right: 0;
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
  color: #fff;
  font-size: 1.05rem;
}
.autocomplete-list li:last-child { border-bottom: none; }
.autocomplete-list li:hover { background: var(--color-accent, #3b82f6); }
.autocomplete-list::-webkit-scrollbar { width: 8px; }
.autocomplete-list::-webkit-scrollbar-track { background: transparent; }
.autocomplete-list::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
.text-muted { color: var(--color-muted, #888); font-size: 0.88rem; }
</style>