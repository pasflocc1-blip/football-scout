<template>
  <div class="player-detail">

    <!-- ── Barra di ricerca ── -->
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

    <!-- ── Welcome state ── -->
    <div v-if="!player && !loading && !error && !route.params.id" class="welcome-state">
      <h2>Benvenuto nello Scouting</h2>
      <p>Cerca un calciatore usando la barra qui sopra per visualizzare la sua scheda.</p>
    </div>

    <div v-if="loading" class="spinner-wrap"><div class="spinner"></div></div>
    <div v-if="error" class="error-msg">⚠️ {{ error }}</div>

    <!-- ══════════════ HERO ══════════════ -->
    <div v-if="player && !loading" class="player-hero">
      <div class="hero-avatar">
        <div class="avatar-circle">
          <span class="avatar-initial">{{ player.profile?.name?.charAt(0) }}</span>
        </div>
        <div class="player-badge-pos">{{ player.profile?.position ?? '—' }}</div>
      </div>
      <div class="hero-info">
        <h1 class="hero-name">{{ player.profile?.name }}</h1>
        <div class="hero-meta">
          <span class="meta-club">🏟 {{ player.profile?.club ?? '—' }}</span>
          <span class="meta-sep">·</span>
          <span>{{ player.profile?.nationality ?? '—' }}</span>
          <span class="meta-sep">·</span>
          <span>{{ player.profile?.age ?? '—' }} anni</span>
          <span v-if="player.profile?.preferred_foot" class="meta-sep">·</span>
          <span v-if="player.profile?.preferred_foot">
            {{ player.profile.preferred_foot === 'Left' ? '🦶 Mancino'
              : player.profile.preferred_foot === 'Right' ? '🦶 Destro'
              : player.profile.preferred_foot }}
          </span>
        </div>
        <div class="hero-stats-row">
          <div class="hero-stat">
            <span class="hero-stat-val">{{ player.profile?.height ? player.profile.height + ' cm' : '—' }}</span>
            <span class="hero-stat-lbl">Altezza</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-val">{{ player.profile?.weight ? player.profile.weight + ' kg' : '—' }}</span>
            <span class="hero-stat-lbl">Peso</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-val">{{ player.profile?.jersey_number ? '#' + player.profile.jersey_number : '—' }}</span>
            <span class="hero-stat-lbl">Maglia</span>
          </div>
          <div class="hero-stat" v-if="player.profile?.market_value">
            <span class="hero-stat-val">{{ player.profile.market_value }}M €</span>
            <span class="hero-stat-lbl">Valore</span>
          </div>
          <div class="hero-stat" v-if="player.profile?.sofascore_rating">
            <span class="hero-stat-val rating-val">{{ player.profile.sofascore_rating }}</span>
            <span class="hero-stat-lbl">Rating SS</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════
         HOME PAGE CALCIATORE — Dati sempre visibili all'ingresso
         1a) Dati Anagrafici (hero sopra)
         1b) Dati Algoritmo
         1c) Dati Fonti (SofaScore + FBref per competizione selezionata)
    ═══════════════════════════════════════════════════════════════ -->
    <div v-if="player && !loading && activeTab === 'home'">

      <!-- ── 1b) Dati Algoritmo ── -->
      <div class="section-divider">🧠 Dati Algoritmo</div>
      <div v-if="!scouting" class="card empty-state">
        <p>⚙️ Indici non ancora calcolati. Importa i dati FBref e/o SofaScore, poi lancia il ricalcolo.</p>
      </div>
      <div v-else>
        <div class="card algo-header-card">
          <div class="algo-meta-row">
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Stagione</span>
              <span class="algo-meta-val">{{ scouting.season }}</span>
            </div>
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Ruolo</span>
              <span class="algo-meta-val">{{ scouting.position_group ?? '—' }}</span>
            </div>
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Minuti</span>
              <span class="algo-meta-val">{{ scouting.minutes_sample ?? '—' }}'</span>
            </div>
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Confidenza</span>
              <span class="algo-meta-val" :style="{ color: confidenceColor(scouting.data_confidence) }">
                {{ scouting.data_confidence != null ? (scouting.data_confidence * 100).toFixed(0) + '%' : '—' }}
              </span>
            </div>
            <div class="algo-meta-item" v-if="scouting.sources_used?.length">
              <span class="algo-meta-lbl">Fonti</span>
              <span class="algo-meta-val sources-list">
                <span v-for="s in scouting.sources_used" :key="s"
                  class="source-badge" :class="'source-' + s">{{ s }}</span>
              </span>
            </div>
          </div>
        </div>

<div class="card compact-algo-card" v-if="scouting.overall_index != null">
          <h3 class="section-title">🧠 Parametri Intelligenti</h3>

          <div class="overall-inline-row">
            <div class="overall-inline-info">
              <span class="overall-inline-label">Indice Complessivo</span>
              <span class="overall-inline-value" :style="{ color: scoreColor(scouting.overall_index) }">
                {{ scouting.overall_index.toFixed(1) }}
              </span>
            </div>
            <div class="overall-inline-bar-track">
              <div class="overall-inline-bar-fill"
                :style="{ width: scouting.overall_index + '%', background: scoreColor(scouting.overall_index) }">
              </div>
            </div>
            <div class="overall-inline-sub">Percentile nel gruppo ruolo</div>
          </div>

          <div class="score-grid">
            <div v-for="item in algoItems" :key="item.key" class="score-item">
              <div class="score-bar-wrap">
                <div class="score-bar-fill"
                  :style="{ width: (scouting[item.key] || 0) + '%', background: scoreColor(scouting[item.key]) }">
                </div>
              </div>
              <div class="score-labels">
                <span class="score-lbl">
                  {{ item.label }}
                  <span class="tooltip-wrap">
                    <span class="tooltip-icon">ℹ</span>
                    <span class="tooltip-box">
                      <strong>{{ item.label }}</strong>
                      {{ item.tooltip }}<br>
                      <span class="tooltip-sources">Fonti: {{ item.sources }}</span>
                    </span>
                  </span>
                </span>
                <span class="score-val" :style="{ color: scoreColor(scouting[item.key]) }">
                  {{ scouting[item.key] != null ? scouting[item.key].toFixed(1) : '—' }}
                </span>
              </div>
              <div class="raw-metrics" v-if="scouting.raw">
                <template v-for="mk in item.raw_keys" :key="mk.k">
                  <span v-if="scouting.raw[mk.k] != null" class="raw-metric">
                    {{ mk.label }}: <strong>{{ typeof scouting.raw[mk.k] === 'number' ? scouting.raw[mk.k].toFixed(2) : scouting.raw[mk.k] }}</strong>
                  </span>
                </template>
              </div>
            </div>
          </div>

          <!-- Legenda fonti -->
          <div class="algo-legend">
            <span class="legend-dot fbref"></span> FBref (metriche avanzate)
            <span class="legend-dot sofa" style="margin-left:1rem"></span> SofaScore (pressing, duelli, dribbling)
            <span class="legend-note">Percentile nel gruppo-ruolo (0 = ultimo, 100 = migliore)</span>
          </div>
        </div>


      </div>

      <!-- ── 1c) Dati Fonti ── -->
      <div class="section-divider">📂 Dati Fonti</div>

      <!-- Filtro competizione per le Fonti nella Home -->
      <div class="competition-filter-inline">
        <label>Competizione:</label>
        <select v-model="selectedCompetition">
          <option v-for="comp in availableCompetitions" :key="comp" :value="comp">{{ comp }}</option>
        </select>
      </div>

      <!-- SofaScore per competizione selezionata -->
      <div v-if="bestSofaComp" class="card comp-card">
        <div class="comp-header">
          <div>
            <span class="comp-league">{{ bestSofaComp.league }}</span>
            <span class="comp-season">{{ bestSofaComp.season }}</span>
            <span class="source-badge source-sofa">SofaScore</span>
          </div>
          <div class="comp-rating" v-if="bestSofaComp.sofascore_rating">
            <span class="rating-badge">{{ bestSofaComp.sofascore_rating }}</span>
          </div>
        </div>

        <div class="presence-row">
          <div class="pres-stat"><span>{{ bestSofaComp.appearances ?? '—' }}</span><label>Presenze</label></div>
          <div class="pres-stat"><span>{{ bestSofaComp.matches_started ?? '—' }}</span><label>Titolare</label></div>
          <div class="pres-stat"><span>{{ bestSofaComp.minutes_played != null ? bestSofaComp.minutes_played + "'" : '—' }}</span><label>Minuti</label></div>
          <div class="pres-stat"><span class="goals-val">{{ bestSofaComp.goals ?? '—' }}</span><label>Gol</label></div>
          <div class="pres-stat"><span class="assists-val">{{ bestSofaComp.assists ?? '—' }}</span><label>Assist</label></div>
        </div>

        <div class="stat-sections">
          <div class="stat-section">
            <div class="stat-section-title">⚽ Tiro</div>
            <div class="stat-row" v-if="bestSofaComp.shots_total != null"><span class="stat-lbl">Tiri totali</span><span class="stat-val">{{ bestSofaComp.shots_total }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.shots_on_target != null"><span class="stat-lbl">In porta</span><span class="stat-val">{{ bestSofaComp.shots_on_target }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.shots_off_target != null"><span class="stat-lbl">Fuori</span><span class="stat-val">{{ bestSofaComp.shots_off_target }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.big_chances_created != null"><span class="stat-lbl">Big chances create</span><span class="stat-val">{{ bestSofaComp.big_chances_created }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.big_chances_missed != null"><span class="stat-lbl">Big chances mancate</span><span class="stat-val">{{ bestSofaComp.big_chances_missed }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.xg != null"><span class="stat-lbl">xG</span><span class="stat-val">{{ bestSofaComp.xg }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.xg_per90 != null"><span class="stat-lbl">xG/90</span><span class="stat-val">{{ bestSofaComp.xg_per90 }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.goal_conversion_pct != null"><span class="stat-lbl">Conversione</span><span class="stat-val">{{ bestSofaComp.goal_conversion_pct }}%</span></div>
            <div class="stat-row" v-if="bestSofaComp.headed_goals != null"><span class="stat-lbl">Gol di testa</span><span class="stat-val">{{ bestSofaComp.headed_goals }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.penalty_goals != null"><span class="stat-lbl">Gol su rigore</span><span class="stat-val">{{ bestSofaComp.penalty_goals }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.hit_woodwork != null"><span class="stat-lbl">Pali/traverse</span><span class="stat-val">{{ bestSofaComp.hit_woodwork }}</span></div>
          </div>

          <div class="stat-section">
            <div class="stat-section-title">🎯 Passaggi</div>
            <div class="stat-row" v-if="bestSofaComp.accurate_passes != null"><span class="stat-lbl">Acc./Tot.</span><span class="stat-val">{{ bestSofaComp.accurate_passes }}/{{ bestSofaComp.total_passes }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.pass_accuracy_pct != null"><span class="stat-lbl">Precisione</span><span class="stat-val">{{ bestSofaComp.pass_accuracy_pct }}%</span></div>
            <div class="stat-row" v-if="bestSofaComp.key_passes != null"><span class="stat-lbl">Passaggi chiave</span><span class="stat-val">{{ bestSofaComp.key_passes }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.xa != null"><span class="stat-lbl">xA</span><span class="stat-val">{{ bestSofaComp.xa }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.xa_per90 != null"><span class="stat-lbl">xA/90</span><span class="stat-val">{{ bestSofaComp.xa_per90 }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.accurate_crosses != null"><span class="stat-lbl">Traversoni acc.</span><span class="stat-val">{{ bestSofaComp.accurate_crosses }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.cross_accuracy_pct != null"><span class="stat-lbl">% Traversoni</span><span class="stat-val">{{ bestSofaComp.cross_accuracy_pct }}%</span></div>
            <div class="stat-row" v-if="bestSofaComp.accurate_long_balls != null"><span class="stat-lbl">Lanci lunghi acc.</span><span class="stat-val">{{ bestSofaComp.accurate_long_balls }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.long_ball_accuracy_pct != null"><span class="stat-lbl">% Lanci lunghi</span><span class="stat-val">{{ bestSofaComp.long_ball_accuracy_pct }}%</span></div>
            <div class="stat-row" v-if="bestSofaComp.accurate_final_third_passes != null"><span class="stat-lbl">Pass. terzo finale</span><span class="stat-val">{{ bestSofaComp.accurate_final_third_passes }}</span></div>
          </div>

          <div class="stat-section">
            <div class="stat-section-title">💪 Duelli</div>
            <div class="stat-row" v-if="bestSofaComp.total_duels_won_pct != null"><span class="stat-lbl">Duelli vinti %</span><span class="stat-val">{{ bestSofaComp.total_duels_won_pct }}%</span></div>
            <div class="stat-row" v-if="bestSofaComp.total_duels_won != null"><span class="stat-lbl">Duelli vinti</span><span class="stat-val">{{ bestSofaComp.total_duels_won }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.ground_duels_won_pct != null"><span class="stat-lbl">Duelli a terra %</span><span class="stat-val">{{ bestSofaComp.ground_duels_won_pct }}%</span></div>
            <div class="stat-row" v-if="bestSofaComp.aerial_duels_won != null"><span class="stat-lbl">Aerei vinti</span><span class="stat-val">{{ bestSofaComp.aerial_duels_won }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.aerial_duels_won_pct != null"><span class="stat-lbl">% Aerei</span><span class="stat-val">{{ bestSofaComp.aerial_duels_won_pct }}%</span></div>
            <div class="stat-row" v-if="bestSofaComp.successful_dribbles != null"><span class="stat-lbl">Dribbling riusciti</span><span class="stat-val">{{ bestSofaComp.successful_dribbles }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.dribble_success_pct != null"><span class="stat-lbl">% Dribbling</span><span class="stat-val">{{ bestSofaComp.dribble_success_pct }}%</span></div>
            <div class="stat-row" v-if="bestSofaComp.dribbled_past != null"><span class="stat-lbl">Saltato</span><span class="stat-val">{{ bestSofaComp.dribbled_past }}</span></div>
          </div>

          <div class="stat-section" v-if="bestSofaComp.tackles != null || bestSofaComp.interceptions != null">
            <div class="stat-section-title">🛡 Difesa</div>
            <div class="stat-row" v-if="bestSofaComp.tackles != null"><span class="stat-lbl">Tackle</span><span class="stat-val">{{ bestSofaComp.tackles }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.tackles_won != null"><span class="stat-lbl">Tackle vinti</span><span class="stat-val">{{ bestSofaComp.tackles_won }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.tackles_won_pct != null"><span class="stat-lbl">% Tackle vinti</span><span class="stat-val">{{ bestSofaComp.tackles_won_pct }}%</span></div>
            <div class="stat-row" v-if="bestSofaComp.interceptions != null"><span class="stat-lbl">Intercetti</span><span class="stat-val">{{ bestSofaComp.interceptions }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.clearances != null"><span class="stat-lbl">Respinte</span><span class="stat-val">{{ bestSofaComp.clearances }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.blocked_shots != null"><span class="stat-lbl">Tiri bloccati</span><span class="stat-val">{{ bestSofaComp.blocked_shots }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.ball_recovery != null"><span class="stat-lbl">Palloni recuperati</span><span class="stat-val">{{ bestSofaComp.ball_recovery }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.possession_won_att_third != null"><span class="stat-lbl">Poss. recuperato 3°</span><span class="stat-val">{{ bestSofaComp.possession_won_att_third }}</span></div>
          </div>

          <div class="stat-section">
            <div class="stat-section-title">🟨 Disciplina</div>
            <div class="stat-row"><span class="stat-lbl">Ammonizioni</span><span class="stat-val">{{ bestSofaComp.yellow_cards ?? 0 }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.yellow_red_cards != null"><span class="stat-lbl">Doppia ammonizione</span><span class="stat-val">{{ bestSofaComp.yellow_red_cards }}</span></div>
            <div class="stat-row"><span class="stat-lbl">Espulsioni</span><span class="stat-val">{{ bestSofaComp.red_cards ?? 0 }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.fouls_committed != null"><span class="stat-lbl">Falli commessi</span><span class="stat-val">{{ bestSofaComp.fouls_committed }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.fouls_won != null"><span class="stat-lbl">Falli subiti</span><span class="stat-val">{{ bestSofaComp.fouls_won }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.offsides != null"><span class="stat-lbl">Fuorigioco</span><span class="stat-val">{{ bestSofaComp.offsides }}</span></div>
          </div>

          <div class="stat-section" v-if="bestSofaComp.saves != null">
            <div class="stat-section-title">🧤 Portiere</div>
            <div class="stat-row"><span class="stat-lbl">Parate</span><span class="stat-val">{{ bestSofaComp.saves }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.goals_conceded != null"><span class="stat-lbl">Gol subiti</span><span class="stat-val">{{ bestSofaComp.goals_conceded }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.clean_sheets != null"><span class="stat-lbl">Clean sheet</span><span class="stat-val">{{ bestSofaComp.clean_sheets }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.penalty_saved != null"><span class="stat-lbl">Rigori parati</span><span class="stat-val">{{ bestSofaComp.penalty_saved }}</span></div>
            <div class="stat-row" v-if="bestSofaComp.high_claims != null"><span class="stat-lbl">Uscite alte</span><span class="stat-val">{{ bestSofaComp.high_claims }}</span></div>
          </div>
        </div>
      </div>
      <div v-if="!bestSofaComp" class="empty-state card">
        <p>Nessun dato SofaScore disponibile per questa competizione.</p>
      </div>

      <!-- FBref per competizione selezionata (tutti i campi da player_fbref_stats) -->
      <div v-if="bestFbrefComp" class="card comp-card">
        <div class="comp-header">
          <div>
            <span class="comp-league">{{ bestFbrefComp.league }}</span>
            <span class="comp-season">{{ bestFbrefComp.season }}</span>
            <span class="source-badge source-fbref">FBref</span>
          </div>
        </div>

        <div class="presence-row">
          <div class="pres-stat"><span>{{ bestFbrefComp.appearances ?? '—' }}</span><label>Presenze</label></div>
          <div class="pres-stat"><span>{{ bestFbrefComp.starts ?? '—' }}</span><label>Titolare</label></div>
          <div class="pres-stat"><span>{{ bestFbrefComp.minutes != null ? bestFbrefComp.minutes + "'" : '—' }}</span><label>Minuti</label></div>
          <div class="pres-stat"><span class="goals-val">{{ bestFbrefComp.goals ?? '—' }}</span><label>Gol</label></div>
          <div class="pres-stat"><span class="assists-val">{{ bestFbrefComp.assists ?? '—' }}</span><label>Assist</label></div>
        </div>

        <div class="stat-sections">
          <!-- Standard / xG -->
          <div class="stat-section">
            <div class="stat-section-title">⚽ Standard</div>
            <div class="stat-row" v-if="bestFbrefComp.xg != null"><span class="stat-lbl">xG</span><span class="stat-val">{{ bestFbrefComp.xg }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.npxg != null"><span class="stat-lbl">npxG</span><span class="stat-val">{{ bestFbrefComp.npxg }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.xa != null"><span class="stat-lbl">xA</span><span class="stat-val">{{ bestFbrefComp.xa }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.xg_per90 != null"><span class="stat-lbl">xG/90</span><span class="stat-val">{{ bestFbrefComp.xg_per90 }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.xa_per90 != null"><span class="stat-lbl">xA/90</span><span class="stat-val">{{ bestFbrefComp.xa_per90 }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.npxg_per90 != null"><span class="stat-lbl">npxG/90</span><span class="stat-val">{{ bestFbrefComp.npxg_per90 }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.goals_per90 != null"><span class="stat-lbl">Gol/90</span><span class="stat-val">{{ bestFbrefComp.goals_per90 }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.assists_per90 != null"><span class="stat-lbl">Assist/90</span><span class="stat-val">{{ bestFbrefComp.assists_per90 }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.yellow_cards != null"><span class="stat-lbl">Ammonizioni</span><span class="stat-val">{{ bestFbrefComp.yellow_cards }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.red_cards != null"><span class="stat-lbl">Espulsioni</span><span class="stat-val">{{ bestFbrefComp.red_cards }}</span></div>
          </div>

          <!-- Tiro -->
          <div class="stat-section">
            <div class="stat-section-title">🎯 Tiro</div>
            <div class="stat-row" v-if="bestFbrefComp.shots != null"><span class="stat-lbl">Tiri totali</span><span class="stat-val">{{ bestFbrefComp.shots }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.shots_on_target != null"><span class="stat-lbl">In porta</span><span class="stat-val">{{ bestFbrefComp.shots_on_target }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.shots_on_target_pct != null"><span class="stat-lbl">% In porta</span><span class="stat-val">{{ bestFbrefComp.shots_on_target_pct }}%</span></div>
            <div class="stat-row" v-if="bestFbrefComp.goals_per_shot != null"><span class="stat-lbl">Gol/Tiro</span><span class="stat-val">{{ bestFbrefComp.goals_per_shot }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.goals_per_sot != null"><span class="stat-lbl">Gol/Tiro in porta</span><span class="stat-val">{{ bestFbrefComp.goals_per_sot }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.avg_shot_distance != null"><span class="stat-lbl">Dist. media tiro</span><span class="stat-val">{{ bestFbrefComp.avg_shot_distance }} yd</span></div>
            <div class="stat-row" v-if="bestFbrefComp.xg_net != null">
              <span class="stat-lbl">xG Net</span>
              <span class="stat-val" :style="{ color: (bestFbrefComp.xg_net ?? 0) >= 0 ? '#22c55e' : '#ef4444' }">
                {{ (bestFbrefComp.xg_net ?? 0) >= 0 ? '+' : '' }}{{ bestFbrefComp.xg_net }}
              </span>
            </div>
          </div>

          <!-- GCA -->
          <div class="stat-section" v-if="bestFbrefComp.sca != null || bestFbrefComp.gca != null">
            <div class="stat-section-title">⚡ GCA / SCA</div>
            <div class="stat-row" v-if="bestFbrefComp.sca != null"><span class="stat-lbl">SCA</span><span class="stat-val">{{ bestFbrefComp.sca }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.sca_per90 != null"><span class="stat-lbl">SCA/90</span><span class="stat-val">{{ bestFbrefComp.sca_per90 }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.sca_pass_live != null"><span class="stat-lbl">SCA pass. live</span><span class="stat-val">{{ bestFbrefComp.sca_pass_live }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.sca_pass_dead != null"><span class="stat-lbl">SCA calcio piazz.</span><span class="stat-val">{{ bestFbrefComp.sca_pass_dead }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.sca_take_on != null"><span class="stat-lbl">SCA dribbling</span><span class="stat-val">{{ bestFbrefComp.sca_take_on }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.sca_shot != null"><span class="stat-lbl">SCA tiro</span><span class="stat-val">{{ bestFbrefComp.sca_shot }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.gca != null"><span class="stat-lbl">GCA</span><span class="stat-val">{{ bestFbrefComp.gca }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.gca_per90 != null"><span class="stat-lbl">GCA/90</span><span class="stat-val">{{ bestFbrefComp.gca_per90 }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.gca_pass_live != null"><span class="stat-lbl">GCA pass. live</span><span class="stat-val">{{ bestFbrefComp.gca_pass_live }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.gca_take_on != null"><span class="stat-lbl">GCA dribbling</span><span class="stat-val">{{ bestFbrefComp.gca_take_on }}</span></div>
          </div>

          <!-- Passaggi -->
          <div class="stat-section" v-if="bestFbrefComp.passes_completed != null || bestFbrefComp.key_passes != null">
            <div class="stat-section-title">🎯 Passaggi</div>
            <div class="stat-row" v-if="bestFbrefComp.passes_completed != null"><span class="stat-lbl">Completati/Tentati</span><span class="stat-val">{{ bestFbrefComp.passes_completed }}/{{ bestFbrefComp.passes_attempted ?? '—' }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.pass_completion_pct != null"><span class="stat-lbl">% Precisione</span><span class="stat-val">{{ bestFbrefComp.pass_completion_pct }}%</span></div>
            <div class="stat-row" v-if="bestFbrefComp.passes_long_completed != null"><span class="stat-lbl">Lanci lunghi acc.</span><span class="stat-val">{{ bestFbrefComp.passes_long_completed }}/{{ bestFbrefComp.passes_long_attempted ?? '—' }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.passes_long_pct != null"><span class="stat-lbl">% Lanci lunghi</span><span class="stat-val">{{ bestFbrefComp.passes_long_pct }}%</span></div>
            <div class="stat-row" v-if="bestFbrefComp.key_passes != null"><span class="stat-lbl">Passaggi chiave</span><span class="stat-val">{{ bestFbrefComp.key_passes }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.xa_pass != null"><span class="stat-lbl">xA (passaggi)</span><span class="stat-val">{{ bestFbrefComp.xa_pass }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.passes_final_third != null"><span class="stat-lbl">Pass. terzo finale</span><span class="stat-val">{{ bestFbrefComp.passes_final_third }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.passes_penalty_area != null"><span class="stat-lbl">Pass. in area</span><span class="stat-val">{{ bestFbrefComp.passes_penalty_area }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.crosses_penalty_area != null"><span class="stat-lbl">Cross in area</span><span class="stat-val">{{ bestFbrefComp.crosses_penalty_area }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.progressive_passes != null"><span class="stat-lbl">Pass. progressivi</span><span class="stat-val">{{ bestFbrefComp.progressive_passes }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.progressive_passes_received != null"><span class="stat-lbl">Ric. progressivi</span><span class="stat-val">{{ bestFbrefComp.progressive_passes_received }}</span></div>
          </div>

          <!-- Conduzione / Possesso -->
          <div class="stat-section" v-if="bestFbrefComp.touches != null || bestFbrefComp.progressive_carries != null">
            <div class="stat-section-title">🏃 Conduzione</div>
            <div class="stat-row" v-if="bestFbrefComp.touches != null"><span class="stat-lbl">Tocchi totali</span><span class="stat-val">{{ bestFbrefComp.touches }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.touches_def_3rd != null"><span class="stat-lbl">Tocchi 3° difens.</span><span class="stat-val">{{ bestFbrefComp.touches_def_3rd }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.touches_mid_3rd != null"><span class="stat-lbl">Tocchi 3° medio</span><span class="stat-val">{{ bestFbrefComp.touches_mid_3rd }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.touches_att_3rd != null"><span class="stat-lbl">Tocchi 3° offens.</span><span class="stat-val">{{ bestFbrefComp.touches_att_3rd }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.touches_att_pen != null"><span class="stat-lbl">Tocchi area avv.</span><span class="stat-val">{{ bestFbrefComp.touches_att_pen }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.progressive_carries != null"><span class="stat-lbl">Conduzioni progr.</span><span class="stat-val">{{ bestFbrefComp.progressive_carries }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.carries_prog_dist != null"><span class="stat-lbl">Distanza progr. (yd)</span><span class="stat-val">{{ bestFbrefComp.carries_prog_dist }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.carries_final_third != null"><span class="stat-lbl">Cond. 3° finale</span><span class="stat-val">{{ bestFbrefComp.carries_final_third }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.carries_penalty_area != null"><span class="stat-lbl">Cond. in area</span><span class="stat-val">{{ bestFbrefComp.carries_penalty_area }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.take_ons_att != null"><span class="stat-lbl">Dribbling tentati</span><span class="stat-val">{{ bestFbrefComp.take_ons_att }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.take_ons_succ != null"><span class="stat-lbl">Dribbling riusciti</span><span class="stat-val">{{ bestFbrefComp.take_ons_succ }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.take_ons_succ_pct != null"><span class="stat-lbl">% Dribbling</span><span class="stat-val">{{ bestFbrefComp.take_ons_succ_pct }}%</span></div>
            <div class="stat-row" v-if="bestFbrefComp.take_ons_tackled != null"><span class="stat-lbl">Dribbling subiti</span><span class="stat-val">{{ bestFbrefComp.take_ons_tackled }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.miscontrols != null"><span class="stat-lbl">Perse (errore)</span><span class="stat-val">{{ bestFbrefComp.miscontrols }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.dispossessed != null"><span class="stat-lbl">Palla persa (press.)</span><span class="stat-val">{{ bestFbrefComp.dispossessed }}</span></div>
          </div>

          <!-- Difesa -->
          <div class="stat-section" v-if="bestFbrefComp.tackles != null || bestFbrefComp.interceptions != null">
            <div class="stat-section-title">🛡 Difesa</div>
            <div class="stat-row" v-if="bestFbrefComp.tackles != null"><span class="stat-lbl">Tackle tentati</span><span class="stat-val">{{ bestFbrefComp.tackles }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.tackles_won != null"><span class="stat-lbl">Tackle vinti</span><span class="stat-val">{{ bestFbrefComp.tackles_won }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.tackles_def_3rd != null"><span class="stat-lbl">Tackle 3° difens.</span><span class="stat-val">{{ bestFbrefComp.tackles_def_3rd }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.tackles_mid_3rd != null"><span class="stat-lbl">Tackle 3° medio</span><span class="stat-val">{{ bestFbrefComp.tackles_mid_3rd }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.tackles_att_3rd != null"><span class="stat-lbl">Tackle 3° offens.</span><span class="stat-val">{{ bestFbrefComp.tackles_att_3rd }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.challenge_tackles != null"><span class="stat-lbl">Contrasti vinti</span><span class="stat-val">{{ bestFbrefComp.challenge_tackles }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.challenge_tackles_pct != null"><span class="stat-lbl">% Contrasti</span><span class="stat-val">{{ bestFbrefComp.challenge_tackles_pct }}%</span></div>
            <div class="stat-row" v-if="bestFbrefComp.interceptions != null"><span class="stat-lbl">Intercetti</span><span class="stat-val">{{ bestFbrefComp.interceptions }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.tkl_int != null"><span class="stat-lbl">Tackle + Intercetti</span><span class="stat-val">{{ bestFbrefComp.tkl_int }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.blocks != null"><span class="stat-lbl">Block</span><span class="stat-val">{{ bestFbrefComp.blocks }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.blocked_shots != null"><span class="stat-lbl">Tiri bloccati</span><span class="stat-val">{{ bestFbrefComp.blocked_shots }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.blocked_passes != null"><span class="stat-lbl">Passaggi bloccati</span><span class="stat-val">{{ bestFbrefComp.blocked_passes }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.clearances != null"><span class="stat-lbl">Respinte</span><span class="stat-val">{{ bestFbrefComp.clearances }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.errors != null"><span class="stat-lbl">Errori → tiro</span><span class="stat-val">{{ bestFbrefComp.errors }}</span></div>
          </div>

          <!-- Misc -->
          <div class="stat-section">
            <div class="stat-section-title">📋 Misc</div>
            <div class="stat-row" v-if="bestFbrefComp.fouls_committed != null"><span class="stat-lbl">Falli commessi</span><span class="stat-val">{{ bestFbrefComp.fouls_committed }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.fouls_drawn != null"><span class="stat-lbl">Falli subiti</span><span class="stat-val">{{ bestFbrefComp.fouls_drawn }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.offsides != null"><span class="stat-lbl">Fuorigioco</span><span class="stat-val">{{ bestFbrefComp.offsides }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.crosses != null"><span class="stat-lbl">Cross</span><span class="stat-val">{{ bestFbrefComp.crosses }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.aerials_won != null"><span class="stat-lbl">Aerei vinti</span><span class="stat-val">{{ bestFbrefComp.aerials_won }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.aerials_lost != null"><span class="stat-lbl">Aerei persi</span><span class="stat-val">{{ bestFbrefComp.aerials_lost }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.aerials_won_pct != null"><span class="stat-lbl">% Aerei</span><span class="stat-val">{{ bestFbrefComp.aerials_won_pct }}%</span></div>
            <div class="stat-row" v-if="bestFbrefComp.ball_recoveries != null"><span class="stat-lbl">Palloni recuperati</span><span class="stat-val">{{ bestFbrefComp.ball_recoveries }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.pens_won != null"><span class="stat-lbl">Rigori conquistati</span><span class="stat-val">{{ bestFbrefComp.pens_won }}</span></div>
            <div class="stat-row" v-if="bestFbrefComp.own_goals != null"><span class="stat-lbl">Autogol</span><span class="stat-val">{{ bestFbrefComp.own_goals }}</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════════ TAB BAR ══════════════ -->
    <!-- PUNTO 6: Competizione allo stesso livello dei pulsanti -->
    <div class="tabs-and-filters" v-if="player && !loading">
      <div class="tabs">
        <button class="tab-btn" :class="{ active: activeTab === 'scheda' }" @click="activeTab = 'scheda'">
          👤 Scheda
        </button>
        <button class="tab-btn" :class="{ active: activeTab === 'algoritmo' }" @click="activeTab = 'algoritmo'">
          🧠 Algoritmo
        </button>
        <!-- PUNTO 4: Heatmap con indicazione fonte SofaScore -->
        <button class="tab-btn" :class="{ active: activeTab === 'heatmap' }" @click="activeTab = 'heatmap'">
          🗺 Heatmap <span class="tab-source-hint">(SofaScore)</span>
        </button>
        <!-- PUNTO 3: Partite con scelta fonte -->
        <button class="tab-btn" :class="{ active: activeTab === 'matches' }" @click="activeTab = 'matches'; loadMatches()">
          🗓 Partite
        </button>
        <button class="tab-btn" :class="{ active: activeTab === 'career' }" @click="activeTab = 'career'">
          🔄 Carriera
        </button>
        <!-- PUNTO 5: Pulsante Fonti RIMOSSO -->
      </div>

      <!-- PUNTO 6: Filtro competizione sempre visibile inline con i tab -->
      <div class="competition-filter">
        <label>🏆 Competizione:</label>
        <select v-model="selectedCompetition" @change="onCompetitionChange">
          <option v-for="comp in availableCompetitions" :key="comp" :value="comp">{{ comp }}</option>
        </select>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════
         TAB — SCHEDA (Punto 2: Algoritmo + Fonti in sequenza)
    ══════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'scheda' && player && !loading">

      <!-- 2a) Dati Algoritmo -->
      <div class="section-divider">🧠 Dati Algoritmo</div>
      <div v-if="!scouting" class="card empty-state" style="margin-top:1rem">
        <p>⚙️ Indici non ancora calcolati. Importa i dati FBref e/o SofaScore, poi lancia il ricalcolo.</p>
      </div>
      <div v-else>
        <div class="card algo-header-card" style="margin-top:1rem">
          <div class="algo-meta-row">
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Stagione</span>
              <span class="algo-meta-val">{{ scouting.season }}</span>
            </div>
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Ruolo</span>
              <span class="algo-meta-val">{{ scouting.position_group ?? '—' }}</span>
            </div>
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Minuti</span>
              <span class="algo-meta-val">{{ scouting.minutes_sample ?? '—' }}'</span>
            </div>
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Confidenza</span>
              <span class="algo-meta-val" :style="{ color: confidenceColor(scouting.data_confidence) }">
                {{ scouting.data_confidence != null ? (scouting.data_confidence * 100).toFixed(0) + '%' : '—' }}
              </span>
            </div>
            <div class="algo-meta-item" v-if="scouting.sources_used?.length">
              <span class="algo-meta-lbl">Fonti</span>
              <span class="algo-meta-val sources-list">
                <span v-for="s in scouting.sources_used" :key="s"
                  class="source-badge" :class="'source-' + s">{{ s }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="card overall-card" style="margin-top:1rem" v-if="scouting.overall_index != null">
          <div class="overall-label">Indice Complessivo</div>
          <div class="overall-value" :style="{ color: scoreColor(scouting.overall_index) }">
            {{ scouting.overall_index.toFixed(1) }}
          </div>
          <div class="overall-bar-track">
            <div class="overall-bar-fill"
              :style="{ width: scouting.overall_index + '%', background: scoreColor(scouting.overall_index) }">
            </div>
          </div>
          <div class="overall-sublabel">Percentile nel gruppo ruolo</div>
        </div>

        <div class="card" style="margin-top:1rem">
          <h3 class="section-title">🧠 Parametri Intelligenti</h3>
          <div class="score-grid">
            <div v-for="item in algoItems" :key="item.key" class="score-item">
              <div class="score-bar-wrap">
                <div class="score-bar-fill"
                  :style="{ width: (scouting[item.key] || 0) + '%', background: scoreColor(scouting[item.key]) }">
                </div>
              </div>
              <div class="score-labels">
                <span class="score-lbl">
                  {{ item.label }}
                  <span class="tooltip-wrap">
                    <span class="tooltip-icon">ℹ</span>
                    <span class="tooltip-box">
                      <strong>{{ item.label }}</strong>
                      {{ item.tooltip }}<br>
                      <span class="tooltip-sources">Fonti: {{ item.sources }}</span>
                    </span>
                  </span>
                </span>
                <span class="score-val" :style="{ color: scoreColor(scouting[item.key]) }">
                  {{ scouting[item.key] != null ? scouting[item.key].toFixed(1) : '—' }}
                </span>
              </div>
              <div class="raw-metrics" v-if="scouting.raw">
                <template v-for="mk in item.raw_keys" :key="mk.k">
                  <span v-if="scouting.raw[mk.k] != null" class="raw-metric">
                    {{ mk.label }}: <strong>{{ typeof scouting.raw[mk.k] === 'number' ? scouting.raw[mk.k].toFixed(2) : scouting.raw[mk.k] }}</strong>
                  </span>
                </template>
              </div>
            </div>
          </div>
          <!-- Legenda fonti -->
          <div class="algo-legend">
            <span class="legend-dot fbref"></span> FBref (metriche avanzate)
            <span class="legend-dot sofa" style="margin-left:1rem"></span> SofaScore (pressing, duelli, dribbling)
            <span class="legend-note">Percentile nel gruppo-ruolo (0 = ultimo, 100 = migliore)</span>
          </div>
        </div>

        <div class="card algo-note-card" style="margin-top:1rem">
          <p>
            ℹ️ Gli indici sono <strong>percentili nel gruppo-ruolo</strong> (0 = ultimo, 100 = migliore).
            Calcolati fondendo <strong>FBref</strong> (npxG, SCA, GCA, portate progressive, passaggi progressivi)
            e <strong>SofaScore</strong> (tackle, intercetti, recuperi, dribbling, duelli aerei).
            La confidenza dipende da quante fonti e quanti minuti sono disponibili.
            Ricalcola con <code>POST /scoring/run</code> dopo ogni nuovo import.
          </p>
        </div>
      </div>

      <!-- 2b) Dati Fonti — stessa struttura completa della home -->
      <div class="section-divider">📂 Dati Fonti — SofaScore</div>

      <!-- SofaScore — tutti i dati completi dalla nuova tabella -->
      <div class="card fonte-card" style="margin-top:1rem">
        <div class="fonte-header">
          <h3 class="section-title">⚡ SofaScore — Statistiche per Competizione</h3>
          <span class="source-badge source-sofa">sofascore</span>
        </div>
        <div v-if="sofascoreStatsByComp.length">
          <div v-for="row in sofascoreStatsByComp" :key="row.season + row.league" class="fonte-season-block">
            <div class="fonte-season-title">
              {{ row.season }} · {{ row.league }}
              <span v-if="row.sofascore_rating" class="rating-badge small">{{ row.sofascore_rating }}</span>
            </div>
            <div class="stat-sections">
              <div class="stat-section">
                <div class="stat-section-title">📋 Riepilogo</div>
                <div class="stat-row"><span class="stat-lbl">Presenze</span><span class="stat-val">{{ row.appearances ?? '—' }}</span></div>
                <div class="stat-row"><span class="stat-lbl">Titolare</span><span class="stat-val">{{ row.matches_started ?? '—' }}</span></div>
                <div class="stat-row"><span class="stat-lbl">Minuti</span><span class="stat-val">{{ row.minutes_played != null ? row.minutes_played + "'" : '—' }}</span></div>
                <div class="stat-row"><span class="stat-lbl">Gol</span><span class="stat-val">{{ row.goals ?? '—' }}</span></div>
                <div class="stat-row"><span class="stat-lbl">Assist</span><span class="stat-val">{{ row.assists ?? '—' }}</span></div>
                <div class="stat-row" v-if="row.goals_assists_sum != null"><span class="stat-lbl">G+A</span><span class="stat-val">{{ row.goals_assists_sum }}</span></div>
                <div class="stat-row" v-if="row.xg != null"><span class="stat-lbl">xG</span><span class="stat-val">{{ row.xg }}</span></div>
                <div class="stat-row" v-if="row.xa != null"><span class="stat-lbl">xA</span><span class="stat-val">{{ row.xa }}</span></div>
                <div class="stat-row" v-if="row.xg_per90 != null"><span class="stat-lbl">xG/90</span><span class="stat-val">{{ row.xg_per90 }}</span></div>
                <div class="stat-row" v-if="row.xa_per90 != null"><span class="stat-lbl">xA/90</span><span class="stat-val">{{ row.xa_per90 }}</span></div>
              </div>
              <div class="stat-section">
                <div class="stat-section-title">⚽ Tiro</div>
                <div class="stat-row" v-if="row.shots_total != null"><span class="stat-lbl">Tiri totali</span><span class="stat-val">{{ row.shots_total }}</span></div>
                <div class="stat-row" v-if="row.shots_on_target != null"><span class="stat-lbl">In porta</span><span class="stat-val">{{ row.shots_on_target }}</span></div>
                <div class="stat-row" v-if="row.shots_off_target != null"><span class="stat-lbl">Fuori</span><span class="stat-val">{{ row.shots_off_target }}</span></div>
                <div class="stat-row" v-if="row.big_chances_created != null"><span class="stat-lbl">Big chances create</span><span class="stat-val">{{ row.big_chances_created }}</span></div>
                <div class="stat-row" v-if="row.big_chances_missed != null"><span class="stat-lbl">Big chances mancate</span><span class="stat-val">{{ row.big_chances_missed }}</span></div>
                <div class="stat-row" v-if="row.goal_conversion_pct != null"><span class="stat-lbl">Conversione gol</span><span class="stat-val">{{ row.goal_conversion_pct }}%</span></div>
                <div class="stat-row" v-if="row.headed_goals != null"><span class="stat-lbl">Gol di testa</span><span class="stat-val">{{ row.headed_goals }}</span></div>
                <div class="stat-row" v-if="row.penalty_goals != null"><span class="stat-lbl">Gol su rigore</span><span class="stat-val">{{ row.penalty_goals }}</span></div>
                <div class="stat-row" v-if="row.penalty_won != null"><span class="stat-lbl">Rigori conquistati</span><span class="stat-val">{{ row.penalty_won }}</span></div>
                <div class="stat-row" v-if="row.hit_woodwork != null"><span class="stat-lbl">Pali/traverse</span><span class="stat-val">{{ row.hit_woodwork }}</span></div>
              </div>
              <div class="stat-section">
                <div class="stat-section-title">🎯 Passaggi</div>
                <div class="stat-row" v-if="row.accurate_passes != null"><span class="stat-lbl">Acc./Tot.</span><span class="stat-val">{{ row.accurate_passes }}/{{ row.total_passes ?? '—' }}</span></div>
                <div class="stat-row" v-if="row.pass_accuracy_pct != null"><span class="stat-lbl">% precisione</span><span class="stat-val">{{ row.pass_accuracy_pct }}%</span></div>
                <div class="stat-row" v-if="row.key_passes != null"><span class="stat-lbl">Passaggi chiave</span><span class="stat-val">{{ row.key_passes }}</span></div>
                <div class="stat-row" v-if="row.accurate_crosses != null"><span class="stat-lbl">Traversoni acc.</span><span class="stat-val">{{ row.accurate_crosses }}</span></div>
                <div class="stat-row" v-if="row.cross_accuracy_pct != null"><span class="stat-lbl">% Traversoni</span><span class="stat-val">{{ row.cross_accuracy_pct }}%</span></div>
                <div class="stat-row" v-if="row.accurate_long_balls != null"><span class="stat-lbl">Lanci lunghi acc.</span><span class="stat-val">{{ row.accurate_long_balls }}</span></div>
                <div class="stat-row" v-if="row.long_ball_accuracy_pct != null"><span class="stat-lbl">% Lanci lunghi</span><span class="stat-val">{{ row.long_ball_accuracy_pct }}%</span></div>
                <div class="stat-row" v-if="row.accurate_final_third_passes != null"><span class="stat-lbl">Pass. terzo finale</span><span class="stat-val">{{ row.accurate_final_third_passes }}</span></div>
                <div class="stat-row" v-if="row.accurate_own_half_passes != null"><span class="stat-lbl">Pass. propria metà</span><span class="stat-val">{{ row.accurate_own_half_passes }}</span></div>
                <div class="stat-row" v-if="row.accurate_opp_half_passes != null"><span class="stat-lbl">Pass. metà avv.</span><span class="stat-val">{{ row.accurate_opp_half_passes }}</span></div>
              </div>
              <div class="stat-section">
                <div class="stat-section-title">💪 Duelli & Dribbling</div>
                <div class="stat-row" v-if="row.total_duels_won_pct != null"><span class="stat-lbl">Duelli vinti %</span><span class="stat-val">{{ row.total_duels_won_pct }}%</span></div>
                <div class="stat-row" v-if="row.total_duels_won != null"><span class="stat-lbl">Duelli vinti</span><span class="stat-val">{{ row.total_duels_won }}</span></div>
                <div class="stat-row" v-if="row.ground_duels_won_pct != null"><span class="stat-lbl">Duelli a terra %</span><span class="stat-val">{{ row.ground_duels_won_pct }}%</span></div>
                <div class="stat-row" v-if="row.aerial_duels_won != null"><span class="stat-lbl">Aerei vinti</span><span class="stat-val">{{ row.aerial_duels_won }}</span></div>
                <div class="stat-row" v-if="row.aerial_duels_won_pct != null"><span class="stat-lbl">% Aerei</span><span class="stat-val">{{ row.aerial_duels_won_pct }}%</span></div>
                <div class="stat-row" v-if="row.successful_dribbles != null"><span class="stat-lbl">Dribbling riusciti</span><span class="stat-val">{{ row.successful_dribbles }}</span></div>
                <div class="stat-row" v-if="row.dribble_success_pct != null"><span class="stat-lbl">% Dribbling</span><span class="stat-val">{{ row.dribble_success_pct }}%</span></div>
                <div class="stat-row" v-if="row.dribbled_past != null"><span class="stat-lbl">Saltato</span><span class="stat-val">{{ row.dribbled_past }}</span></div>
                <div class="stat-row" v-if="row.dispossessed != null"><span class="stat-lbl">Palla persa</span><span class="stat-val">{{ row.dispossessed }}</span></div>
              </div>
              <div class="stat-section">
                <div class="stat-section-title">🛡 Difesa</div>
                <div class="stat-row" v-if="row.tackles != null"><span class="stat-lbl">Tackle</span><span class="stat-val">{{ row.tackles }}</span></div>
                <div class="stat-row" v-if="row.tackles_won != null"><span class="stat-lbl">Tackle vinti</span><span class="stat-val">{{ row.tackles_won }}</span></div>
                <div class="stat-row" v-if="row.tackles_won_pct != null"><span class="stat-lbl">% Tackle</span><span class="stat-val">{{ row.tackles_won_pct }}%</span></div>
                <div class="stat-row" v-if="row.interceptions != null"><span class="stat-lbl">Intercetti</span><span class="stat-val">{{ row.interceptions }}</span></div>
                <div class="stat-row" v-if="row.clearances != null"><span class="stat-lbl">Respinte</span><span class="stat-val">{{ row.clearances }}</span></div>
                <div class="stat-row" v-if="row.blocked_shots != null"><span class="stat-lbl">Tiri bloccati</span><span class="stat-val">{{ row.blocked_shots }}</span></div>
                <div class="stat-row" v-if="row.ball_recovery != null"><span class="stat-lbl">Palloni recuperati</span><span class="stat-val">{{ row.ball_recovery }}</span></div>
                <div class="stat-row" v-if="row.errors_led_to_goal != null"><span class="stat-lbl">Errori → gol</span><span class="stat-val">{{ row.errors_led_to_goal }}</span></div>
                <div class="stat-row" v-if="row.possession_won_att_third != null"><span class="stat-lbl">Poss. rec. 3° off.</span><span class="stat-val">{{ row.possession_won_att_third }}</span></div>
              </div>
              <div class="stat-section">
                <div class="stat-section-title">🟨 Disciplina</div>
                <div class="stat-row"><span class="stat-lbl">Ammonizioni</span><span class="stat-val">{{ row.yellow_cards ?? 0 }}</span></div>
                <div class="stat-row" v-if="row.yellow_red_cards != null"><span class="stat-lbl">Doppia amm.</span><span class="stat-val">{{ row.yellow_red_cards }}</span></div>
                <div class="stat-row"><span class="stat-lbl">Espulsioni</span><span class="stat-val">{{ row.red_cards ?? 0 }}</span></div>
                <div class="stat-row" v-if="row.fouls_committed != null"><span class="stat-lbl">Falli commessi</span><span class="stat-val">{{ row.fouls_committed }}</span></div>
                <div class="stat-row" v-if="row.fouls_won != null"><span class="stat-lbl">Falli subiti</span><span class="stat-val">{{ row.fouls_won }}</span></div>
                <div class="stat-row" v-if="row.offsides != null"><span class="stat-lbl">Fuorigioco</span><span class="stat-val">{{ row.offsides }}</span></div>
              </div>
              <div class="stat-section" v-if="row.saves != null">
                <div class="stat-section-title">🧤 Portiere</div>
                <div class="stat-row"><span class="stat-lbl">Parate</span><span class="stat-val">{{ row.saves }}</span></div>
                <div class="stat-row" v-if="row.goals_conceded != null"><span class="stat-lbl">Gol subiti</span><span class="stat-val">{{ row.goals_conceded }}</span></div>
                <div class="stat-row" v-if="row.clean_sheets != null"><span class="stat-lbl">Clean sheet</span><span class="stat-val">{{ row.clean_sheets }}</span></div>
                <div class="stat-row" v-if="row.penalty_saved != null"><span class="stat-lbl">Rigori parati</span><span class="stat-val">{{ row.penalty_saved }}</span></div>
                <div class="stat-row" v-if="row.high_claims != null"><span class="stat-lbl">Uscite alte</span><span class="stat-val">{{ row.high_claims }}</span></div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <p>Nessun dato SofaScore nella tabella dedicata. Riesegui l'import SofaScore.</p>
        </div>
      </div>

      <div class="section-divider">📂 Dati Fonti — FBref</div>

      <!-- FBref — Statistiche Avanzate (da player_fbref_stats, filtrate per competizione) -->
      <div class="card fonte-card" style="margin-top:1rem">
        <div class="fonte-header">
          <h3 class="section-title">📊 FBref — Statistiche Avanzate</h3>
          <span class="source-badge source-fbref">fbref</span>
        </div>

        <div v-if="fbrefStatsByComp.length">
          <div v-for="row in fbrefStatsByComp" :key="row.season + row.league" class="fonte-season-block">
            <div class="fonte-season-title">{{ row.season }} · {{ row.league }}</div>

            <div class="presence-row">
              <div class="pres-stat"><span>{{ row.appearances ?? '—' }}</span><label>Presenze</label></div>
              <div class="pres-stat"><span>{{ row.starts ?? '—' }}</span><label>Titolare</label></div>
              <div class="pres-stat"><span>{{ row.minutes != null ? row.minutes + "'" : '—' }}</span><label>Minuti</label></div>
              <div class="pres-stat"><span class="goals-val">{{ row.goals ?? '—' }}</span><label>Gol</label></div>
              <div class="pres-stat"><span class="assists-val">{{ row.assists ?? '—' }}</span><label>Assist</label></div>
            </div>

            <div class="stat-sections">

              <!-- Standard / xG -->
              <div class="stat-section">
                <div class="stat-section-title">⚽ Standard</div>
                <div class="stat-row" v-if="row.xg != null"><span class="stat-lbl">xG</span><span class="stat-val">{{ row.xg }}</span></div>
                <div class="stat-row" v-if="row.npxg != null"><span class="stat-lbl">npxG</span><span class="stat-val">{{ row.npxg }}</span></div>
                <div class="stat-row" v-if="row.xa != null"><span class="stat-lbl">xA</span><span class="stat-val">{{ row.xa }}</span></div>
                <div class="stat-row" v-if="row.xg_per90 != null"><span class="stat-lbl">xG/90</span><span class="stat-val">{{ row.xg_per90 }}</span></div>
                <div class="stat-row" v-if="row.xa_per90 != null"><span class="stat-lbl">xA/90</span><span class="stat-val">{{ row.xa_per90 }}</span></div>
                <div class="stat-row" v-if="row.npxg_per90 != null"><span class="stat-lbl">npxG/90</span><span class="stat-val">{{ row.npxg_per90 }}</span></div>
                <div class="stat-row" v-if="row.goals_per90 != null"><span class="stat-lbl">Gol/90</span><span class="stat-val">{{ row.goals_per90 }}</span></div>
                <div class="stat-row" v-if="row.assists_per90 != null"><span class="stat-lbl">Assist/90</span><span class="stat-val">{{ row.assists_per90 }}</span></div>
                <div class="stat-row" v-if="row.yellow_cards != null"><span class="stat-lbl">Ammonizioni</span><span class="stat-val">{{ row.yellow_cards }}</span></div>
                <div class="stat-row" v-if="row.red_cards != null"><span class="stat-lbl">Espulsioni</span><span class="stat-val">{{ row.red_cards }}</span></div>
              </div>

              <!-- Tiro -->
              <div class="stat-section">
                <div class="stat-section-title">🎯 Tiro</div>
                <div class="stat-row" v-if="row.shots != null"><span class="stat-lbl">Tiri totali</span><span class="stat-val">{{ row.shots }}</span></div>
                <div class="stat-row" v-if="row.shots_on_target != null"><span class="stat-lbl">In porta</span><span class="stat-val">{{ row.shots_on_target }}</span></div>
                <div class="stat-row" v-if="row.shots_on_target_pct != null"><span class="stat-lbl">% In porta</span><span class="stat-val">{{ row.shots_on_target_pct }}%</span></div>
                <div class="stat-row" v-if="row.shots_per90 != null"><span class="stat-lbl">Tiri/90</span><span class="stat-val">{{ row.shots_per90 }}</span></div>
                <div class="stat-row" v-if="row.goals_per_shot != null"><span class="stat-lbl">Gol/Tiro</span><span class="stat-val">{{ row.goals_per_shot }}</span></div>
                <div class="stat-row" v-if="row.goals_per_sot != null"><span class="stat-lbl">Gol/Tiro in porta</span><span class="stat-val">{{ row.goals_per_sot }}</span></div>
                <div class="stat-row" v-if="row.avg_shot_distance != null"><span class="stat-lbl">Dist. media tiro</span><span class="stat-val">{{ row.avg_shot_distance }} yd</span></div>
                <div class="stat-row" v-if="row.xg_net != null">
                  <span class="stat-lbl">xG Net (over/under)</span>
                  <span class="stat-val" :style="{ color: (row.xg_net ?? 0) >= 0 ? '#22c55e' : '#ef4444' }">
                    {{ (row.xg_net ?? 0) >= 0 ? '+' : '' }}{{ row.xg_net }}
                  </span>
                </div>
                <div class="stat-row" v-if="row.npxg_net != null">
                  <span class="stat-lbl">npxG Net</span>
                  <span class="stat-val" :style="{ color: (row.npxg_net ?? 0) >= 0 ? '#22c55e' : '#ef4444' }">
                    {{ (row.npxg_net ?? 0) >= 0 ? '+' : '' }}{{ row.npxg_net }}
                  </span>
                </div>
              </div>

              <!-- GCA (Goal/Shot Creating Actions) -->
              <div class="stat-section" v-if="row.sca != null || row.gca != null">
                <div class="stat-section-title">⚡ Creazione (GCA/SCA)</div>
                <div class="stat-row" v-if="row.sca != null"><span class="stat-lbl">SCA</span><span class="stat-val">{{ row.sca }}</span></div>
                <div class="stat-row" v-if="row.sca_per90 != null"><span class="stat-lbl">SCA/90</span><span class="stat-val">{{ row.sca_per90 }}</span></div>
                <div class="stat-row" v-if="row.sca_pass_live != null"><span class="stat-lbl">SCA pass. live</span><span class="stat-val">{{ row.sca_pass_live }}</span></div>
                <div class="stat-row" v-if="row.sca_pass_dead != null"><span class="stat-lbl">SCA calco piazz.</span><span class="stat-val">{{ row.sca_pass_dead }}</span></div>
                <div class="stat-row" v-if="row.sca_take_on != null"><span class="stat-lbl">SCA dribbling</span><span class="stat-val">{{ row.sca_take_on }}</span></div>
                <div class="stat-row" v-if="row.sca_shot != null"><span class="stat-lbl">SCA tiro</span><span class="stat-val">{{ row.sca_shot }}</span></div>
                <div class="stat-row" v-if="row.gca != null"><span class="stat-lbl">GCA</span><span class="stat-val">{{ row.gca }}</span></div>
                <div class="stat-row" v-if="row.gca_per90 != null"><span class="stat-lbl">GCA/90</span><span class="stat-val">{{ row.gca_per90 }}</span></div>
                <div class="stat-row" v-if="row.gca_pass_live != null"><span class="stat-lbl">GCA pass. live</span><span class="stat-val">{{ row.gca_pass_live }}</span></div>
                <div class="stat-row" v-if="row.gca_take_on != null"><span class="stat-lbl">GCA dribbling</span><span class="stat-val">{{ row.gca_take_on }}</span></div>
              </div>

              <!-- Passaggi -->
              <div class="stat-section" v-if="row.passes_completed != null || row.key_passes != null">
                <div class="stat-section-title">🎯 Passaggi</div>
                <div class="stat-row" v-if="row.passes_completed != null"><span class="stat-lbl">Completati/Tentati</span><span class="stat-val">{{ row.passes_completed }}/{{ row.passes_attempted ?? '—' }}</span></div>
                <div class="stat-row" v-if="row.pass_completion_pct != null"><span class="stat-lbl">% Precisione</span><span class="stat-val">{{ row.pass_completion_pct }}%</span></div>
                <div class="stat-row" v-if="row.passes_long_completed != null"><span class="stat-lbl">Lanci lunghi acc.</span><span class="stat-val">{{ row.passes_long_completed }}/{{ row.passes_long_attempted ?? '—' }}</span></div>
                <div class="stat-row" v-if="row.passes_long_pct != null"><span class="stat-lbl">% Lanci lunghi</span><span class="stat-val">{{ row.passes_long_pct }}%</span></div>
                <div class="stat-row" v-if="row.key_passes != null"><span class="stat-lbl">Passaggi chiave</span><span class="stat-val">{{ row.key_passes }}</span></div>
                <div class="stat-row" v-if="row.xa_pass != null"><span class="stat-lbl">xA (passaggi)</span><span class="stat-val">{{ row.xa_pass }}</span></div>
                <div class="stat-row" v-if="row.passes_final_third != null"><span class="stat-lbl">Pass. terzo finale</span><span class="stat-val">{{ row.passes_final_third }}</span></div>
                <div class="stat-row" v-if="row.passes_penalty_area != null"><span class="stat-lbl">Pass. in area</span><span class="stat-val">{{ row.passes_penalty_area }}</span></div>
                <div class="stat-row" v-if="row.crosses_penalty_area != null"><span class="stat-lbl">Cross in area</span><span class="stat-val">{{ row.crosses_penalty_area }}</span></div>
                <div class="stat-row" v-if="row.progressive_passes != null"><span class="stat-lbl">Pass. progressivi</span><span class="stat-val">{{ row.progressive_passes }}</span></div>
                <div class="stat-row" v-if="row.progressive_passes_received != null"><span class="stat-lbl">Ric. progressivi</span><span class="stat-val">{{ row.progressive_passes_received }}</span></div>
              </div>

              <!-- Conduzione / Possesso -->
              <div class="stat-section" v-if="row.touches != null || row.progressive_carries != null">
                <div class="stat-section-title">🏃 Conduzione & Possesso</div>
                <div class="stat-row" v-if="row.touches != null"><span class="stat-lbl">Tocchi totali</span><span class="stat-val">{{ row.touches }}</span></div>
                <div class="stat-row" v-if="row.touches_def_3rd != null"><span class="stat-lbl">Tocchi 3° difens.</span><span class="stat-val">{{ row.touches_def_3rd }}</span></div>
                <div class="stat-row" v-if="row.touches_mid_3rd != null"><span class="stat-lbl">Tocchi 3° medio</span><span class="stat-val">{{ row.touches_mid_3rd }}</span></div>
                <div class="stat-row" v-if="row.touches_att_3rd != null"><span class="stat-lbl">Tocchi 3° offens.</span><span class="stat-val">{{ row.touches_att_3rd }}</span></div>
                <div class="stat-row" v-if="row.touches_att_pen != null"><span class="stat-lbl">Tocchi area avv.</span><span class="stat-val">{{ row.touches_att_pen }}</span></div>
                <div class="stat-row" v-if="row.progressive_carries != null"><span class="stat-lbl">Conduzioni progr.</span><span class="stat-val">{{ row.progressive_carries }}</span></div>
                <div class="stat-row" v-if="row.carries_prog_dist != null"><span class="stat-lbl">Distanza progr. (yd)</span><span class="stat-val">{{ row.carries_prog_dist }}</span></div>
                <div class="stat-row" v-if="row.carries_final_third != null"><span class="stat-lbl">Cond. 3° finale</span><span class="stat-val">{{ row.carries_final_third }}</span></div>
                <div class="stat-row" v-if="row.carries_penalty_area != null"><span class="stat-lbl">Cond. in area</span><span class="stat-val">{{ row.carries_penalty_area }}</span></div>
                <div class="stat-row" v-if="row.take_ons_att != null"><span class="stat-lbl">Dribbling tentati</span><span class="stat-val">{{ row.take_ons_att }}</span></div>
                <div class="stat-row" v-if="row.take_ons_succ != null"><span class="stat-lbl">Dribbling riusciti</span><span class="stat-val">{{ row.take_ons_succ }}</span></div>
                <div class="stat-row" v-if="row.take_ons_succ_pct != null"><span class="stat-lbl">% Dribbling</span><span class="stat-val">{{ row.take_ons_succ_pct }}%</span></div>
                <div class="stat-row" v-if="row.take_ons_tackled != null"><span class="stat-lbl">Dribbling subiti</span><span class="stat-val">{{ row.take_ons_tackled }}</span></div>
                <div class="stat-row" v-if="row.miscontrols != null"><span class="stat-lbl">Perse (errore)</span><span class="stat-val">{{ row.miscontrols }}</span></div>
                <div class="stat-row" v-if="row.dispossessed != null"><span class="stat-lbl">Palla persa (press.)</span><span class="stat-val">{{ row.dispossessed }}</span></div>
              </div>

              <!-- Difesa -->
              <div class="stat-section" v-if="row.tackles != null || row.interceptions != null">
                <div class="stat-section-title">🛡 Difesa</div>
                <div class="stat-row" v-if="row.tackles != null"><span class="stat-lbl">Tackle tentati</span><span class="stat-val">{{ row.tackles }}</span></div>
                <div class="stat-row" v-if="row.tackles_won != null"><span class="stat-lbl">Tackle vinti</span><span class="stat-val">{{ row.tackles_won }}</span></div>
                <div class="stat-row" v-if="row.tackles_def_3rd != null"><span class="stat-lbl">Tackle 3° difens.</span><span class="stat-val">{{ row.tackles_def_3rd }}</span></div>
                <div class="stat-row" v-if="row.tackles_mid_3rd != null"><span class="stat-lbl">Tackle 3° medio</span><span class="stat-val">{{ row.tackles_mid_3rd }}</span></div>
                <div class="stat-row" v-if="row.tackles_att_3rd != null"><span class="stat-lbl">Tackle 3° offens.</span><span class="stat-val">{{ row.tackles_att_3rd }}</span></div>
                <div class="stat-row" v-if="row.challenge_tackles != null"><span class="stat-lbl">Contrasti vinti</span><span class="stat-val">{{ row.challenge_tackles }}</span></div>
                <div class="stat-row" v-if="row.challenge_tackles_pct != null"><span class="stat-lbl">% Contrasti</span><span class="stat-val">{{ row.challenge_tackles_pct }}%</span></div>
                <div class="stat-row" v-if="row.interceptions != null"><span class="stat-lbl">Intercetti</span><span class="stat-val">{{ row.interceptions }}</span></div>
                <div class="stat-row" v-if="row.tkl_int != null"><span class="stat-lbl">Tackle + Intercetti</span><span class="stat-val">{{ row.tkl_int }}</span></div>
                <div class="stat-row" v-if="row.blocks != null"><span class="stat-lbl">Block</span><span class="stat-val">{{ row.blocks }}</span></div>
                <div class="stat-row" v-if="row.blocked_shots != null"><span class="stat-lbl">Tiri bloccati</span><span class="stat-val">{{ row.blocked_shots }}</span></div>
                <div class="stat-row" v-if="row.blocked_passes != null"><span class="stat-lbl">Passaggi bloccati</span><span class="stat-val">{{ row.blocked_passes }}</span></div>
                <div class="stat-row" v-if="row.clearances != null"><span class="stat-lbl">Respinte</span><span class="stat-val">{{ row.clearances }}</span></div>
                <div class="stat-row" v-if="row.errors != null"><span class="stat-lbl">Errori → tiro</span><span class="stat-val">{{ row.errors }}</span></div>
              </div>

              <!-- Misc -->
              <div class="stat-section">
                <div class="stat-section-title">📋 Misc / Discipline</div>
                <div class="stat-row" v-if="row.fouls_committed != null"><span class="stat-lbl">Falli commessi</span><span class="stat-val">{{ row.fouls_committed }}</span></div>
                <div class="stat-row" v-if="row.fouls_drawn != null"><span class="stat-lbl">Falli subiti</span><span class="stat-val">{{ row.fouls_drawn }}</span></div>
                <div class="stat-row" v-if="row.offsides != null"><span class="stat-lbl">Fuorigioco</span><span class="stat-val">{{ row.offsides }}</span></div>
                <div class="stat-row" v-if="row.crosses != null"><span class="stat-lbl">Cross</span><span class="stat-val">{{ row.crosses }}</span></div>
                <div class="stat-row" v-if="row.aerials_won != null"><span class="stat-lbl">Duelli aerei vinti</span><span class="stat-val">{{ row.aerials_won }}</span></div>
                <div class="stat-row" v-if="row.aerials_lost != null"><span class="stat-lbl">Duelli aerei persi</span><span class="stat-val">{{ row.aerials_lost }}</span></div>
                <div class="stat-row" v-if="row.aerials_won_pct != null"><span class="stat-lbl">% Aerei</span><span class="stat-val">{{ row.aerials_won_pct }}%</span></div>
                <div class="stat-row" v-if="row.ball_recoveries != null"><span class="stat-lbl">Palloni recuperati</span><span class="stat-val">{{ row.ball_recoveries }}</span></div>
                <div class="stat-row" v-if="row.pens_won != null"><span class="stat-lbl">Rigori conquistati</span><span class="stat-val">{{ row.pens_won }}</span></div>
                <div class="stat-row" v-if="row.pens_conceded != null"><span class="stat-lbl">Rigori concessi</span><span class="stat-val">{{ row.pens_conceded }}</span></div>
                <div class="stat-row" v-if="row.own_goals != null"><span class="stat-lbl">Autogol</span><span class="stat-val">{{ row.own_goals }}</span></div>
              </div>

            </div><!-- /stat-sections -->
          </div><!-- /fonte-season-block -->
        </div>

        <div v-else class="empty-state">
          <p>Nessun dato FBref per la competizione selezionata. Importa con <code>python -m app.ingest.fbref.import_json</code>.</p>
        </div>
      </div>

      <!-- Match logs FBref: visibili nel tab Partite (selezionare "FBref" nel toggle fonte) -->
    </div>

    <!-- ══════════════════════════════════════════════════════════════
         TAB — ALGORITMO (solo indici, bug fix m.k corretto)
    ══════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'algoritmo' && player && !loading">

      <div v-if="!scouting" class="card empty-state" style="margin-top:1rem">
        <p>⚙️ Indici non ancora calcolati. Importa i dati FBref e/o SofaScore, poi lancia il ricalcolo.</p>
      </div>

      <div v-else>
        <div class="card algo-header-card" style="margin-top:1rem">
          <div class="algo-meta-row">
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Stagione</span>
              <span class="algo-meta-val">{{ scouting.season }}</span>
            </div>
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Ruolo</span>
              <span class="algo-meta-val">{{ scouting.position_group ?? '—' }}</span>
            </div>
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Minuti</span>
              <span class="algo-meta-val">{{ scouting.minutes_sample ?? '—' }}'</span>
            </div>
            <div class="algo-meta-item">
              <span class="algo-meta-lbl">Confidenza</span>
              <span class="algo-meta-val" :style="{ color: confidenceColor(scouting.data_confidence) }">
                {{ scouting.data_confidence != null ? (scouting.data_confidence * 100).toFixed(0) + '%' : '—' }}
              </span>
            </div>
            <div class="algo-meta-item" v-if="scouting.sources_used?.length">
              <span class="algo-meta-lbl">Fonti</span>
              <span class="algo-meta-val sources-list">
                <span v-for="s in scouting.sources_used" :key="s"
                  class="source-badge" :class="'source-' + s">{{ s }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="card overall-card" style="margin-top:1rem" v-if="scouting.overall_index != null">
          <div class="overall-label">Indice Complessivo</div>
          <div class="overall-value" :style="{ color: scoreColor(scouting.overall_index) }">
            {{ scouting.overall_index.toFixed(1) }}
          </div>
          <div class="overall-bar-track">
            <div class="overall-bar-fill"
              :style="{ width: scouting.overall_index + '%', background: scoreColor(scouting.overall_index) }">
            </div>
          </div>
          <div class="overall-sublabel">Percentile nel gruppo ruolo</div>
        </div>

        <div class="card" style="margin-top:1rem">
          <h3 class="section-title">🧠 Parametri Intelligenti</h3>
          <div class="score-grid">
            <!-- BUGFIX: uso template v-for per raw_keys invece di v-if su span con alias -->
            <div v-for="item in algoItems" :key="item.key" class="score-item">
              <div class="score-bar-wrap">
                <div class="score-bar-fill"
                  :style="{ width: (scouting[item.key] || 0) + '%', background: scoreColor(scouting[item.key]) }">
                </div>
              </div>
              <div class="score-labels">
                <span class="score-lbl">{{ item.label }}</span>
                <span class="score-val" :style="{ color: scoreColor(scouting[item.key]) }">
                  {{ scouting[item.key] != null ? scouting[item.key].toFixed(1) : '—' }}
                </span>
              </div>
              <div class="raw-metrics" v-if="scouting.raw">
                <template v-for="mk in item.raw_keys" :key="mk.k">
                  <span v-if="scouting.raw[mk.k] != null" class="raw-metric">
                    {{ mk.label }}: <strong>{{ scouting.raw[mk.k] }}</strong>
                  </span>
                </template>
              </div>
            </div>
          </div>
        </div>

        <div class="card algo-note-card" style="margin-top:1rem">
          <p>
            ℹ️ Gli indici sono <strong>percentili nel gruppo-ruolo</strong> (0 = ultimo, 100 = migliore).
            Vengono calcolati fondendo i dati <strong>FBref</strong> (metriche avanzate) e
            <strong>SofaScore</strong> (fallback). Ricalcola con <code>POST /scoring/run</code> dopo ogni nuovo import.
          </p>
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════
         TAB — HEATMAP & ATTRIBUTI SofaScore (Punto 4)
    ══════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'heatmap' && player && !loading">

      <!-- Fonte: SofaScore esplicita -->
      <div class="card" style="margin-top:1rem">
        <div class="fonte-header">
          <h3 class="section-title">🎯 Attributi</h3>
          <span class="source-badge source-sofa">SofaScore</span>
        </div>

        <div v-if="playerAttributes" class="attributes-layout">
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
                fill="rgba(255,255,255,0.7)" font-size="10" font-family="monospace">{{ axis.label }}</text>
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
              <span class="attr-avg-val" v-if="averageAttributes">⌀ {{ averageAttributes[axis.key] ?? '—' }}</span>
            </div>
            <p class="attr-note">🟠 Media SofaScore &nbsp;|&nbsp; 🟢 Giocatore</p>
          </div>
        </div>

        <div class="card empty-state" style="margin-top: 1rem;" v-if="!playerAttributes">
          <p>Attributi SofaScore non disponibili per questo giocatore.</p>
        </div>
      </div>

      <!-- Heatmap SofaScore — filtrata per competizione selezionata -->
      <div v-if="selectedHeatmapComp" class="card" style="margin-top: 1rem;">
        <div class="fonte-header">
          <h3 class="section-title">
            🗺 Heatmap
            <span class="heat-meta" v-if="selectedHeatmapComp.league">
              · {{ selectedHeatmapComp.league }}
              <span v-if="selectedHeatmapComp.season"> {{ selectedHeatmapComp.season }}</span>
              · {{ selectedHeatmapComp.heatmap_points?.length ?? 0 }} punti
            </span>
          </h3>
          <span class="source-badge source-sofa">SofaScore</span>
        </div>
        <div class="heatmap-outer">
          <div class="heatmap-pitch-wrap">
            <svg class="pitch-svg" viewBox="0 0 100 65" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="0" y="0" width="100" height="65" fill="#1a4a1a"/>
              <rect x="0" y="0" width="50" height="65" fill="#1e541e"/>
              <rect x="1.5" y="1.5" width="97" height="62" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <line x1="50" y1="1.5" x2="50" y2="63.5" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <circle cx="50" cy="32.5" r="8.5" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <rect x="1.5" y="13.8" width="15.7" height="37.4" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <rect x="82.8" y="13.8" width="15.7" height="37.4" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="0.5"/>
              <rect x="0" y="27.5" width="1.5" height="10.5" fill="none" stroke="rgba(255,255,255,0.65)" stroke-width="0.5"/>
              <rect x="98.5" y="27.5" width="1.5" height="10.5" fill="none" stroke="rgba(255,255,255,0.65)" stroke-width="0.5"/>
            </svg>
            <canvas ref="heatmapCanvas" class="heatmap-canvas" width="700" height="455"></canvas>
          </div>
        </div>
      </div>
      <div v-else class="card empty-state" style="margin-top:1rem">
        <p>Dati heatmap SofaScore non disponibili per questo giocatore.</p>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════
         TAB — PARTITE (Punto 3: scelta fonte SofaScore / FBref)
    ══════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'matches' && player && !loading">
      <div class="card" style="margin-top: 1rem;">
        <div class="matches-header">
          <h3 class="section-title" style="margin-bottom:0">🗓 Partite</h3>
          <!-- Selezione fonte -->
          <div class="matches-source-selector">
            <label>Fonte:</label>
            <div class="source-toggle">
              <button
                class="source-toggle-btn"
                :class="{ active: matchesSource === 'sofascore' }"
                @click="matchesSource = 'sofascore'">
                ⚡ SofaScore
              </button>
              <button
                class="source-toggle-btn"
                :class="{ active: matchesSource === 'fbref' }"
                @click="matchesSource = 'fbref'">
                📊 FBref
              </button>
            </div>
          </div>
        </div>

        <!-- Partite SofaScore -->
        <div v-if="matchesSource === 'sofascore'">
          <div class="source-badge source-sofa" style="margin-bottom:0.8rem;display:inline-block">sofascore</div>
          <div v-if="loadingMatches" class="spinner"></div>
          <div v-else-if="filteredMatches.length">
            <div v-for="m in filteredMatches" :key="m.event_id" class="match-row">
              <div class="match-date">{{ formatDate(m.date) }}</div>
              <div class="match-tournament">{{ m.tournament }}</div>
              <div class="match-teams">
                <span :class="{ bold: isHome(m, player.profile?.club) }">{{ m.home_team }}</span>
                <span class="match-score">{{ m.home_score ?? '?' }} - {{ m.away_score ?? '?' }}</span>
                <span :class="{ bold: !isHome(m, player.profile?.club) }">{{ m.away_team }}</span>
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
          <div v-else class="empty-state">Nessuna partita SofaScore disponibile per la competizione selezionata.</div>
        </div>

        <!-- Partite FBref (match log) -->
        <div v-if="matchesSource === 'fbref'">
          <div class="source-badge source-fbref" style="margin-bottom:0.8rem;display:inline-block">fbref</div>
          <div v-if="fbrefMatchLogs.length" class="match-log-table">
            <div class="match-log-header">
              <span>Data</span><span>Comp.</span><span>Avversario</span><span>Ris.</span>
              <span>Min</span><span>G</span><span>A</span><span>Tiri</span><span>Tackle</span>
            </div>
            <div v-for="m in fbrefMatchLogs" :key="m.date + m.comp" class="match-log-row">
              <span>{{ m.date }}</span>
              <span class="muted">{{ m.comp }}</span>
              <span>{{ m.opponent }}</span>
              <span :class="resultClass(m.result)">{{ m.result }}</span>
              <span>{{ m.minutes ?? '—' }}'</span>
              <span class="goals-val">{{ m.goals ?? 0 }}</span>
              <span class="assists-val">{{ m.assists ?? 0 }}</span>
              <span>{{ m.shots ?? '—' }}</span>
              <span>{{ m.tackles_won ?? '—' }}</span>
            </div>
          </div>
          <div v-else class="empty-state">Nessun match log FBref disponibile. Importa con <code>/ingest/fbref</code>.</div>
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════
         TAB — CARRIERA
    ══════════════════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'career' && player && !loading">
      <div class="card" style="margin-top: 1rem;">
        <h3 class="section-title">🔄 Storico trasferimenti</h3>
        <div v-if="player.career?.length" class="career-timeline">
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
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">Nessuna informazione sulla carriera.</div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const route  = useRoute()
const router = useRouter()

const player        = ref(null)
const matches       = ref([])
const loading       = ref(false)
const loadingMatches= ref(false)
const error         = ref(null)
// Tab iniziale: 'scheda' (dopo il caricamento mostra Algoritmo+Fonti)
const activeTab     = ref('scheda')

// Fonte partite: 'sofascore' | 'fbref'
const matchesSource = ref('sofascore')

// ══════════════════════════════════════════════
// DATI ESTRATTI DALLA RISPOSTA STRUTTURATA
// ══════════════════════════════════════════════

const scouting = computed(() => player.value?.scouting ?? null)

// FBref stats (lista stagioni)
const fbrefStats = computed(() => player.value?.sources?.fbref?.stats ?? [])

// FBref match logs
const fbrefMatchLogs = computed(() => player.value?.sources?.fbref?.match_logs ?? [])

// SofaScore stats dalla tabella player_sofascore_stats
const sofascoreStats = computed(() => player.value?.sources?.sofascore?.stats ?? [])

// Partite SofaScore
const sofascoreMatches = computed(() => player.value?.sources?.sofascore?.matches ?? [])

// ══════════════════════════════════════════════
// FILTRO COMPETIZIONE — visibile su tutti i tab
// ══════════════════════════════════════════════

// Array di heatmaps per competizione dalla nuova struttura API:
// sources.sofascore.heatmaps → [{league, season, heatmap_points, point_count}]
const sofascoreHeatmaps = computed(() => player.value?.sources?.sofascore?.heatmaps ?? [])

const selectedCompetition = ref('')

const availableCompetitions = computed(() => {
  const comps = new Set()
  sofascoreStats.value.forEach(s => { if (s.league) comps.add(s.league) })
  fbrefStats.value.forEach(s => { if (s.league) comps.add(s.league) })
  sofascoreMatches.value.forEach(m => { if (m.tournament) comps.add(m.tournament) })
  sofascoreHeatmaps.value.forEach(h => { if (h.league) comps.add(h.league) })
  // Aggiunge le competizioni presenti nei match_logs FBref
  // (Champions Lg, Coppa Italia, ecc. che hanno stats aggregate dal match_log)
  fbrefMatchLogs.value.forEach(m => { if (m.comp && m.comp !== 'Comp') comps.add(m.comp) })
  return Array.from(comps).filter(Boolean)
})

watch(availableCompetitions, (newComps) => {
  if (newComps.length > 0 && !newComps.includes(selectedCompetition.value)) {
    selectedCompetition.value = newComps[0]
  }
}, { immediate: true })

// Normalizza il nome competizione per il matching FBref
// (es. "Champions Lg" dai match_logs → "Champions League" nelle stats aggregate)
function normComp(s) {
  return (s ?? '').toLowerCase()
    .replace(/[_\-\.]/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\blg\b/, 'league')
    .replace(/\bchampions league\b/, 'champions')
    .replace(/\buchampions\b/, 'champions')
    .trim()
}

// Dati FBref filtrati per competizione selezionata
const fbrefStatsByComp = computed(() => {
  if (!fbrefStats.value.length) return []
  if (!selectedCompetition.value) return fbrefStats.value

  // 1. Match esatto
  const exact = fbrefStats.value.filter(s =>
    s.league?.toLowerCase() === selectedCompetition.value.toLowerCase()
  )
  if (exact.length) return exact

  // 2. Match fuzzy normalizzato
  const sel = normComp(selectedCompetition.value)
  const fuzzy = fbrefStats.value.filter(s => {
    const hl = normComp(s.league)
    return hl.includes(sel) || sel.includes(hl) || hl === sel
  })
  return fuzzy
})



// SofaScore stats filtrate per competizione selezionata (usate nel tab Scheda — sezione lista)
const sofascoreStatsByComp = computed(() => {
  if (!sofascoreStats.value.length) return []
  if (!selectedCompetition.value) return sofascoreStats.value
  const exact = sofascoreStats.value.filter(s =>
    s.league?.toLowerCase() === selectedCompetition.value.toLowerCase()
  )
  if (exact.length) return exact
  // Fuzzy match: un nome contiene l'altro
  const sel = selectedCompetition.value.toLowerCase().replace(/[_-]/g, ' ')
  return sofascoreStats.value.filter(s => {
    const hl = (s.league ?? '').toLowerCase().replace(/[_-]/g, ' ')
    return hl.includes(sel) || sel.includes(hl)
  })
})

// Scheda / Home: dati SofaScore per competizione selezionata
const bestSofaComp = computed(() => {
  if (!sofascoreStats.value.length || !selectedCompetition.value) return null
  const matching = sofascoreStats.value.filter(s => s.league === selectedCompetition.value)
  if (!matching.length) return null
  return matching.reduce((best, curr) =>
    (curr.minutes_played ?? 0) > (best.minutes_played ?? 0) ? curr : best
  )
})

// Dati FBref per competizione selezionata.
// I nomi FBref ("Serie A") e SofaScore ("Serie A") di solito coincidono.
// Usiamo un matching case-insensitive + fuzzy per coprire piccole differenze
// (es. "Serie A" vs "serie_a", "Champions League" vs "UEFA Champions League").
const bestFbrefComp = computed(() => {
  if (!fbrefStats.value.length) return null
  if (!selectedCompetition.value) return fbrefStats.value[0] ?? null

  // 1. Match esatto
  const exact = fbrefStats.value.find(s =>
    s.league?.toLowerCase() === selectedCompetition.value.toLowerCase()
  )
  if (exact) return exact

  // 2. Match fuzzy normalizzato
  const sel = normComp(selectedCompetition.value)
  const fuzzy = fbrefStats.value.filter(s => {
    const hl = normComp(s.league)
    return hl.includes(sel) || sel.includes(hl) || hl === sel
  })
  if (fuzzy.length) {
    return fuzzy.reduce((best, curr) =>
      (curr.minutes ?? 0) > (best.minutes ?? 0) ? curr : best
    )
  }
  return null
})

const filteredMatches = computed(() => {
  if (!selectedCompetition.value) return sofascoreMatches.value
  return sofascoreMatches.value.filter(m => m.tournament === selectedCompetition.value)
})

// ══════════════════════════════════════════════
// HEATMAP (fonte: SofaScore)
// ══════════════════════════════════════════════

const heatmapCanvas = ref(null)

// Seleziona la heatmap corrispondente alla competizione scelta nel dropdown.
// Cascata di fallback:
//   1. heatmap con league che corrisponde ESATTAMENTE alla competizione selezionata
//   2. heatmap con league che contiene/è contenuta nella competizione selezionata (fuzzy)
//   3. heatmap con più punti tra tutte le disponibili
const selectedHeatmapComp = computed(() => {
  const heatmaps = sofascoreHeatmaps.value.filter(h => (h.heatmap_points?.length ?? 0) > 0)
  if (!heatmaps.length) return null

  const sel = selectedCompetition.value?.toLowerCase() ?? ''

  if (sel) {
    // 1. Match esatto
    const exact = heatmaps.find(h => h.league?.toLowerCase() === sel)
    if (exact) return exact

    // 2. Match fuzzy (es. "Serie A" vs "serie_a")
    const fuzzy = heatmaps.find(h => {
      const hl = h.league?.toLowerCase() ?? ''
      return hl.includes(sel) || sel.includes(hl)
    })
    if (fuzzy) return fuzzy
  }

  // 3. Fallback: quella con più punti
  return heatmaps.reduce((best, curr) =>
    (curr.heatmap_points?.length ?? 0) > (best.heatmap_points?.length ?? 0) ? curr : best
  )
})

function drawHeatmap() {
  nextTick(() => {
    const canvas = heatmapCanvas.value
    if (!canvas || !selectedHeatmapComp.value) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width, H = canvas.height
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

watch(activeTab, (tab) => {
  if (tab === 'heatmap') drawHeatmap()
  if (tab === 'matches' && !matches.value.length && route.params.id) loadMatches()
})
watch(selectedHeatmapComp, () => {
  if (activeTab.value === 'heatmap') drawHeatmap()
})
// Ridisegna heatmap al cambio competizione (se il tab heatmap è già attivo)
watch(selectedCompetition, () => {
  if (activeTab.value === 'heatmap') drawHeatmap()
})
// Ridisegna heatmap se il tab è già attivo quando i dati arrivano (cambio giocatore)
watch(player, () => {
  if (activeTab.value === 'heatmap') drawHeatmap()
})

// ══════════════════════════════════════════════
// DATI PLAYER
// ══════════════════════════════════════════════

async function loadPlayer() {
  const id = route.params.id
  if (!id) { player.value = null; loading.value = false; return }
  loading.value = true
  error.value   = null
  try {
    const res = await axios.get(`${API}/players/${id}`)
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

watch(() => route.params.id, (newId) => {
  if (newId) {
    loadPlayer()
    if (activeTab.value === 'matches') loadMatches()
  } else {
    player.value = null
    matches.value = []
    activeTab.value = 'scheda'
  }
})

onMounted(() => { loadPlayer() })

// ══════════════════════════════════════════════
// ALGORITMO — items con metriche raw
// BUGFIX: raw_keys è array di oggetti { k, label }
// Il template ora usa <template v-for> + <span v-if> separati
// così Vue non cerca 'm' sull'istanza del componente
// ══════════════════════════════════════════════

const algoItems = [
  {
    key: 'finishing_index',
    label: 'Finalizzazione',
    tooltip: 'Qualità e volume dei tiri. Misura quanto il giocatore crea tiri pericolosi e li concretizza rispetto ai compagni di ruolo.',
    sources: 'FBref (npxG/90, Gol/Tiro) + SofaScore (xG/90, conversione %)',
    raw_keys: [
      { k: 'npxg_per90',     label: 'npxG/90' },
      { k: 'xg_per90',       label: 'xG/90' },
      { k: 'goals_per_shot', label: 'Gol/Tiro' },
    ],
  },
  {
    key: 'creativity_index',
    label: 'Creatività',
    tooltip: 'Capacità di creare occasioni da gol per sé e per i compagni. SCA = azioni che portano a un tiro, GCA = azioni che portano a un gol.',
    sources: 'FBref (SCA/90, GCA/90, xA/90) + SofaScore (xA/90, passaggi chiave/90)',
    raw_keys: [
      { k: 'xa_per90',  label: 'xA/90' },
      { k: 'sca_per90', label: 'SCA/90' },
      { k: 'gca_per90', label: 'GCA/90' },
    ],
  },
  {
    key: 'pressing_index',
    label: 'Pressing',
    tooltip: 'Intensità nel recupero palla. Considera tackle vinti, intercetti, palloni recuperati e possesso recuperato nel terzo offensivo.',
    sources: 'SofaScore (tackle/90, intercetti/90, recuperi/90) + FBref (dove disponibile)',
    raw_keys: [
      { k: 'tackles_won_per90',     label: 'Tackle vinti/90' },
      { k: 'interceptions_per90',   label: 'Intercetti/90' },
      { k: 'ball_recoveries_per90', label: 'Recuperi/90' },
    ],
  },
  {
    key: 'carrying_index',
    label: 'Conduzione',
    tooltip: 'Abilità nel portare palla in avanti. Include portate progressive, dribbling riusciti e penetrazione in area avversaria.',
    sources: 'FBref (portate progressive/90) + SofaScore (% dribbling, dribbling riusciti/90)',
    raw_keys: [
      { k: 'progressive_carries_per90', label: 'Port. prog./90' },
      { k: 'take_ons_succ_pct',         label: '% Dribbling' },
    ],
  },
  {
    key: 'defending_index',
    label: 'Difesa',
    tooltip: 'Solidità difensiva diretta. Misura l\'efficacia nei duelli aerei e a terra, nelle intercettazioni e nelle respinte.',
    sources: 'SofaScore (% aerei, % duelli vinti, respinte/90) + FBref (challenge tackles %)',
    raw_keys: [
      { k: 'aerials_won_pct',     label: '% Aerei vinti' },
      { k: 'interceptions_per90', label: 'Intercetti/90' },
    ],
  },
  {
    key: 'buildup_index',
    label: 'Costruzione',
    tooltip: 'Qualità nella distribuzione del gioco. Misura la precisione dei passaggi, la progressione e la capacità di coinvolgere i compagni in posizioni avanzate.',
    sources: 'FBref (% passaggi, pass. progressivi/90) + SofaScore (% precisione passaggi)',
    raw_keys: [
      { k: 'pass_completion_pct',      label: '% Passaggi' },
      { k: 'progressive_passes_per90', label: 'Pass. prog./90' },
    ],
  },
]

function scoreColor(val) {
  if (val == null) return '#666'
  if (val >= 75) return '#22c55e'
  if (val >= 50) return '#f59e0b'
  return '#ef4444'
}

function confidenceColor(val) {
  if (val == null) return '#666'
  if (val >= 0.9) return '#22c55e'
  if (val >= 0.6) return '#f59e0b'
  return '#ef4444'
}

// ══════════════════════════════════════════════
// ATTRIBUTI SOFASCORE (radar)
// ══════════════════════════════════════════════

const playerAttributes = computed(() => {
  const attrs = player.value?.profile?.sofascore_attributes
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

const averageAttributes = computed(() => {
  const raw = player.value?.profile?.sofascore_attributes_avg
  if (!raw) return null
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const mapped = {}
    for (const [k, v] of Object.entries(raw)) {
      if (k.startsWith('attr_') && !k.startsWith('attr_title_') && !k.startsWith('attr_avg_')) {
        mapped[k.replace('attr_', '')] = v
      }
    }
    return Object.keys(mapped).length ? mapped : null
  }
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
    const val   = (attrs[axis.key] ?? 0) / MAX
    const angle = (i * 2 * Math.PI / n) - Math.PI / 2
    return `${cx + r * val * Math.cos(angle)},${cy + r * val * Math.sin(angle)}`
  }).join(' ')
}
function radarDots(attrs) {
  const cx = 130, cy = 130, r = 110, n = radarAxes.length, MAX = 99
  return radarAxes.map((axis, i) => {
    const val   = (attrs[axis.key] ?? 0) / MAX
    const angle = (i * 2 * Math.PI / n) - Math.PI / 2
    return { x: cx + r * val * Math.cos(angle), y: cy + r * val * Math.sin(angle) }
  })
}
function radarLabelPos(i) {
  const cx = 130, cy = 130, r = 128, n = radarAxes.length
  const angle = (i * 2 * Math.PI / n) - Math.PI / 2
  return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) }
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
function resultClass(r) {
  if (!r) return ''
  if (r.startsWith('W')) return 'result-win'
  if (r.startsWith('L')) return 'result-loss'
  return 'result-draw'
}

// ── Cambio competizione ──────────────────────────────────────────
// Chiamata dal @change della select nella tab bar.
// Ridisegna la heatmap se il tab è già attivo.
function onCompetitionChange() {
  if (activeTab.value === 'heatmap') drawHeatmap()
}

// ── Ricerca ──────────────────────────────────────────────────────
const searchQuery   = ref('')
const searchResults = ref([])
let searchTimeout   = null

const onSearch = () => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(async () => {
    if (searchQuery.value.length < 3) { searchResults.value = []; return }
    try {
      const res = await axios.get(`${API}/scouting/autocomplete?q=${searchQuery.value}`)
      searchResults.value = res.data
    } catch (err) {
      console.error('Errore nella ricerca', err)
    }
  }, 300)
}

const goToPlayer = (id) => {
  searchQuery.value   = ''
  searchResults.value = []
  router.push(`/players/${id}`)
}
</script>

<style scoped>
/* ─── Layout ──────────────────────────────────── */
.player-detail {
  max-width: 1000px;
  margin: 0 auto;
  padding: 1rem;
  font-size: 1.05rem;
}

/* ─── Search ──────────────────────────────────── */
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

/* ─── Section Divider ────────────────────────── */
.section-divider {
  font-size: 0.82rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--color-muted, #888);
  padding: 0.6rem 0 0.3rem;
  margin-top: 1.5rem;
  border-bottom: 1px solid var(--color-border, #2a2a3e);
  margin-bottom: 0.2rem;
}

/* ─── Filtro competizione inline (home) ──────── */
.competition-filter-inline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.95rem;
  color: var(--color-muted, #888);
  margin: 0.6rem 0 0.8rem;
}
.competition-filter-inline select {
  background: var(--color-surface, #1e1e2e);
  border: 1px solid var(--color-border, #444);
  border-radius: 8px;
  padding: 0.35rem 0.7rem;
  color: var(--color-text, #fff);
  font-size: 0.95rem;
  cursor: pointer;
}

/* ─── Tabs & Filters ─────────────────────────── */
/* PUNTO 6: tutto su una riga */
.tabs-and-filters {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  margin: 1.5rem 0 0.5rem;
  flex-wrap: wrap;
  background: var(--color-surface, #1e1e2e);
  border: 1px solid var(--color-border, #333);
  border-radius: 12px;
  padding: 0.6rem 0.8rem;
}
.competition-filter {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: var(--color-muted, #888);
  margin-left: auto;
  white-space: nowrap;
}
.competition-filter select {
  background: var(--color-surface, #1e1e2e);
  border: 1px solid var(--color-border, #444);
  border-radius: 8px;
  padding: 0.35rem 0.7rem;
  color: var(--color-text, #fff);
  font-size: 0.9rem;
  cursor: pointer;
}
.tabs { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.tab-btn {
  background: transparent;
  border: 1px solid var(--color-border, #444);
  border-radius: 8px;
  color: var(--color-muted, #aaa);
  cursor: pointer;
  font-size: 0.88rem;
  padding: 0.35rem 0.8rem;
  transition: all 0.15s;
  white-space: nowrap;
}
.tab-btn.active {
  background: var(--color-accent, #3b82f6);
  border-color: var(--color-accent, #3b82f6);
  color: #fff;
}
.heat-meta {
  font-size: 0.78rem;
  color: var(--color-muted, #888);
  font-weight: 400;
  margin-left: 0.5rem;
}
.tab-source-hint {
  font-size: 0.72rem;
  opacity: 0.7;
  font-weight: 400;
  margin-left: 0.2rem;
}

/* ─── Matches header ─────────────────────────── */
.matches-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.8rem;
  margin-bottom: 1rem;
}
.matches-source-selector {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.9rem;
  color: var(--color-muted, #888);
}
.source-toggle {
  display: flex;
  gap: 0.3rem;
}
.source-toggle-btn {
  background: transparent;
  border: 1px solid var(--color-border, #444);
  border-radius: 8px;
  color: var(--color-muted, #aaa);
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.3rem 0.7rem;
  transition: all 0.15s;
}
.source-toggle-btn.active {
  background: var(--color-accent, #3b82f6);
  border-color: var(--color-accent, #3b82f6);
  color: #fff;
}

/* ─── Hero ───────────────────────────────────── */
.player-hero {
  display: flex;
  align-items: flex-start;
  gap: 1.5rem;
  background: var(--color-surface, #1e1e2e);
  border-radius: 16px;
  padding: 1.5rem;
  margin-bottom: 0.5rem;
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
.player-badge-pos {
  background: var(--color-accent, #3b82f6);
  color: #fff;
  border-radius: 6px;
  padding: 0.15rem 0.5rem;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.hero-name { font-size: 1.8rem; font-weight: 800; color: #fff; margin: 0 0 0.4rem; }
.hero-meta { color: var(--color-muted, #94A3B8); font-size: 0.95rem; display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1rem; }
.meta-sep { opacity: 0.4; }
.hero-stats-row { display: flex; gap: 1.5rem; flex-wrap: wrap; }
.hero-stat { display: flex; flex-direction: column; align-items: center; }
.hero-stat-val { font-size: 1.15rem; font-weight: 700; color: #fff; }
.hero-stat-lbl { font-size: 0.75rem; color: var(--color-muted, #94A3B8); margin-top: 0.15rem; }

/* ─── Card ───────────────────────────────────── */
.card {
  background: var(--color-surface, #1e1e2e);
  border-radius: 12px;
  padding: 1.2rem 1.4rem;
  margin-bottom: 1rem;
  border: 1px solid var(--color-border, #333);
}
.section-title { font-size: 1.05rem; font-weight: 700; color: #fff; margin: 0 0 1rem; }

/* ─── Source badges ──────────────────────────── */
.source-badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-left: 0.5rem;
}
.source-fbref   { background: rgba(99,102,241,0.2); color: #818cf8; border: 1px solid rgba(99,102,241,0.3); }
.source-sofa    { background: rgba(34,197,94,0.15); color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }
.sources-list   { display: inline-flex; gap: 0.3rem; }

/* ─── Competition card ───────────────────────── */
.comp-card { margin-top: 1rem; }
.comp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}
.comp-league { font-weight: 700; color: #fff; font-size: 1.05rem; }
.comp-season { color: var(--color-muted, #888); font-size: 0.9rem; margin-left: 0.5rem; }
.presence-row {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  background: rgba(255,255,255,0.04);
  border-radius: 8px;
  padding: 0.8rem 1rem;
  margin-bottom: 1rem;
}
.pres-stat { display: flex; flex-direction: column; align-items: center; gap: 0.2rem; }
.pres-stat span { font-size: 1.25rem; font-weight: 700; color: #fff; }
.pres-stat label { font-size: 0.72rem; color: var(--color-muted, #888); }
.goals-val   { color: #22c55e !important; }
.assists-val { color: #3b82f6 !important; }
.rating-val  { color: #f59e0b !important; }

/* ─── Stat sections ──────────────────────────── */
.stat-sections { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
.stat-section  { display: flex; flex-direction: column; gap: 0.3rem; }
.stat-section-title { font-size: 0.82rem; font-weight: 700; color: var(--color-muted, #888); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.4rem; }
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.3rem 0;
  border-bottom: 1px solid var(--color-border, #2a2a3e);
  font-size: 0.9rem;
}
.stat-lbl { color: var(--color-muted, #94A3B8); }
.stat-val { color: #fff; font-weight: 600; }

/* ─── Rating badge ───────────────────────────── */
.rating-badge {
  background: #f59e0b;
  color: #000;
  font-weight: 800;
  font-size: 1rem;
  padding: 0.2rem 0.6rem;
  border-radius: 6px;
}
.rating-badge.small { font-size: 0.85rem; padding: 0.1rem 0.5rem; }
.rating-great { background: #22c55e !important; }
.rating-good  { background: #84cc16 !important; }
.rating-ok    { background: #f59e0b !important; }
.rating-bad   { background: #ef4444 !important; }

/* ─── Algoritmo ──────────────────────────────── */
.algo-header-card { }
.algo-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  align-items: center;
}
.algo-meta-item { display: flex; flex-direction: column; gap: 0.2rem; }
.algo-meta-lbl  { font-size: 0.72rem; color: var(--color-muted, #888); text-transform: uppercase; letter-spacing: 0.06em; }
.algo-meta-val  { font-size: 1rem; font-weight: 700; color: #fff; }
.overall-card   { text-align: center; padding: 1.5rem; }
.overall-label  { font-size: 0.85rem; color: var(--color-muted, #888); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.5rem; }
.overall-value  { font-size: 3.5rem; font-weight: 900; line-height: 1; margin-bottom: 0.8rem; }
.overall-bar-track {
  height: 8px;
  background: rgba(255,255,255,0.1);
  border-radius: 4px;
  overflow: hidden;
  margin: 0 auto 0.4rem;
  max-width: 400px;
}
.overall-bar-fill  { height: 100%; border-radius: 4px; transition: width 0.6s ease; }
.overall-sublabel  { font-size: 0.75rem; color: var(--color-muted, #666); }
/* Stile per la riga dell'Indice Complessivo interna */
.overall-inline-row {
  background: rgba(255, 255, 255, 0.03);
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.overall-inline-info {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.5rem;
}

.overall-inline-label {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-muted, #aaa);
}

.overall-inline-value {
  font-size: 1.8rem;
  font-weight: 800;
}

.overall-inline-bar-track {
  height: 10px;
  background: rgba(0,0,0,0.2);
  border-radius: 5px;
  overflow: hidden;
}

.overall-inline-bar-fill {
  height: 100%;
  transition: width 0.6s ease;
}

.overall-inline-sub {
  font-size: 0.75rem;
  color: #666;
  margin-top: 0.4rem;
  text-align: right;
}
.score-grid {
  display: grid;
  /* Crea colonne dinamiche: 2 o 3 a seconda dello spazio */
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1.2rem;
}
.score-item { display: flex; flex-direction: column; }
.score-bar-wrap {
  height: 5px;
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 0.3rem;
}
.score-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
.score-labels { display: flex; justify-content: space-between; font-size: 0.85rem;}
.score-lbl { color: var(--color-muted, #94A3B8); }
.score-val { font-weight: 700; }
.raw-metrics { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.25rem; }
.raw-metric {
  font-size: 0.75rem;
  color: var(--color-muted, #777);
  background: rgba(255,255,255,0.04);
  border-radius: 4px;
  padding: 1px 6px;
}
.algo-note-card p {
  font-size: 0.85rem;
  color: var(--color-muted, #888);
  line-height: 1.6;
  margin: 0;
}

/* ─── Fonti ──────────────────────────────────── */
.fonte-card { }
.fonte-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.fonte-season-block {
  border: 1px solid var(--color-border, #2a2a3e);
  border-radius: 8px;
  padding: 0.8rem 1rem;
  margin-bottom: 0.8rem;
}
.fonte-season-title {
  font-weight: 700;
  color: #fff;
  font-size: 0.95rem;
  margin-bottom: 0.6rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* ─── Match log table ────────────────────────── */
.match-log-table { font-size: 0.82rem; }
.match-log-header, .match-log-row {
  display: grid;
  grid-template-columns: 90px 80px 1fr 50px 50px 30px 30px 50px 50px;
  gap: 0.4rem;
  padding: 0.35rem 0;
  border-bottom: 1px solid var(--color-border, #2a2a3e);
  align-items: center;
}
.match-log-header { color: var(--color-muted, #888); font-weight: 700; text-transform: uppercase; font-size: 0.72rem; }
.muted { color: var(--color-muted, #888); }
.result-win  { color: #22c55e; font-weight: 700; }
.result-loss { color: #ef4444; font-weight: 700; }
.result-draw { color: #f59e0b; font-weight: 700; }

/* ─── Partite ────────────────────────────────── */
.match-row {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--color-border, #f3f0f0);
  flex-wrap: wrap;
  font-size: 0.9rem;
}
.match-date      { color: var(--color-muted, #94A3B8); min-width: 80px; }
.match-tournament{ color: var(--color-muted, #94A3B8); font-size: 0.82rem; min-width: 80px; }
.match-teams     { display: flex; align-items: center; gap: 0.4rem; flex: 1; }
.match-score     { color: #FFFFFF !important; font-weight: 700; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.15); }
.match-perf      { display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }
.match-mins      { color: var(--color-muted, #888); font-size: 0.85rem; }
.match-goal      { color: #22c55e; font-size: 0.85rem; }
.match-assist    { color: #3b82f6; font-size: 0.85rem; }
.bold            { font-weight: 700; }

/* ─── Carriera ───────────────────────────────── */
.career-timeline  { display: flex; flex-direction: column; gap: 0; }
.career-item      { display: flex; gap: 1rem; padding: 0.8rem 0; border-bottom: 1px solid var(--color-border, #333); }
.career-dot       { width: 10px; height: 10px; border-radius: 50%; background: var(--color-accent, #3b82f6); margin-top: 5px; flex-shrink: 0; }
.career-teams     { display: flex; align-items: center; gap: .6rem; font-weight: 600; }
.career-from      { color: var(--color-muted, #94A3B8); }
.career-to        { color: var(--color-text, #fff); font-weight: 700 !important; }
.career-arrow     { color: var(--color-accent, #3b82f6); }
.career-meta      { display: flex; gap: 1rem; font-size: .9rem; color: var(--color-muted, #CBD5E1); margin-top: .2rem; flex-wrap: wrap; }
.career-type      { color: #f59e0b; }
.career-fee       { color: #4ADE80; font-weight: 600; }

/* ─── Heatmap ────────────────────────────────── */
.heatmap-outer { display: flex; justify-content: center; padding: .5rem 0 1rem; }
.heatmap-pitch-wrap {
  position: relative;
  width: 100%;
  max-width: 380px;
  aspect-ratio: 105 / 68;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}
.pitch-svg     { position: absolute; inset: 0; width: 100%; height: 100%; }
.heatmap-canvas{ position: absolute; inset: 0; width: 100%; height: 100%; }

/* ─── Attributi radar ────────────────────────── */
.attributes-layout { display: flex; gap: 2rem; align-items: center; flex-wrap: wrap; padding: .5rem 0; }
.radar-wrap { flex: 0 0 260px; }
.radar-svg  { width: 260px; height: 260px; }
.attr-bars  { flex: 1; min-width: 200px; display: flex; flex-direction: column; gap: .7rem; }
.attr-bar-row { display: flex; align-items: center; gap: .6rem; }
.attr-bar-lbl { width: 36px; font-size: .8rem; font-weight: 700; color: var(--color-muted, #888); text-transform: uppercase; letter-spacing: .05em; flex-shrink: 0; }
.attr-bar-track { flex: 1; height: 8px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden; }
.attr-bar-fill  { height: 100%; border-radius: 4px; transition: width .5s ease; }
.attr-bar-val   { width: 28px; font-size: .9rem; font-weight: 700; text-align: right; flex-shrink: 0; }
.attr-avg-val   { width: 48px; font-size: .78rem; color: #f59e0b; flex-shrink: 0; }
.attr-note      { font-size: .75rem; color: var(--color-muted, #666); margin-top: .4rem; }

/* ─── Empty / Welcome ────────────────────────── */
.empty-state    { text-align: center; color: var(--color-muted, #888); padding: 2rem; font-size: 1rem; }
.welcome-state  { text-align: center; padding: 4rem 2rem; color: var(--color-muted, #888); }
.spinner-wrap   { display: flex; justify-content: center; padding: 3rem; }
.spinner {
  width: 40px; height: 40px;
  border: 3px solid var(--color-border, #333);
  border-top-color: var(--color-accent, #3b82f6);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #ef4444; padding: 1rem; text-align: center; }

/* ─── Autocomplete ───────────────────────────── */
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
.text-muted { color: var(--color-muted, #888); font-size: 0.88rem; }
.algo-layout-grid {
  display: grid;
  grid-template-columns: 1fr 2.5fr; /* L'indice prende meno spazio dei parametri */
  gap: 1.5rem;
  align-items: stretch;
  margin-bottom: 1.5rem;
}

/* Rimuove margini extra dalle card per farle allineare bene nel grid */
.algo-layout-grid .card {
  margin-bottom: 0; 
}
/* Card principale più stretta */
.compact-algo-card {
  max-width: 800px; /* Evita che si allarghi troppo su schermi grandi */
  margin: 0 auto 1.5rem auto; /* La centra e aggiunge spazio sotto */
}
/* Adattamento per dispositivi mobili */
@media (max-width: 768px) {
  .algo-layout-grid {
    grid-template-columns: 1fr;
  }
}

/* ─── Tooltip ────────────────────────────────────────────────── */
.tooltip-wrap {
  position: relative;
  display: inline-block;
  margin-left: 4px;
  vertical-align: middle;
}
.tooltip-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: rgba(255,255,255,0.15);
  color: rgba(255,255,255,0.55);
  font-size: 9px;
  font-style: normal;
  cursor: help;
  line-height: 1;
  font-weight: 700;
  transition: background 0.15s;
}
.tooltip-wrap:hover .tooltip-icon {
  background: rgba(255,255,255,0.28);
  color: #fff;
}
.tooltip-box {
  display: none;
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: #1a1a2e;
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 8px;
  padding: 10px 12px;
  width: 260px;
  font-size: 0.78rem;
  color: #cbd5e1;
  line-height: 1.5;
  z-index: 200;
  pointer-events: none;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  white-space: normal;
  text-align: left;
}
.tooltip-box strong {
  color: #fff;
  display: block;
  margin-bottom: 4px;
  font-size: 0.82rem;
}
.tooltip-sources {
  display: block;
  margin-top: 6px;
  color: rgba(255,255,255,0.4);
  font-size: 0.72rem;
  border-top: 1px solid rgba(255,255,255,0.08);
  padding-top: 5px;
}
.tooltip-box::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: rgba(255,255,255,0.15);
}
.tooltip-wrap:hover .tooltip-box { display: block; }
@media (max-width: 600px) {
  .tooltip-box { left: auto; right: -8px; transform: none; }
  .tooltip-box::after { left: auto; right: 14px; transform: none; }
}

/* ─── Legenda fonti algo ──────────────────────────────────────── */
.algo-legend {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.3rem 0.8rem;
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(255,255,255,0.07);
  font-size: 0.75rem;
  color: rgba(255,255,255,0.4);
}
.legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.legend-dot.fbref { background: #3b82f6; }
.legend-dot.sofa  { background: #f59e0b; }
.legend-note {
  margin-left: auto;
  font-style: italic;
  color: rgba(255,255,255,0.28);
  font-size: 0.72rem;
}
@media (max-width: 600px) {
  .legend-note { margin-left: 0; width: 100%; }
}
</style>