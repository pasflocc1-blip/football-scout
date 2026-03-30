<template>
  <div class="ingest-page">
    <div class="page-header">
      <h1>🔄 Gestione Dati</h1>
      <p class="subtitle">Importa e aggiorna i dati dei calciatori da tutte le sorgenti</p>
    </div>

    <!-- Variabili d'ambiente — collassabile -->
    <div class="card env-panel">
      <div class="env-header" @click="envExpanded = !envExpanded" style="cursor:pointer">
        <div class="env-header-left">
          <span class="env-toggle-icon">{{ envExpanded ? '▼' : '▶' }}</span>
          <div>
            <h2>🔑 Variabili d'ambiente</h2>
            <p class="env-path">
              📁 <code>{{ envFilePath }}</code>
            </p>
          </div>
        </div>
        <div class="env-header-right" @click.stop>
          <!-- Badge riassuntivo quando è chiuso -->
          <div v-if="!envExpanded" class="env-summary-badges">
            <span v-for="ev in ENV_VARS" :key="ev.name">
              <span v-if="envStatus[ev.name] === false" class="env-badge missing">❌ {{ ev.name }}</span>
              <span v-else-if="envStatus[ev.name] === true" class="env-badge set" style="font-size:0.7rem">✅</span>
            </span>
          </div>
          <button class="btn-refresh-env" @click="loadEnvStatus" :disabled="loadingEnv">
            <span :class="{ spin: loadingEnv }">↻</span> Aggiorna
          </button>
        </div>
      </div>

      <div v-if="envExpanded">
        <table class="env-table">
          <thead>
            <tr>
              <th>Nome variabile</th>
              <th>Stato</th>
              <th>Utilizzata da</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ev in ENV_VARS" :key="ev.name">
              <td><code class="env-name">{{ ev.name }}</code></td>
              <td>
                <span v-if="loadingEnv" class="env-badge checking">⏳ …</span>
                <span v-else-if="envStatus[ev.name] === true"  class="env-badge set">✅ Configurata</span>
                <span v-else-if="envStatus[ev.name] === false" class="env-badge missing">❌ Mancante</span>
                <span v-else class="env-badge unknown">— Non verificata</span>
              </td>
              <td class="env-used-by">{{ ev.usedBy }}</td>
              <td class="env-note">{{ ev.note }}</td>
            </tr>
          </tbody>
        </table>

        <p v-if="envError" class="env-error">⚠️ {{ envError }}</p>
        <p class="env-tip">
          💡 Modifica <code>.env</code> e riavvia con
          <code>docker-compose down &amp;&amp; docker-compose up -d</code>
        </p>
      </div>
    </div>

    <!-- Configurazione per sorgente — accordion -->
    <div class="card config-panel">
      <div class="config-panel-header">
        <h2>⚙️ Configurazione sorgenti</h2>
        <div class="config-expand-all">
          <button class="btn-text" @click="expandAllConfig">Espandi tutto</button>
          <span class="sep">·</span>
          <button class="btn-text" @click="collapseAllConfig">Chiudi tutto</button>
        </div>
      </div>

      <!-- ── Kaggle ── -->
      <div class="config-source-block" :class="{ open: configOpen.kaggle }">
        <div class="config-source-header" @click="toggleConfig('kaggle')">
          <span class="config-src-icon">📊</span>
          <span class="config-src-name">Kaggle FIFA</span>
          <span class="config-src-badge badge-free">Gratis</span>
          <span class="config-src-summary">
            {{ config.kaggle_file.split('/').pop() }} · max {{ config.kaggle_limit }}
          </span>
          <span class="config-chevron">{{ configOpen.kaggle ? '▲' : '▼' }}</span>
        </div>
        <div v-if="configOpen.kaggle" class="config-fields">
          <div class="config-group">
            <label>
              CSV Path nel container
              <span class="hint-icon" title="Il container monta ./backend come /app. Quindi: backend/app/data/players_22.csv → /app/app/data/players_22.csv">ℹ️</span>
            </label>
            <input v-model="config.kaggle_file" placeholder="/app/app/data/players_22.csv" />
          </div>
          <div class="config-group">
            <label>Max giocatori</label>
            <input v-model.number="config.kaggle_limit" type="number" placeholder="2000" />
          </div>
        </div>
      </div>

      <!-- ── API-Football ── -->
      <div class="config-source-block" :class="{ open: configOpen.api_football }">
        <div class="config-source-header" @click="toggleConfig('api_football')">
          <span class="config-src-icon">⚽</span>
          <span class="config-src-name">API-Football</span>
          <span class="config-src-badge badge-key">API key</span>
          <span class="config-src-summary">
            {{ leagueName(config.league_id) }} · {{ config.season }}/{{ config.season + 1 }}
          </span>
          <span class="config-chevron">{{ configOpen.api_football ? '▲' : '▼' }}</span>
        </div>
        <div v-if="configOpen.api_football" class="config-fields">
          <div class="config-note-warning">
            ⚠️ Free tier: 100 req/giorno · Max 3 pagine (~60 giocatori) · Stagioni 2022–2024
          </div>
          <div class="config-group">
            <label>Campionato</label>
            <select v-model="config.league_id" @change="config.team_id = null">
              <option :value="135">🇮🇹 Serie A</option>
              <option :value="39">🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League</option>
              <option :value="140">🇪🇸 La Liga</option>
              <option :value="78">🇩🇪 Bundesliga</option>
              <option :value="61">🇫🇷 Ligue 1</option>
            </select>
          </div>
          <div class="config-group">
            <label>Stagione</label>
            <select v-model="config.season">
              <option v-for="y in apifSeasons" :key="y" :value="y">{{ y }}/{{ y + 1 }}</option>
            </select>
            <small style="color:#b45309">Solo 2022–2024 supportate dal free tier</small>
          </div>
          <div class="config-group">
            <label>
              Modalità import
              <span class="hint-icon" title="Singola squadra usa meno richieste API e non ha limite di pagine">ℹ️</span>
            </label>
            <select v-model="config.import_mode">
              <option value="league">🌍 Tutto il campionato (max 3 pag. ≈ 60 giocatori)</option>
              <option value="team">🎯 Singola squadra (nessun limite di pagine)</option>
            </select>
          </div>
          <div v-if="config.import_mode === 'team'" class="config-group">
            <label>Team ID</label>
            <input v-model.number="config.team_id" type="number" placeholder="es. 489 (AC Milan)" />
            <small style="color:var(--text-muted,#6b7280)">
              Trova l'ID su
              <a href="https://dashboard.api-football.com" target="_blank">dashboard.api-football.com</a>
              → Ids → Teams
            </small>
            <div class="team-id-hints">
              <span v-for="t in (APIF_TEAM_HINTS[config.league_id] || [])" :key="t.id"
                class="team-hint-chip" @click="config.team_id = t.id">
                {{ t.name }} ({{ t.id }})
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- ── FBref ── -->
      <div class="config-source-block" :class="{ open: configOpen.fbref }">
        <div class="config-source-header" @click="toggleConfig('fbref')">
          <span class="config-src-icon">🌐</span>
          <span class="config-src-name">FBref</span>
          <span class="config-src-badge badge-free">Scraping</span>
          <span class="config-src-summary">
            {{ config.fbref_league }} · {{ config.fbref_season }}
          </span>
          <span class="config-chevron">{{ configOpen.fbref ? '▲' : '▼' }}</span>
        </div>
        <div v-if="configOpen.fbref" class="config-fields">
          <div class="config-group">
            <label>Campionato</label>
            <select v-model="config.fbref_league">
              <option value="serie_a">🇮🇹 Serie A</option>
              <option value="premier_league">🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League</option>
              <option value="la_liga">🇪🇸 La Liga</option>
              <option value="bundesliga">🇩🇪 Bundesliga</option>
              <option value="ligue_1">🇫🇷 Ligue 1</option>
              <option value="champions_league">🏆 Champions League</option>
              <option value="eredivisie">🇳🇱 Eredivisie</option>
              <option value="primeira_liga">🇵🇹 Primeira Liga</option>
            </select>
          </div>
          <div class="config-group">
            <label>Stagione (formato YYYY-YYYY)</label>
            <input v-model="config.fbref_season" placeholder="es. 2023-2024" />
          </div>
        </div>
      </div>

      <!-- ── StatsBomb ── -->
      <div class="config-source-block" :class="{ open: configOpen.statsbomb }">
        <div class="config-source-header" @click="toggleConfig('statsbomb')">
          <span class="config-src-icon">📈</span>
          <span class="config-src-name">StatsBomb</span>
          <span class="config-src-badge badge-free">Open Data</span>
          <span class="config-src-summary">
            {{ sbCompName(config.statsbomb_comp) }} · {{ sbSeasonName(config.statsbomb_season_id) }} · {{ config.statsbomb_max_matches || 50 }} partite
          </span>
          <span class="config-chevron">{{ configOpen.statsbomb ? '▲' : '▼' }}</span>
        </div>
        <div v-if="configOpen.statsbomb" class="config-fields">
          <div class="config-group">
            <label>
              Competizione
              <span class="hint-icon" title="Dati open data storici. Non include partite in corso.">ℹ️</span>
            </label>
            <select v-model.number="config.statsbomb_comp" @change="onSbCompChange">
              <option v-for="c in SB_QUICK_COMPS" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
            <small>
              <a href="#" @click.prevent="loadStatsBombComps">Vedi tutte le stagioni disponibili →</a>
            </small>
          </div>
          <div class="config-group">
            <label>
              Stagione (Season ID)
              <span class="hint-icon" title="Ogni competizione ha i propri Season ID. Usa 'Vedi tutte' per trovare quello corretto.">ℹ️</span>
            </label>
            <select v-model.number="config.statsbomb_season_id">
              <option v-for="s in activeSbSeasons" :key="s.season_id" :value="s.season_id">
                {{ s.season_name }} (ID: {{ s.season_id }})
              </option>
              <option v-if="!activeSbSeasons.length" :value="config.statsbomb_season_id">
                ID {{ config.statsbomb_season_id }} — clicca "Vedi tutte" per caricare i nomi
              </option>
            </select>
          </div>
          <div class="config-group">
            <label>Max partite</label>
            <input v-model.number="config.statsbomb_max_matches" type="number" min="1" max="380" placeholder="50" />
            <small style="color:var(--text-muted,#6b7280)">Default 50 · Serie A completa = 380</small>
          </div>
        </div>
      </div>

      <!-- ── Understat ── -->
      <div class="config-source-block" :class="{ open: configOpen.understat }">
        <div class="config-source-header" @click="toggleConfig('understat')">
          <span class="config-src-icon">📉</span>
          <span class="config-src-name">Understat</span>
          <span class="config-src-badge badge-free">Gratis</span>
          <span class="config-src-summary">
            {{ config.understat_league }} · {{ config.understat_season }}/{{ config.understat_season + 1 }}
          </span>
          <span class="config-chevron">{{ configOpen.understat ? '▲' : '▼' }}</span>
        </div>
        <div v-if="configOpen.understat" class="config-fields">
          <div class="config-note-info">
            ℹ️ Dati xG/xA stagione corrente. Nessuna API key. Richiede: pip install understat aiohttp
          </div>
          <div class="config-group">
            <label>Campionato</label>
            <select v-model="config.understat_league">
              <option value="serie_a">🇮🇹 Serie A</option>
              <option value="premier_league">🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League</option>
              <option value="la_liga">🇪🇸 La Liga</option>
              <option value="bundesliga">🇩🇪 Bundesliga</option>
              <option value="ligue_1">🇫🇷 Ligue 1</option>
            </select>
          </div>
          <div class="config-group">
            <label>Stagione (anno inizio)</label>
            <select v-model.number="config.understat_season">
              <option v-for="y in Array.from({length:11},(_,i)=>2024-i)" :key="y" :value="y">
                {{ y }}/{{ y + 1 }}
              </option>
            </select>
          </div>
        </div>
      </div>

      <!-- ── Football-Data.org ── -->
      <div class="config-source-block" :class="{ open: configOpen.football_data }">
        <div class="config-source-header" @click="toggleConfig('football_data')">
          <span class="config-src-icon">🏛</span>
          <span class="config-src-name">Football-Data.org</span>
          <span class="config-src-badge badge-key">API key</span>
          <span class="config-src-summary">
            {{ config.fd_comp }} · {{ config.fd_season }}/{{ config.fd_season + 1 }}
          </span>
          <span class="config-chevron">{{ configOpen.football_data ? '▲' : '▼' }}</span>
        </div>
        <div v-if="configOpen.football_data" class="config-fields">
          <div class="config-note-info">
            ℹ️ Free tier: 10 req/min. Aggiorna il campo <em>club</em> nei giocatori importati.
          </div>
          <div class="config-group">
            <label>Competizione</label>
            <select v-model="config.fd_comp">
              <option value="SA">🇮🇹 SA — Serie A</option>
              <option value="PL">🏴󠁧󠁢󠁥󠁮󠁧󠁿 PL — Premier League</option>
              <option value="PD">🇪🇸 PD — La Liga</option>
              <option value="BL1">🇩🇪 BL1 — Bundesliga</option>
              <option value="FL1">🇫🇷 FL1 — Ligue 1</option>
              <option value="CL">🏆 CL — Champions League</option>
              <option value="DED">🇳🇱 DED — Eredivisie</option>
              <option value="PPL">🇵🇹 PPL — Primeira Liga</option>
            </select>
          </div>
          <div class="config-group">
            <label>Stagione</label>
            <select v-model="config.fd_season">
              <option v-for="y in fdSeasons" :key="y" :value="y">{{ y }}/{{ y + 1 }}</option>
            </select>
          </div>
        </div>
      </div>

    </div><!-- /config-panel -->

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
          <span>📁 {{ config.kaggle_file.split('/').pop() }}</span>
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
          Free tier: 100 req/giorno · max 3 pagine.
        </p>
        <div class="source-params">
          <span>🏆 {{ leagueName(config.league_id) }}</span>
          <span>📅 {{ config.season }}/{{ config.season + 1 }}</span>
        </div>
        <div class="source-status" v-if="jobs.api_football">
          <JobStatus :job="jobs.api_football" />
        </div>
        <div v-if="isPageLimited && dialogSource === 'api-football'" class="source-page-limit-badge">
          ⚠️ Fermato a 3 pag. (free tier)
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
          <span>🏆 {{ sbCompName(config.statsbomb_comp) }}</span>
          <span>📅 {{ sbSeasonName(config.statsbomb_season_id) }}</span>
          <span>🎮 {{ config.statsbomb_max_matches || 50 }} partite</span>
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
        <FBrefCsvImport />
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

      <!-- Understat -->
      <div class="source-card card" :class="statusClass('understat')">
        <div class="source-header">
          <div class="source-icon">📉</div>
          <div>
            <h3>Understat</h3>
            <span class="badge badge-free">Gratis</span>
          </div>
        </div>
        <p class="source-desc">
          xG, xA, npxG stagione corrente. Fonte statistica più aggiornata.
          Arricchisce i giocatori già importati. Nessuna API key richiesta.
        </p>
        <div class="source-params">
          <span>🏆 {{ config.understat_league }}</span>
          <span>📅 {{ config.understat_season }}/{{ config.understat_season + 1 }}</span>
        </div>
        <div class="source-status" v-if="jobs.understat">
          <JobStatus :job="jobs.understat" />
        </div>
        <button
          class="btn btn-source"
          :disabled="jobs.understat?.status === 'running'"
          @click="runSource('understat')"
        >
          <span v-if="jobs.understat?.status === 'running'">⏳ In esecuzione…</span>
          <span v-else>▶ Arricchisci xG/xA</span>
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
          <span>📅 {{ config.fd_season }}/{{ config.fd_season + 1 }}</span>
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

    <!-- ── Dialog progresso / riepilogo import ───────────────────── -->
    <div v-if="dialogVisible" class="modal-overlay">
      <div class="modal card progress-dialog">

        <!-- Header -->
        <div class="modal-header">
          <div class="dialog-title">
            <span class="dialog-icon">{{ activeDialogLabel.icon }}</span>
            <div>
              <h3>{{ activeDialogLabel.label }}</h3>
              <span class="dialog-subtitle">
                <span v-if="activeDialogJob?.status === 'running'">Import in corso…</span>
                <span v-else-if="activeDialogJob?.status === 'done'">Import completato</span>
                <span v-else-if="activeDialogJob?.status === 'error'">Import fallito</span>
                <span v-else>In attesa di risposta…</span>
              </span>
            </div>
          </div>
          <!-- Header right: Stop durante esecuzione, X al termine -->
          <div class="dialog-header-actions">
            <button
              v-if="activeDialogJob?.status === 'running'"
              class="btn-stop-import"
              :disabled="stopping"
              @click="stopImport"
            >
              <span v-if="stopping">⏳ Interruzione…</span>
              <span v-else>⏹ Interrompi</span>
            </button>
            <button
              v-if="activeDialogJob?.status !== 'running'"
              class="btn-close"
              @click="dialogVisible = false"
            >✕</button>
          </div>
        </div>

        <!-- Corpo: IN ESECUZIONE -->
        <div v-if="!activeDialogJob || activeDialogJob.status === 'running'" class="dialog-body">
          <div class="progress-pulse">
            <div class="pulse-ring"></div>
            <span class="pulse-icon">{{ activeDialogLabel.icon }}</span>
          </div>
          <p class="dialog-running-text">Elaborazione in corso…</p>
          <p class="dialog-hint">Clicca ⏹ Interrompi per annullare l'operazione.</p>
          <div class="progress-bar-track">
            <div class="progress-bar-indeterminate"></div>
          </div>

          <!-- Live log SEMPRE visibile (con placeholder se ancora vuoto) -->
          <div class="live-log-container" ref="logContainer">
            <div class="live-log-header">📋 Log in tempo reale</div>
            <div class="live-log-body">
              <div v-if="!activeDialogJob?.logs?.length" class="log-line log-debug">
                In attesa dei primi messaggi…
              </div>
              <div
                v-for="(line, i) in (activeDialogJob?.logs || [])"
                :key="i"
                class="log-line"
                :class="logLineClass(line)"
              >{{ line }}</div>
            </div>
          </div>
        </div>

        <!-- Corpo: INTERROTTO -->
        <div v-else-if="activeDialogJob?.status === 'cancelled'" class="dialog-body">
          <div class="dialog-success-icon">⏹</div>
          <p class="dialog-done-text" style="color:#f59e0b">Import interrotto dall'utente</p>
          <div v-if="activeDialogJob.logs?.length" class="live-log-container done-log" style="margin-top:0.75rem">
            <div class="live-log-header" @click="logExpanded = !logExpanded" style="cursor:pointer">
              📋 Log esecuzione {{ logExpanded ? '▲' : '▼' }}
            </div>
            <div v-if="logExpanded" class="live-log-body">
              <div v-for="(line, i) in activeDialogJob.logs" :key="i" class="log-line" :class="logLineClass(line)">{{ line }}</div>
            </div>
          </div>
          <button class="btn btn-close-dialog" @click="dialogVisible = false">Chiudi</button>
        </div>

        <!-- Corpo: COMPLETATO con riepilogo -->
        <div v-else-if="activeDialogJob.status === 'done'" class="dialog-body">

          <div class="dialog-success-icon">✅</div>
          <p class="dialog-done-text">Import completato con successo</p>

          <p v-if="activeDialogJob.finished_at" class="dialog-time">
            ⏱ {{ new Date(activeDialogJob.finished_at).toLocaleTimeString('it-IT') }}
          </p>

          <!-- TAB -->
          <div class="tabs">
            <button :class="{ active: activeTab === 'results' }" @click="activeTab = 'results'">
              Risultati
            </button>
            <button :class="{ active: activeTab === 'log' }" @click="activeTab = 'log'">
              Log
            </button>
          </div>

          <!-- RISULTATI -->
          <div v-if="activeTab === 'results'">

            <div v-if="activeDialogJob.result" class="result-summary">

              <!-- Kaggle / API-Football: chiave generica "imported" -->
              <template v-if="activeDialogJob.result.imported != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.imported }}</span>
                  <span class="stat-lbl">Giocatori importati</span>
                </div>
              </template>

              <!-- API-Football: aggiornati vs inseriti separati -->
              <template v-if="activeDialogJob.result.updated != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.updated }}</span>
                  <span class="stat-lbl">Aggiornati</span>
                </div>
              </template>

              <template v-if="activeDialogJob.result.inserted != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.inserted }}</span>
                  <span class="stat-lbl">Nuovi inseriti</span>
                </div>
              </template>

              <template v-if="activeDialogJob.result.players_updated != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.players_updated }}</span>
                  <span class="stat-lbl">Club aggiornati</span>
                </div>
              </template>

              <template v-if="activeDialogJob.result.players_inserted != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.players_inserted }}</span>
                  <span class="stat-lbl">Giocatori inseriti</span>
                </div>
              </template>

              <template v-if="activeDialogJob.result.players_total != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.players_total }}</span>
                  <span class="stat-lbl">Totale modifiche</span>
                </div>
              </template>

              <template v-if="activeDialogJob.result.teams_processed != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.teams_processed }}</span>
                  <span class="stat-lbl">Squadre processate</span>
                </div>
              </template>

              <!-- FBref specific fields -->
              <template v-if="activeDialogJob.result.players_found_on_site != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.players_found_on_site }}</span>
                  <span class="stat-lbl">Trovati sul sito</span>
                </div>
              </template>

              <template v-if="activeDialogJob.result.players_enriched_in_db != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.players_enriched_in_db }}</span>
                  <span class="stat-lbl">Arricchiti nel DB</span>
                </div>
              </template>

              <!-- Understat specific fields -->
              <template v-if="activeDialogJob.result.players_fetched != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.players_fetched }}</span>
                  <span class="stat-lbl">Giocatori ricevuti</span>
                </div>
              </template>

              <!-- StatsBomb specific fields -->
              <template v-if="activeDialogJob.result.matches_processed != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.matches_processed }}</span>
                  <span class="stat-lbl">Partite processate</span>
                </div>
              </template>

              <template v-if="activeDialogJob.result.players_with_stats != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.players_with_stats }}</span>
                  <span class="stat-lbl">Giocatori con stats</span>
                </div>
              </template>

              <template v-if="activeDialogJob.result.players_enriched != null">
                <div class="stat-box">
                  <span class="stat-val">{{ activeDialogJob.result.players_enriched }}</span>
                  <span class="stat-lbl">Arricchiti con xG/xA</span>
                </div>
              </template>

              <template v-if="activeDialogJob.result.players_not_matched != null">
                <div class="stat-box">
                  <span class="stat-val" style="color:#f59e0b">{{ activeDialogJob.result.players_not_matched }}</span>
                  <span class="stat-lbl">Non abbinati al DB</span>
                </div>
              </template>

            </div>

          </div>

          <!-- LOG -->
          <div v-if="activeTab === 'log'">
            <div class="live-log-container">
              <div class="live-log-header">📋 Log esecuzione</div>
              <div class="live-log-body">
                <div
                  v-for="(line, i) in activeDialogJob.logs"
                  :key="i"
                  class="log-line"
                  :class="logLineClass(line)"
                >
                  {{ line }}
                </div>
              </div>
            </div>
          </div>

          <button class="btn btn-close-dialog" @click="dialogVisible = false">
            Chiudi
          </button>

        </div>
        <!-- Corpo: ERRORE -->
        <div v-else-if="activeDialogJob.status === 'error'" class="dialog-body dialog-error">
          <div class="dialog-error-icon">❌</div>
          <p class="dialog-error-title">Import fallito</p>
          <pre class="error-detail">{{ activeDialogJob.error }}</pre>
          <!-- Log anche in caso di errore -->
          <div v-if="activeDialogJob.logs?.length" class="live-log-container error-log">
            <div class="live-log-header" @click="logExpanded = !logExpanded" style="cursor:pointer">
              📋 Log esecuzione {{ logExpanded ? '▲' : '▼' }}
            </div>
            <div v-if="logExpanded" class="live-log-body">
              <div
                v-for="(line, i) in activeDialogJob.logs"
                :key="i"
                class="log-line"
                :class="logLineClass(line)"
              >{{ line }}</div>
            </div>
          </div>
          <button class="btn btn-close-dialog" @click="dialogVisible = false">Chiudi</button>
        </div>

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
              <tr v-for="c in filteredSbComps" :key="`${c.competition_id}-${c.season_id}`">
                <td>{{ c.competition_id }}</td>
                <td>{{ c.season_id }}</td>
                <td>{{ c.name }}</td>
                <td>{{ c.season }}</td>
                <td>{{ c.country }}</td>
                <td>
                  <button class="btn-select" @click="selectSbComp(c)">Seleziona</button>
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
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import FBrefCsvImport from '@/components/FBrefCsvImport.vue'
import api from '@/api/client'
const activeTab = ref('results')
// ── StatsBomb: competizioni rapide pre-caricate ─────────────────
const SB_QUICK_COMPS = [
  { id: 12, name: 'Serie A' },
  { id: 11, name: 'La Liga' },
  { id: 16, name: 'Champions League' },
  { id: 2,  name: 'Premier League (storico)' },
  { id: 9,  name: 'Bundesliga' },
  { id: 7,  name: 'Ligue 1' },
  { id: 43, name: 'FIFA World Cup' },
  { id: 37, name: "FA Women's Super League" },
  { id: 55, name: 'UEFA Euro' },
]

const SB_SEASONS_MAP = {
  12: [
    { season_id: 12, season_name: '2019/20' },
    { season_id: 11, season_name: '2018/19' },
    { season_id: 27, season_name: '2015/16' },
  ],
  11: [
    { season_id: 90, season_name: '2020/21' },
    { season_id: 42, season_name: '2019/20' },
    { season_id:  4, season_name: '2018/19' },
    { season_id:  1, season_name: '2017/18' },
    { season_id: 27, season_name: '2015/16' },
    { season_id: 26, season_name: '2014/15' },
    { season_id: 25, season_name: '2013/14' },
    { season_id: 24, season_name: '2012/13' },
    { season_id: 23, season_name: '2011/12' },
    { season_id: 22, season_name: '2010/11' },
    { season_id: 21, season_name: '2009/10' },
    { season_id: 41, season_name: '2008/09' },
  ],
  16: [
    { season_id: 90, season_name: '2021/22' },
    { season_id: 44, season_name: '2020/21' },
    { season_id: 37, season_name: '2019/20' },
    { season_id: 8,  season_name: '2018/19' },
  ],
  43: [
    { season_id: 106, season_name: 'Qatar 2022' },
    { season_id:   3, season_name: 'Russia 2018' },
  ],
  9: [{ season_id: 27, season_name: '2015/16' }],
  7: [{ season_id: 27, season_name: '2015/16' }],
  2: [{ season_id: 27, season_name: '2003/04' }],
}

// ── Variabili d'ambiente ────────────────────────────────────────
const ENV_VARS = [
  { name: 'API_FOOTBALL_KEY',  usedBy: 'API-Football',       note: 'dashboard.api-football.com — free: 100 req/giorno' },
  { name: 'FOOTBALL_DATA_KEY', usedBy: 'Football-Data.org',  note: 'football-data.org/client/register — free: 10 req/min' },
  { name: 'DATABASE_URL',      usedBy: 'Backend (DB)',        note: 'Impostata automaticamente da docker-compose' },
  { name: 'POSTGRES_USER',     usedBy: 'PostgreSQL',          note: 'Default: football' },
  { name: 'POSTGRES_PASSWORD', usedBy: 'PostgreSQL',          note: 'Default: football123 — cambiare in produzione' },
]

const envFilePath  = 'football-scout/backend/.env'
const envExpanded  = ref(false)   // ← chiuso di default
const envStatus    = ref({})
const loadingEnv   = ref(false)
const envError     = ref(null)

async function loadEnvStatus() {
  loadingEnv.value = true
  envError.value   = null
  try {
    const { data } = await api.get('/ingest/env-status')
    envStatus.value = data
  } catch (e) {
    if (e.response?.status === 404) {
      envError.value = 'Endpoint /ingest/env-status non trovato. Aggiungi la route al backend.'
    } else {
      envError.value = e.message
    }
  } finally {
    loadingEnv.value = false
  }
}

// ── Config ─────────────────────────────────────────────────────
// Quick team IDs per campionato (utili come shortcut nella UI)
const APIF_TEAM_HINTS = {
  135: [ // Serie A
    { id: 489, name: 'AC Milan' }, { id: 496, name: 'Juventus' },
    { id: 505, name: 'Inter' },    { id: 492, name: 'Napoli' },
    { id: 497, name: 'Roma' },     { id: 487, name: 'Lazio' },
    { id: 500, name: 'Fiorentina' }, { id: 499, name: 'Atalanta' },
  ],
  39: [ // Premier League
    { id: 33, name: 'Manchester United' }, { id: 40, name: 'Liverpool' },
    { id: 42, name: 'Arsenal' },           { id: 50, name: 'Manchester City' },
    { id: 49, name: 'Chelsea' },           { id: 47, name: 'Tottenham' },
  ],
  140: [ // La Liga
    { id: 529, name: 'Barcelona' }, { id: 541, name: 'Real Madrid' },
    { id: 530, name: 'Atletico' },  { id: 548, name: 'Real Sociedad' },
  ],
  78: [ // Bundesliga
    { id: 157, name: 'Bayern' }, { id: 165, name: 'Borussia Dortmund' },
    { id: 168, name: 'RB Leipzig' }, { id: 161, name: 'Freiburg' },
  ],
  61: [ // Ligue 1
    { id: 85, name: 'Paris SG' }, { id: 80, name: 'Lyon' },
    { id: 91, name: 'Monaco' },   { id: 81, name: 'Marseille' },
  ],
}

// API-Football free tier: solo 2022-2024
const apifSeasons = [2024, 2023, 2022]
// Football-Data: stagioni recenti
const currentYear = new Date().getFullYear()
const fdSeasons   = Array.from({ length: 6 }, (_, i) => currentYear - 1 - i)

const config = ref({
  // API-Football
  league_id: 135,
  season:    2024,           // default sicuro per free tier

  // FBref
  fbref_league:  'serie_a',
  fbref_season:  '2023-2024',

  // StatsBomb
  statsbomb_comp:        12,
  statsbomb_season_id:   12,   // Serie A 2019/20
  statsbomb_max_matches: 50,

  // API-Football: modalità import
  import_mode: 'league',   // 'league' | 'team'
  team_id: null,            // se import_mode === 'team'

  // Kaggle
  kaggle_file:  '/app/app/data/players_22.csv',
  kaggle_limit: 2000,

  // Understat
  understat_league: 'serie_a',
  understat_season: new Date().getFullYear() - 1,

  // Football-Data
  fd_comp:   'SA',
  fd_season: currentYear - 1,
})

// Config accordion — tutti chiusi di default
const configOpen = ref({
  kaggle:        false,
  api_football:  false,
  fbref:         false,
  statsbomb:     false,
  understat:     false,
  football_data: false,
})

function toggleConfig(key) {
  configOpen.value[key] = !configOpen.value[key]
}
function expandAllConfig() {
  Object.keys(configOpen.value).forEach(k => { configOpen.value[k] = true })
}
function collapseAllConfig() {
  Object.keys(configOpen.value).forEach(k => { configOpen.value[k] = false })
}

const LEAGUE_NAMES = {
  135: 'Serie A', 39: 'Premier League', 140: 'La Liga', 78: 'Bundesliga', 61: 'Ligue 1',
}
const leagueName = (id) => LEAGUE_NAMES[id] || `Lega ${id}`

const activeSbSeasons = computed(() =>
  SB_SEASONS_MAP[config.value.statsbomb_comp] || []
)

function onSbCompChange() {
  const seasons = SB_SEASONS_MAP[config.value.statsbomb_comp]
  if (seasons && seasons.length) {
    config.value.statsbomb_season_id = seasons[0].season_id
  }
}

function sbCompName(id) {
  return SB_QUICK_COMPS.find(c => c.id === id)?.name || `Comp ID ${id}`
}
function sbSeasonName(seasonId) {
  const seasons = SB_SEASONS_MAP[config.value.statsbomb_comp] || []
  return seasons.find(s => s.season_id === seasonId)?.season_name || `Season ID ${seasonId}`
}

// ── Job status ──────────────────────────────────────────────────
const jobs = ref({})
let pollingInterval = null

const dialogVisible = ref(false)
const dialogSource  = ref(null)
const logExpanded   = ref(false)
const logContainer  = ref(null)
const stopping      = ref(false)

const SOURCE_KEY_MAP = {
  'kaggle':        'kaggle',
  'api-football':  'api_football',
  'statsbomb':     'statsbomb',
  'fbref':         'fbref',
  'understat':     'understat',
  'football-data': 'football_data',
  'all':           'all',
}

const SOURCE_LABELS = {
  kaggle:        { icon: '📊', label: 'Kaggle FIFA' },
  api_football:  { icon: '⚽', label: 'API-Football' },
  statsbomb:     { icon: '📈', label: 'StatsBomb' },
  fbref:         { icon: '🌐', label: 'FBref' },
  understat:     { icon: '📉', label: 'Understat' },
  football_data: { icon: '🏛', label: 'Football-Data.org' },
  all:           { icon: '🚀', label: 'Tutte le sorgenti' },
}

const isAnyRunning = computed(() =>
  Object.values(jobs.value).some(j => j?.status === 'running')
)

// Rileva se API-Football si è fermato al limite delle 3 pagine del free tier
// (il backend imposta pages_fetched nel result)
const isPageLimited = computed(() => {
  const job = jobs.value['api_football']
  if (!job || job.status !== 'done') return false
  return job.result?.pages_fetched >= 3 && job.result?.pages_total > 3
})

const activeDialogJob = computed(() => {
  if (!dialogSource.value) return null
  const key = SOURCE_KEY_MAP[dialogSource.value] ?? dialogSource.value
  return jobs.value[key] ?? null
})

const activeDialogLabel = computed(() => {
  const key = SOURCE_KEY_MAP[dialogSource.value] ?? dialogSource.value
  return SOURCE_LABELS[key] ?? { icon: '🔄', label: key }
})

async function loadStatus() {
  try {
    const { data } = await api.get('/ingest/status')
    jobs.value = data
    if (!isAnyRunning.value) stopPolling()
  } catch (e) {
    // silenzioso
  }
}

function startPolling() {
  stopPolling()
  pollingInterval = setInterval(loadStatus, 2000)
}

function stopPolling() {
  if (pollingInterval) {
    clearInterval(pollingInterval)
    pollingInterval = null
  }
}

async function stopImport() {
  if (!dialogSource.value || stopping.value) return
  stopping.value = true
  try {
    await api.post(`/ingest/${dialogSource.value}/cancel`)
    // Il backend imposta status = 'cancelled'; aspettiamo il prossimo polling
    await loadStatus()
  } catch (e) {
    // fallback: se l'endpoint non esiste, lo segnaliamo nel log visivo
    console.warn('Endpoint /cancel non disponibile:', e.message)
    // Chiudiamo comunque il dialog e stoppiamo il polling
    stopPolling()
    dialogVisible.value = false
  } finally {
    stopping.value = false
  }
}

onUnmounted(() => stopPolling())

// ── Run handlers ─────────────────────────────────────────────────
async function runAll() {
  logExpanded.value = false
  await api.post('/ingest/all', {
    kaggle_file:           config.value.kaggle_file,
    kaggle_limit:          config.value.kaggle_limit,
    api_league:            config.value.league_id,
    season:                config.value.season,
    statsbomb_comp:        config.value.statsbomb_comp,
    statsbomb_season_id:   config.value.statsbomb_season_id,
    statsbomb_max_matches: config.value.statsbomb_max_matches || 50,
    fbref_league:          config.value.fbref_league,
    fbref_season:          config.value.fbref_season,
    understat_league:      config.value.understat_league,
    understat_season:      config.value.understat_season,
    football_data_comp:    config.value.fd_comp,
  })
  dialogSource.value = 'all'
  dialogVisible.value = true
  await loadStatus()
  startPolling()
}

async function runSource(source) {
  logExpanded.value = false
  const payloads = {
    'kaggle': {
      file_path: config.value.kaggle_file,
      limit:     config.value.kaggle_limit,
    },
    'api-football': {
      league_id: config.value.league_id,
      season:    config.value.season,
      ...(config.value.import_mode === 'team' && config.value.team_id
        ? { team_id: config.value.team_id }
        : {}),
    },
    'statsbomb': {
      competition_id: config.value.statsbomb_comp,
      season_id:      config.value.statsbomb_season_id,
      max_matches:    config.value.statsbomb_max_matches || 50,
    },
    'fbref': {
      league_key: config.value.fbref_league,
      season:     config.value.fbref_season,
    },
    'understat': {
      league_key: config.value.understat_league,
      season:     config.value.understat_season,
    },
    'football-data': {
      competition_code: config.value.fd_comp,
      season:           config.value.fd_season,
    },
  }
  await api.post(`/ingest/${source}`, payloads[source])
  dialogSource.value  = source
  dialogVisible.value = true
  await loadStatus()
  startPolling()
}

// ── Montaggio ─────────────────────────────────────────────────
onMounted(() => {
  loadStatus()
  loadEnvStatus()
})

// Auto-scroll del log live
watch(
  () => activeDialogJob.value?.logs?.length,
  async () => {
    await nextTick()
    if (logContainer.value) {
      const body = logContainer.value.querySelector('.live-log-body')
      if (body) body.scrollTop = body.scrollHeight
    }
  }
)

/**
 * Classifica una riga di log per colorarla:
 *   - errore:  riga contiene ERROR / ✗ / ⚠
 *   - warn:    riga contiene WARNING / ⚠️
 *   - ok:      riga contiene ✅ / importati / arricchiti
 *   - debug:   riga inizia con DEBUG
 */
function logLineClass(line) {
  if (!line) return {}
  const l = line.toUpperCase()
  if (l.includes('ERROR') || l.includes('✗') || l.includes('ERRORE')) return { 'log-error': true }
  if (l.includes('⚠') || l.includes('WARN')) return { 'log-warn': true }
  if (l.includes('✅') || l.includes('COMPLETAT') || l.includes('IMPORTATI') || l.includes('ARRICCHITI')) return { 'log-ok': true }
  if (l.startsWith('DEBUG')) return { 'log-debug': true }
  return {}
}

const showSbModal = ref(false)
const sbComps     = ref([])
const sbSearch    = ref('')

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
  config.value.statsbomb_comp      = c.competition_id
  config.value.statsbomb_season_id = c.season_id
  showSbModal.value = false
}

function statusClass(key) {
  const s = jobs.value[key]?.status
  return {
    'status-running': s === 'running',
    'status-done':    s === 'done',
    'status-error':   s === 'error',
  }
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
            <span v-if="job.result" class="result-detail">— {{ formatResult(job.result) }}</span>
          </span>
          <span v-else-if="job.status === 'error'" class="status-badge error" :title="job.error">
            ❌ Errore — {{ truncate(job.error) }}
          </span>
          <span v-else class="status-badge idle">⬜ Non eseguito</span>
        </div>
      `,
      methods: {
        formatTime(iso)  { return new Date(iso).toLocaleTimeString('it-IT') },
        formatResult(r) {
          if (r?.imported != null)         return `${r.imported} giocatori importati`
          if (r?.players_enriched != null) return `${r.players_enriched} giocatori arricchiti`
          if (r?.players_updated != null)  return `${r.players_updated} giocatori aggiornati`
          return JSON.stringify(r).slice(0, 60)
        },
        truncate(s) { return s ? s.slice(0, 80) : '' },
      },
    },
  },
}
</script>

<style scoped>
/* ── Layout pagina ─────────────────────────────────────────── */
.ingest-page { max-width: 1200px; margin: 0 auto; padding: 1.5rem; }
.page-header { margin-bottom: 1.5rem; }
.page-header h1 { margin: 0 0 0.25rem; font-size: 1.6rem; }
.subtitle { margin: 0; color: var(--text-muted, #6b7280); font-size: 0.9rem; }

.card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.25rem;
}

/* ── Env panel ─────────────────────────────────────────────── */
.env-panel { margin-bottom: 1.25rem; }

.env-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  user-select: none;
}
.env-header-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.env-header-left h2 { margin: 0; font-size: 1.05rem; }
.env-path { margin: 0.15rem 0 0; font-size: 0.78rem; color: var(--text-muted, #6b7280); }
.env-path code { background: var(--bg,#f3f4f6); padding: 0.1rem 0.3rem; border-radius: 3px; }

.env-toggle-icon {
  font-size: 0.75rem;
  color: var(--text-muted, #9ca3af);
  flex-shrink: 0;
}

.env-header-right {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.env-summary-badges {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
}

.btn-refresh-env {
  padding: 0.3rem 0.75rem;
  border: 1px solid var(--border, #e5e7eb);
  background: var(--bg, #f9fafb);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 0.3rem;
  white-space: nowrap;
  flex-shrink: 0;
}
.btn-refresh-env:disabled { opacity: 0.5; cursor: not-allowed; }

.env-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  margin: 0.75rem 0;
}
.env-table th {
  text-align: left;
  padding: 0.4rem 0.6rem;
  border-bottom: 2px solid var(--border, #e5e7eb);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted, #6b7280);
}
.env-table td {
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid var(--border, #f3f4f6);
  vertical-align: middle;
}
.env-table tr:hover td { background: #fafafa; }

.env-name     { font-size: 0.82rem; font-weight: 600; }
.env-used-by  { font-size: 0.8rem; color: var(--text-muted, #6b7280); }
.env-note     { font-size: 0.75rem; color: var(--text-muted, #9ca3af); }

.env-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.15rem 0.5rem;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
}
.env-badge.set      { background: #bbf7d0; color: #064e3b; }
.env-badge.missing  { background: #fecaca; color: #7f1d1d; }
.env-badge.checking { background: #fde68a; color: #78350f; }
.env-badge.unknown  { background: var(--bg,#f3f4f6); color: var(--text-muted,#6b7280); }

.env-error {
  font-size: 0.8rem;
  color: #b45309;
  background: #fef3c7;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  margin-bottom: 0.5rem;
}
.env-tip { font-size: 0.78rem; color: var(--text-muted, #6b7280); margin: 0; }
.env-tip code { background: var(--bg,#f3f4f6); padding: 0.1rem 0.3rem; border-radius: 3px; }

/* ── Config panel accordion ────────────────────────────────── */
.config-panel { padding: 1.25rem 1.5rem; }
.config-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}
.config-panel-header h2 { margin: 0; font-size: 1.05rem; }
.config-expand-all {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
}
.btn-text {
  background: none;
  border: none;
  color: var(--primary, #3b82f6);
  cursor: pointer;
  font-size: 0.8rem;
  padding: 0;
}
.btn-text:hover { text-decoration: underline; }
.sep { color: var(--text-muted, #d1d5db); }

.config-source-block {
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 0.5rem;
  overflow: hidden;
  transition: box-shadow 0.15s;
}
.config-source-block.open {
  box-shadow: 0 1px 6px rgba(0,0,0,0.07);
}
.config-source-block.open .config-source-header {
  border-bottom: 1px solid var(--border, #e5e7eb);
  background: var(--bg, #f9fafb);
}

.config-source-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.65rem 1rem;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}
.config-source-header:hover { background: var(--bg, #f9fafb); }

.config-src-icon  { font-size: 1.1rem; flex-shrink: 0; }
.config-src-name  { font-weight: 600; font-size: 0.9rem; flex-shrink: 0; }
.config-src-summary {
  margin-left: auto;
  font-size: 0.78rem;
  color: var(--text-muted, #6b7280);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}
.config-chevron {
  font-size: 0.65rem;
  color: var(--text-muted, #9ca3af);
  flex-shrink: 0;
  margin-left: 0.4rem;
}

.config-fields {
  padding: 1rem;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.85rem;
}

.config-note-warning {
  grid-column: 1 / -1;
  background: #fef3c7;
  color: #92400e;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  font-size: 0.8rem;
}
.config-note-info {
  grid-column: 1 / -1;
  background: #eff6ff;
  color: #1e40af;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  font-size: 0.8rem;
}

.config-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.config-group label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text, #374151);
}
.config-group select,
.config-group input {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border, #d1d5db);
  border-radius: 6px;
  font-size: 0.875rem;
  background: var(--input-bg, #fff);
  color: var(--text, #111827);
  transition: border-color 0.15s;
}
.config-group select:focus,
.config-group input:focus {
  outline: none;
  border-color: var(--primary, #3b82f6);
  box-shadow: 0 0 0 2px rgba(59,130,246,0.15);
}
.config-group small { font-size: 0.73rem; color: var(--text-muted, #6b7280); }

/* Hint icon */
.hint-icon {
  cursor: help;
  font-size: 0.85rem;
  opacity: 0.7;
  margin-left: 0.15rem;
}

/* ── Run all ──────────────────────────────────────────────── */
.run-all-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}
.run-all-info h2 { margin: 0 0 0.25rem; font-size: 1.1rem; }
.run-all-info p  { margin: 0; font-size: 0.85rem; color: var(--text-muted, #6b7280); }

.btn { padding: 0.6rem 1.4rem; border-radius: 8px; font-size: 0.9rem; font-weight: 600; border: none; cursor: pointer; }
.btn-all {
  background: var(--primary, #3b82f6);
  color: #fff;
  white-space: nowrap;
  transition: background 0.2s, opacity 0.2s;
}
.btn-all:hover:not(:disabled) { background: #1d4ed8; }
.btn-all:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Sources grid ─────────────────────────────────────────── */
.sources-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.source-card {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 1.1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.source-card.status-running { border-color: #f59e0b; box-shadow: 0 0 0 2px rgba(245,158,11,0.15); }
.source-card.status-done    { border-color: #10b981; box-shadow: 0 0 0 2px rgba(16,185,129,0.10); }
.source-card.status-error   { border-color: #ef4444; box-shadow: 0 0 0 2px rgba(239,68,68,0.10); }

.source-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.source-icon { font-size: 1.6rem; flex-shrink: 0; }
.source-header h3 { margin: 0; font-size: 1rem; }

.badge {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 20px;
  font-size: 0.7rem;
  font-weight: 600;
}
.badge-free { background: #d1fae5; color: #065f46; }
.badge-key  { background: #fde68a; color: #78350f; }

/* config-src-badge (inside accordion header) */
.config-src-badge {
  display: inline-block;
  padding: 0.1rem 0.45rem;
  border-radius: 20px;
  font-size: 0.68rem;
  font-weight: 600;
  flex-shrink: 0;
}

.source-desc {
  font-size: 0.82rem;
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

/* ── Job status badges ─────────────────────────────────────── */
.job-status { font-size: 0.8rem; }
.status-badge { padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 500; }
.status-badge.running { background: #fde68a; color: #78350f; }
.status-badge.done    { background: #86efac; color: #14532d; }
.status-badge.error   { background: #fca5a5; color: #7f1d1d; }
.status-badge.idle    { background: var(--bg, #f3f4f6); color: var(--text-muted, #4b5563); }
.result-detail { opacity: 0.8; }

/* ── Modal ─────────────────────────────────────────────────── */
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
  width: min(1000px, 96vw);
  max-height: 95vh;
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

/* ── Dialog progresso ──────────────────────────────────────── */

.progress-dialog {
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.dialog-body {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.dialog-header-actions { display: flex; align-items: center; gap: 0.5rem; }

.btn-stop-import {
  padding: 0.4rem 1rem;
  background: #fef3c7;
  color: #92400e;
  border: 1.5px solid #f59e0b;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-stop-import:hover:not(:disabled) { background: #fde68a; }
.btn-stop-import:disabled { opacity: 0.6; cursor: not-allowed; }

.dialog-title { display: flex; align-items: center; gap: 0.75rem; }
.dialog-icon { font-size: 1.75rem; }
.dialog-title h3 { margin: 0; font-size: 1.1rem; }
.dialog-subtitle { font-size: 0.8rem; color: var(--text-muted, #6b7280); }

.dialog-body {
  padding: 1rem 0 0.5rem;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.progress-pulse {
  position: relative;
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pulse-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 3px solid var(--primary, #3b82f6);
  animation: pulse-ring 1.4s ease-in-out infinite;
}
@keyframes pulse-ring {
  0%   { transform: scale(0.8); opacity: 0.8; }
  50%  { transform: scale(1.1); opacity: 0.3; }
  100% { transform: scale(0.8); opacity: 0.8; }
}
.pulse-icon { font-size: 1.8rem; position: relative; z-index: 1; }


.dialog-hint { font-size: 0.8rem; color: var(--text-muted, #9ca3af); margin: 0; }

.progress-bar-track {
  width: 100%;
  height: 6px;
  background: var(--border, #e5e7eb);
  border-radius: 3px;
  overflow: hidden;
  margin-top: 0.5rem;
}
.progress-bar-indeterminate {
  height: 100%;
  width: 40%;
  background: var(--primary, #3b82f6);
  border-radius: 3px;
  animation: indeterminate 1.5s ease-in-out infinite;
}
@keyframes indeterminate {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(350%); }
}

.dialog-success-icon { font-size: 2.5rem; }
.dialog-done-text { font-weight: 700; font-size: 1rem; margin: 0; }
.dialog-time { font-size: 0.8rem; color: var(--text-muted, #6b7280); margin: 0; }

.result-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  justify-content: center;
}
.stat-box {
  background: var(--bg, #f3f4f6);
  border-radius: 10px;
  padding: 0.6rem 1rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  min-width: 100px;
}
.stat-val { font-size: 1.5rem; font-weight: 800; color: var(--primary, #3b82f6); }
.stat-lbl { font-size: 0.7rem; color: var(--text-muted, #6b7280); text-align: center; }

.all-sources-summary { width: 100%; max-height: 200px; overflow-y: auto; text-align: left; }
.all-sources-summary h4 { font-size: 0.85rem; margin: 0.5rem 0; }
.source-row {
  display: flex;
  justify-content: space-between;
  padding: 0.3rem 0;
  border-bottom: 1px solid var(--border, #f3f4f6);
  font-size: 0.85rem;
}
.src-status.ok      { color: #10b981; }
.src-status.skipped { color: #f59e0b; }
.src-status.error   { color: #ef4444; }

.dialog-error { font-size: 2.5rem; }
.dialog-error-icon  { font-size: 2.5rem; }
.dialog-error-title { font-weight: 700; font-size: 1rem; margin: 0; color: #dc2626; }
.error-detail {
  background: #fee2e2;
  color: #991b1b;
  padding: 0.6rem 0.9rem;
  border-radius: 6px;
  font-size: 0.78rem;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-word;
  width: 100%;
  text-align: left;
  max-height: 120px;
  overflow-y: auto;
}

.btn-close-dialog {
  margin-top: 0.5rem;
  padding: 0.5rem 2rem;
  background: var(--primary, #3b82f6);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
}
.btn-close-dialog:hover { background: #1d4ed8; }

/* Spin animation per il bottone refresh */
@keyframes spin { to { transform: rotate(360deg); } }
.spin { display: inline-block; animation: spin 0.8s linear infinite; }

/* Placeholder per mantenere l'allineamento dell'header quando X è nascosto */
.btn-close-placeholder { width: 1.8rem; height: 1.8rem; display: inline-block; }

/* ── Live log ───────────────────────────────────────────────── */
.live-log-container {
  margin-top: 1rem;
  border-radius: 8px;
  overflow: hidden; /* 🔥 unisce header + body */
}
.live-log-header {
  background: #1e1e2e;
  color: #cdd6f4;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.35rem 0.75rem;
  user-select: none;
}
.live-log-body {
  max-height: 200px;
  overflow-y: auto;
  padding: 0.6rem 0.75rem;
  background: #1e1e2e;
  font-family: monospace;
  font-size: 0.8rem;
  line-height: 1.4;
  border-radius: 0 0 8px 8px;
}
.live-log {
  margin-top: 1rem;
  flex-shrink: 0;   /* 🔥 impedisce collasso */
}

.log-line {
  color: #e5e7eb;   /* 🔥 più leggibile */
  white-space: pre-wrap;
  word-break: break-word;
}
.log-line.log-ok    { color: #a6e3a1; }
.log-line.log-error { color: #f38ba8; }
.log-line.log-warn  { color: #f9e2af; }
.log-line.log-debug { color: #89b4fa; opacity: 0.75; }

.done-log .live-log-header  { background: #1e1e2e; }
.error-log .live-log-header { background: #2d1b1b; }
.error-log .live-log-body   { max-height: 35vh; background: #2d1b1b; }

/* ── tab ───────────────────────────────────────── */
.tabs {
  display: flex;
  gap: 0.5rem;
  margin: 1rem 0;
}

.tabs button {
  flex: 1;
  padding: 0.5rem;
  border: none;
  border-radius: 8px;
  background: #eee;
  cursor: pointer;
  font-weight: 600;
}

.tabs button.active {
  background: #3b82f6;
  color: white;
}

/* ── Team hint chips ───────────────────────────────────────── */
.team-id-hints {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.5rem;
}
.team-hint-chip {
  background: var(--bg, #f3f4f6);
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 20px;
  padding: 0.15rem 0.6rem;
  font-size: 0.72rem;
  cursor: pointer;
  color: var(--primary, #3b82f6);
  transition: background 0.15s;
}
.team-hint-chip:hover { background: #dbeafe; border-color: #93c5fd; }

/* ── Avviso limite 3 pagine ────────────────────────────────── */
.page-limit-warning {
  background: #fef3c7;
  border: 1px solid #f59e0b;
  border-radius: 8px;
  padding: 0.65rem 0.9rem;
  font-size: 0.82rem;
  color: #92400e;
  width: 100%;
  text-align: left;
  line-height: 1.5;
}
.page-limit-warning a { color: #b45309; font-weight: 600; }

.source-page-limit-badge {
  background: #fef3c7;
  border: 1px solid #f59e0b;
  border-radius: 6px;
  padding: 0.25rem 0.6rem;
  font-size: 0.75rem;
  color: #92400e;
  margin-bottom: 0.4rem;
  font-weight: 500;
}
</style>