<!--
FBrefCsvImport.vue
==================
Componente da aggiungere in DataIngestion.vue per importare FBref da CSV.
Risolve il problema del 403 da Docker senza richiedere scraping.

ISTRUZIONI DI INTEGRAZIONE:
  1. Copia questo file in frontend/src/components/FBrefCsvImport.vue
  2. In DataIngestion.vue aggiunge nell'import:
       import FBrefCsvImport from '@/components/FBrefCsvImport.vue'
  3. In DataIngestion.vue aggiunge nel template, vicino alla sezione FBref:
       <FBrefCsvImport />

COME USARLO (utente finale):
  1. Apri nel browser: https://fbref.com/en/comps/11/stats/Serie-A-Stats
     (o la lega che ti interessa)
  2. Scorri fino alla tabella "Standard Stats"
  3. Sopra la tabella trovi il link "Share & Export" → "Get table as CSV"
  4. Si apre una popup con il testo CSV — seleziona tutto (Ctrl+A) e copia (Ctrl+C)
  5. Torna su Football Scout → Gestione Dati → sezione "FBref CSV"
  6. Incolla nel campo di testo e clicca "Importa CSV"
-->

<template>
  <div class="fbref-csv-card card">
    <div class="fbref-header">
      <div class="fbref-title">
        <span class="fbref-icon">🌐</span>
        <div>
          <h3>FBref — Importazione CSV</h3>
          <p class="fbref-subtitle">Bypass del 403 · Dati direttamente dal browser</p>
        </div>
      </div>
      <span class="badge badge-free">Gratis</span>
    </div>

    <!-- Istruzioni -->
    <div class="instructions-box">
      <p class="instr-title">📋 Come fare:</p>
      <ol class="instr-list">
        <li>
          Apri
          <a :href="fbrefUrl" target="_blank" rel="noopener">{{ fbrefUrl }}</a>
          nel browser
        </li>
        <li>Scorri fino alla tabella <strong>Standard Stats</strong></li>
        <li>Clicca <strong>"Share &amp; Export"</strong> → <strong>"Get table as CSV"</strong></li>
        <li>Seleziona tutto il testo (Ctrl+A) e copialo (Ctrl+C)</li>
        <li>Incolla qui sotto e clicca <strong>Importa CSV</strong></li>
      </ol>
    </div>

    <!-- Selezione lega -->
    <div class="field-group">
      <label class="field-label">Lega</label>
      <select v-model="selectedLeague" @change="updateUrl">
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

    <!-- Area testo CSV -->
    <div class="field-group">
      <label class="field-label">
        Incolla qui il CSV copiato da FBref
        <span class="char-count" v-if="csvText">{{ csvText.length.toLocaleString() }} caratteri</span>
      </label>
      <textarea
        v-model="csvText"
        class="csv-textarea"
        placeholder="Incolla qui il CSV di FBref (Ctrl+V)&#10;Esempio prima riga:&#10;Player,Nation,Pos,Squad,Age,Born,MP,Starts,Min,90s,Gls,Ast..."
        rows="8"
        spellcheck="false"
      />
    </div>

    <!-- Validazione rapida -->
    <div v-if="csvText && csvPreview" class="csv-preview">
      <span class="preview-ok">✅ CSV rilevato:</span>
      <span class="preview-info">{{ csvPreview }}</span>
    </div>
    <div v-else-if="csvText && !csvPreview" class="csv-preview csv-preview-warn">
      ⚠️ Il testo non sembra un CSV FBref valido. Assicurati di aver copiato dalla voce "Get table as CSV".
    </div>

    <!-- Azioni -->
    <div class="action-bar">
      <button
        class="btn btn-primary btn-import"
        :disabled="!canImport || importing"
        @click="doImport"
      >
        <span v-if="importing">⏳ Importazione in corso…</span>
        <span v-else>⬆️ Importa CSV</span>
      </button>
      <button class="btn btn-ghost" @click="csvText = ''" :disabled="!csvText || importing">
        🗑️ Svuota
      </button>
    </div>

    <!-- Risultato -->
    <div v-if="result" class="result-box" :class="result.error ? 'result-error' : 'result-ok'">
      <template v-if="result.error">
        ❌ Errore: {{ result.error }}
      </template>
      <template v-else>
        ✅ Importazione completata:
        <strong>{{ result.players_enriched_in_db }}</strong> giocatori arricchiti
        su {{ result.players_found_on_site }} trovati nel CSV
        <span v-if="result.players_not_matched" class="not-matched">
          · {{ result.players_not_matched }} non abbinati al DB
        </span>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import api from '@/api/client'

const LEAGUE_URLS = {
  serie_a:          'https://fbref.com/en/comps/11/stats/Serie-A-Stats',
  premier_league:   'https://fbref.com/en/comps/9/stats/Premier-League-Stats',
  la_liga:          'https://fbref.com/en/comps/12/stats/La-Liga-Stats',
  bundesliga:       'https://fbref.com/en/comps/20/stats/Bundesliga-Stats',
  ligue_1:          'https://fbref.com/en/comps/13/stats/Ligue-1-Stats',
  champions_league: 'https://fbref.com/en/comps/8/stats/Champions-League-Stats',
  eredivisie:       'https://fbref.com/en/comps/23/stats/Eredivisie-Stats',
  primeira_liga:    'https://fbref.com/en/comps/32/stats/Primeira-Liga-Stats',
}

const selectedLeague = ref('serie_a')
const fbrefUrl       = computed(() => LEAGUE_URLS[selectedLeague.value])
const csvText        = ref('')
const importing      = ref(false)
const result         = ref(null)

// Valida che il CSV sembri quello di FBref
const csvPreview = computed(() => {
  if (!csvText.value || csvText.value.length < 20) return null
  const lines = csvText.value
    .split('\n')
    .filter(l => !l.startsWith('#') && l.trim())
  if (lines.length < 2) return null
  const header = lines[0].toLowerCase()
  if (!header.includes('player') && !header.includes('squad') && !header.includes('gls')) return null
  const dataRows = lines.length - 1
  return `${dataRows} righe · colonne: ${lines[0].split(',').length}`
})

const canImport = computed(() => csvPreview.value !== null && csvText.value.length > 50)

function updateUrl() {
  result.value = null
}

async function doImport() {
  if (!canImport.value) return
  importing.value = true
  result.value = null

  try {
    const { data } = await api.post('/ingest/fbref/csv', {
    csv_text:   csvText.value,
    league_key: selectedLeague.value,
    }, { 
        timeout: 300000 // 5 minuti in millisecondi
    });
    result.value = data
    if (data.players_enriched_in_db > 0) {
      csvText.value = '' // svuota dopo successo
    }
  } catch (e) {
    result.value = { error: e.response?.data?.detail || e.message }
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.fbref-csv-card {
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
}

.fbref-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
}
.fbref-title { display: flex; gap: 0.75rem; align-items: flex-start; }
.fbref-icon { font-size: 1.4rem; flex-shrink: 0; padding-top: 2px; }
.fbref-title h3 { margin: 0 0 0.15rem; font-size: 1rem; font-weight: 700; }
.fbref-subtitle { margin: 0; font-size: 0.8rem; color: var(--color-muted, #6b7280); }

.badge { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 20px; font-size: 0.7rem; font-weight: 700; }
.badge-free { background: #d1fae5; color: #065f46; }

.instructions-box {
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
}
.instr-title { margin: 0 0 0.4rem; font-size: 0.85rem; font-weight: 700; color: var(--color-primary, #3b82f6); }
.instr-list { margin: 0; padding-left: 1.25rem; font-size: 0.83rem; line-height: 1.7; }
.instr-list a { color: var(--color-primary, #3b82f6); }

.field-group { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 0.85rem; }
.field-label { font-size: 0.8rem; font-weight: 600; color: var(--color-muted, #4b5563); display: flex; justify-content: space-between; align-items: center; }
.char-count { font-size: 0.72rem; color: var(--color-muted, #9ca3af); font-weight: 400; }

.csv-textarea {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 8px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 0.78rem;
  line-height: 1.5;
  resize: vertical;
  background: #1e1e2e;
  color: #cdd6f4;
  box-sizing: border-box;
  min-height: 140px;
}
.csv-textarea:focus { outline: none; border-color: var(--color-primary, #3b82f6); box-shadow: 0 0 0 2px rgba(59,130,246,0.15); }

.csv-preview {
  font-size: 0.8rem;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  margin-bottom: 0.75rem;
}
.preview-ok { color: #10b981; font-weight: 600; }
.preview-info { color: var(--color-muted, #6b7280); margin-left: 0.4rem; }
.csv-preview-warn { background: #fef3c7; color: #92400e; }

.action-bar { display: flex; gap: 0.75rem; align-items: center; }
.btn { padding: 0.55rem 1.25rem; border-radius: 8px; font-size: 0.875rem; font-weight: 600; border: none; cursor: pointer; transition: background 0.15s, opacity 0.15s; }
.btn-primary { background: var(--color-primary, #3b82f6); color: #fff; }
.btn-primary:hover:not(:disabled) { background: #1d4ed8; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: transparent; border: 1px solid var(--color-border, #e5e7eb); color: var(--color-text, #374151); }
.btn-ghost:hover:not(:disabled) { background: rgba(0,0,0,0.05); }
.btn-ghost:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-import { min-width: 180px; }

.result-box { margin-top: 1rem; padding: 0.65rem 0.9rem; border-radius: 8px; font-size: 0.85rem; }
.result-ok { background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16,185,129,0.3); color: #065f46; }
.result-error { background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239,68,68,0.3); color: #991b1b; }
.not-matched { opacity: 0.7; }
</style>