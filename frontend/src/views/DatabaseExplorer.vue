<template>
  <div class="db-explorer">
    <div class="page-header">
      <h1>🗄️ Database Explorer</h1>
      <p class="subtitle">Esplora le tabelle e verifica il contenuto del database</p>
    </div>

    <div class="explorer-layout">

      <!-- Sidebar: lista tabelle -->
      <aside class="sidebar card">
        <div class="sidebar-header">
          <h3>Tabelle</h3>
          <button class="btn-refresh" @click="loadTables" :disabled="loadingTables">
            <span :class="{ spin: loadingTables }">↻</span>
          </button>
        </div>

        <div v-if="loadingTables" class="loading">Caricamento…</div>

        <ul v-else class="table-list">
          <li
            v-for="t in tables"
            :key="t.name"
            class="table-item"
            :class="{ active: selectedTable === t.name }"
            @click="selectTable(t.name)"
          >
            <span class="table-name">{{ t.name }}</span>
            <span class="row-count">{{ formatCount(t.row_count) }}</span>
          </li>
        </ul>
      </aside>

      <!-- Main content -->
      <main class="main-content">

        <!-- Tab selector -->
        <div class="tab-bar card">
          <button class="tab-btn" :class="{ active: activeTab === 'browse' }" @click="activeTab = 'browse'">
            📋 Sfoglia dati
          </button>
          <button class="tab-btn" :class="{ active: activeTab === 'schema' }" @click="activeTab = 'schema'">
            🏗 Schema
          </button>
          <button class="tab-btn" :class="{ active: activeTab === 'query' }" @click="activeTab = 'query'">
            💬 SQL Query
          </button>
        </div>

        <!-- ── TAB: Sfoglia ───────────────────────────────────── -->
        <div v-if="activeTab === 'browse'" class="tab-content card">
          <div v-if="!selectedTable" class="empty-state">← Seleziona una tabella dalla sidebar</div>
          <template v-else>
            <div class="browse-header" style="flex-shrink:0">
              <h3>{{ selectedTable }}</h3>
              <div class="browse-controls">
                <label>Righe per pagina:</label>
                <select v-model.number="pageSize" @change="loadData">
                  <option :value="20">20</option>
                  <option :value="50">50</option>
                  <option :value="100">100</option>
                  <option :value="200">200</option>
                </select>
              </div>
            </div>

            <div v-if="loadingData" class="loading">Caricamento dati…</div>
            <template v-else-if="tableData">
              <div class="table-info" style="flex-shrink:0">
                {{ tableData.rows.length }} di {{ formatCount(tableData.total) }} righe
                — pagina {{ currentPage }} / {{ totalPages }}
              </div>
              <div class="browse-actions" style="flex-shrink:0">
                <button class="btn-open-dialog" @click="browseDialogVisible = true">🔍 Visualizza nella finestra</button>
                <button class="btn-export" @click="exportBrowseExcel">📊 Excel</button>
                <button class="btn-export" @click="exportBrowseCsv">📥 CSV</button>
                <div class="pagination-inline">
                  <button class="btn-page" :disabled="currentOffset === 0" @click="changePage(-1)">← Prec.</button>
                  <button class="btn-page" :disabled="currentOffset + pageSize >= tableData.total" @click="changePage(1)">Succ. →</button>
                </div>
              </div>
              <p class="dialog-hint-inline" style="flex-shrink:0">💡 Per vedere tutti i dati clicca "Visualizza nella finestra".</p>
            </template>
          </template>
        </div>

        <!-- ── TAB: Schema ────────────────────────────────────── -->
        <!-- FIX #6: overflow-y: auto sul tab-content dello schema -->
        <div v-if="activeTab === 'schema'" class="tab-content tab-content-scroll card">
          <div v-if="!selectedTable" class="empty-state">← Seleziona una tabella dalla sidebar</div>
          <template v-else>
            <div v-if="loadingSchema" class="loading">Caricamento schema…</div>
            <template v-else-if="tableSchema">
              <h3 style="flex-shrink:0; margin-bottom:0.75rem">Schema: {{ tableSchema.table }} ({{ tableSchema.columns.length }} colonne)</h3>

              <!-- FIX: tabella schema dentro un div scrollabile -->
              <div class="schema-scroll">
                <table class="schema-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Colonna</th>
                      <th>Tipo</th>
                      <th>Nullable</th>
                      <th>Default</th>
                      <th>PK</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(col, idx) in tableSchema.columns" :key="col.name" :class="{ 'pk-row': col.primary_key }">
                      <td class="col-idx">{{ idx + 1 }}</td>
                      <td><span v-if="col.primary_key">🔑 </span>{{ col.name }}</td>
                      <td><code>{{ col.type }}</code></td>
                      <td><span :class="col.nullable ? 'yes' : 'no'">{{ col.nullable ? 'Sì' : 'No' }}</span></td>
                      <td><code v-if="col.default">{{ col.default }}</code><span v-else>—</span></td>
                      <td>{{ col.primary_key ? '✓' : '' }}</td>
                    </tr>
                  </tbody>
                </table>

                <div v-if="tableSchema.indexes.length" class="indexes">
                  <h4>Indici ({{ tableSchema.indexes.length }})</h4>
                  <table class="schema-table">
                    <thead><tr><th>Nome</th><th>Colonne</th><th>Unique</th></tr></thead>
                    <tbody>
                      <tr v-for="idx in tableSchema.indexes" :key="idx.name">
                        <td>{{ idx.name }}</td>
                        <td>{{ idx.columns.join(', ') }}</td>
                        <td>{{ idx.unique ? '✓' : '' }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </template>
          </template>
        </div>

        <!-- ── TAB: SQL Query ─────────────────────────────────── -->
        <!-- FIX #3/#5: il tab-content non si rimpicciolisce dopo l'esecuzione -->
        <div v-if="activeTab === 'query'" class="tab-content tab-content-query card">
          <div class="query-header" style="flex-shrink:0">
            <h3>SQL Query</h3>
            <span class="query-notice">Qualsiasi istruzione SQL è permessa</span>
          </div>

          <div class="query-quick" style="flex-shrink:0">
            <span class="ql-label">Query rapide:</span>
            <button v-for="q in quickQueries" :key="q.label" class="ql-btn" @click="applySqlTemplate(q.sql)">{{ q.label }}</button>
          </div>

          <!-- FIX: flex-shrink:0 impedisce il rimpicciolimento del textarea dopo l'esecuzione -->
          <textarea
            v-model="customSql"
            class="sql-input"
            placeholder="SELECT * FROM scouting_players WHERE position = 'ST' LIMIT 20"
            rows="8"
            spellcheck="false"
          ></textarea>

          <div class="query-controls" style="flex-shrink:0">
            <div>
              <label>Max righe: </label>
              <select v-model.number="queryLimit">
                <option :value="50">50</option>
                <option :value="100">100</option>
                <option :value="200">200</option>
                <option :value="500">500</option>
              </select>
            </div>
            <button class="btn-run" :disabled="!customSql.trim() || queryRunning" @click="runQuery">
              <span v-if="queryRunning">⏳ Esecuzione…</span>
              <span v-else>▶ Esegui Query</span>
            </button>
          </div>

          <div v-if="queryError" class="query-error" style="flex-shrink:0">❌ {{ queryError }}</div>

          <template v-if="queryResult">
            <div class="table-info" style="flex-shrink:0">
              {{ queryResult.rows?.length ?? 0 }} righe restituite
              <template v-if="queryResult.total != null"> ({{ queryResult.total }} totali)</template>
              <span v-if="queryResult.message" style="margin-left:0.5rem; color:var(--color-success, #10b981)">
                ✅ {{ queryResult.message }}
              </span>
            </div>
            <div class="browse-actions" style="flex-shrink:0">
              <button class="btn-open-dialog" @click="queryDialogVisible = true">🔍 Visualizza nella finestra</button>
              <button class="btn-export" @click="exportExcel">📊 Excel</button>
              <button class="btn-export" @click="exportCsv">📥 CSV</button>
            </div>
            <p class="dialog-hint-inline" style="flex-shrink:0">💡 Per una visione completa clicca "Visualizza nella finestra".</p>
          </template>
        </div>

      </main>
    </div>
  </div>

  <!-- ── Dialog: Sfoglia dati ───────────────────────────────────── -->
  <div v-if="browseDialogVisible" class="db-modal-overlay" @click.self="browseDialogVisible = false">
    <div class="db-modal">
      <div class="db-modal-header">
        <div class="db-modal-title">
          <span>📋</span>
          <h3>{{ selectedTable }}</h3>
          <span class="db-modal-meta">
            {{ tableData?.rows?.length }} di {{ formatCount(tableData?.total) }} righe · Pagina {{ currentPage }}/{{ totalPages }}
          </span>
        </div>
        <div class="db-modal-actions">
          <select v-model.number="pageSize" @change="loadData" class="db-modal-select">
            <option :value="20">20 righe</option>
            <option :value="50">50 righe</option>
            <option :value="100">100 righe</option>
            <option :value="200">200 righe</option>
          </select>
          <button class="btn-page" :disabled="currentOffset === 0" @click="changePage(-1)">← Prec.</button>
          <button class="btn-page" :disabled="currentOffset + pageSize >= (tableData?.total ?? 0)" @click="changePage(1)">Succ. →</button>
          <button class="btn-reload" :disabled="loadingData" @click="reloadData" title="Ricarica dati dal DB">
            <span :class="{ spin: loadingData }">↻</span> Ricarica
          </button>
          <button class="btn-export" @click="exportBrowseExcel" title="Esporta Excel">📊 Excel</button>
          <button class="btn-export" @click="exportBrowseCsv" title="Esporta CSV">📥 CSV</button>
          <button class="db-modal-close" @click="browseDialogVisible = false">✕</button>
        </div>
      </div>
      <div v-if="loadingData" class="db-modal-loading">Caricamento…</div>
      <div v-else-if="tableData" class="db-modal-body">
        <table class="data-table">
          <thead>
            <tr><th v-for="col in tableData.columns" :key="col" :title="col">{{ col }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in tableData.rows" :key="i">
              <td v-for="col in tableData.columns" :key="col">
                <span :class="{ 'null-val': row[col] === null || row[col] === undefined }">
                  {{ formatCell(row[col]) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ── Dialog: Query results ──────────────────────────────────── -->
  <div v-if="queryDialogVisible" class="db-modal-overlay" @click.self="queryDialogVisible = false">
    <div class="db-modal">
      <div class="db-modal-header">
        <div class="db-modal-title">
          <span>💬</span>
          <h3>Risultati Query</h3>
          <span class="db-modal-meta">
            {{ queryResult?.rows?.length }} righe
            <template v-if="queryResult?.total != null"> · {{ queryResult.total }} totali</template>
          </span>
        </div>
        <div class="db-modal-actions">
          <button class="btn-export" @click="exportExcel">📊 Excel</button>
          <button class="btn-export" @click="exportCsv">📥 CSV</button>
          <button class="db-modal-close" @click="queryDialogVisible = false">✕</button>
        </div>
      </div>
      <div v-if="queryResult && queryResult.columns && queryResult.columns.length" class="db-modal-body">
        <table class="data-table">
          <thead>
            <tr><th v-for="col in queryResult.columns" :key="col">{{ col }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in queryResult.rows" :key="i">
              <td v-for="col in queryResult.columns" :key="col">
                <span :class="{ 'null-val': row[col] === null || row[col] === undefined }">
                  {{ formatCell(row[col]) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="db-modal-loading">
        {{ queryResult?.message || 'Nessuna riga da mostrare.' }}
      </div>
    </div>
  </div>

</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/api/client'

// ── Stato ─────────────────────────────────────────────────────────
const tables        = ref([])
const loadingTables = ref(false)
const selectedTable = ref(null)
const activeTab     = ref('browse')

const tableData     = ref(null)
const loadingData   = ref(false)
const pageSize      = ref(50)
const currentOffset = ref(0)
const currentPage   = computed(() => Math.floor(currentOffset.value / pageSize.value) + 1)
const totalPages    = computed(() =>
  tableData.value ? Math.ceil(tableData.value.total / pageSize.value) : 1
)

const tableSchema   = ref(null)
const loadingSchema = ref(false)

const customSql     = ref('')
const queryLimit    = ref(100)
const queryRunning  = ref(false)
const queryResult   = ref(null)
const queryError    = ref(null)

const browseDialogVisible = ref(false)
const queryDialogVisible  = ref(false)

// ── Quick queries aggiornate ─────────────────────────────────────
const quickQueries = [
  { label: 'Top xG/90',         sql: "SELECT name, position, club, xg_per90, xa_per90, npxg_per90, finishing_score, finishing_pct FROM scouting_players WHERE xg_per90 IS NOT NULL ORDER BY xg_per90 DESC LIMIT 20" },
  { label: 'Score per ruolo',   sql: "SELECT position, COUNT(*) as n, ROUND(AVG(finishing_score)::numeric,1) avg_fin, ROUND(AVG(creativity_score)::numeric,1) avg_cre, ROUND(AVG(pressing_score)::numeric,1) avg_prs FROM scouting_players WHERE finishing_score IS NOT NULL GROUP BY position ORDER BY n DESC" },
  { label: 'Colonne NULL',      sql: "SELECT COUNT(*) totale, COUNT(minutes_season) con_minuti, COUNT(xg_per90) con_xg, COUNT(pressures_season) con_pressures, COUNT(tackles_season) con_tackles, COUNT(progressive_carries) con_prog_carries FROM scouting_players" },
  { label: 'Posizioni raw',     sql: "SELECT position, COUNT(*) AS n FROM scouting_players GROUP BY position ORDER BY n DESC" },
  { label: 'Top percentili',    sql: "SELECT name, position, club, finishing_pct, creativity_pct, pressing_pct, defending_pct FROM scouting_players WHERE finishing_pct > 70 ORDER BY finishing_pct DESC LIMIT 30" },
  { label: 'Sorgenti attive',   sql: "SELECT COUNT(*) totale, COUNT(last_updated_fbref) fbref, COUNT(last_updated_api_football) api_football, COUNT(last_updated_understat) understat, COUNT(last_updated_statsbomb) statsbomb FROM scouting_players" },
]

function applySqlTemplate(sql) {
  customSql.value = sql
  activeTab.value = 'query'
}

// ── Tabelle ────────────────────────────────────────────────────────
async function loadTables() {
  loadingTables.value = true
  try {
    const { data } = await api.get('/db/tables')
    tables.value = data
  } finally {
    loadingTables.value = false
  }
}

function selectTable(name) {
  selectedTable.value = name
  tableData.value = null
  tableSchema.value = null
  currentOffset.value = 0
  if (activeTab.value === 'browse') loadData()
  else if (activeTab.value === 'schema') loadSchema()
}

// ── Sfoglia dati ─────────────────────────────────────────────────
async function loadData() {
  if (!selectedTable.value) return
  loadingData.value = true
  try {
    const { data } = await api.get(`/db/tables/${selectedTable.value}/data`, {
      params: { limit: pageSize.value, offset: currentOffset.value },
    })
    tableData.value = {
      ...data,
      columns: data.rows.length ? Object.keys(data.rows[0]) : [],
    }
    browseDialogVisible.value = true
  } finally {
    loadingData.value = false
  }
}

function changePage(direction) {
  currentOffset.value = Math.max(0, currentOffset.value + direction * pageSize.value)
  loadData()
}

function reloadData() {
  currentOffset.value = 0
  tableData.value = null
  loadData()
}

// ── Schema ────────────────────────────────────────────────────────
async function loadSchema() {
  if (!selectedTable.value) return
  loadingSchema.value = true
  try {
    const { data } = await api.get(`/db/tables/${selectedTable.value}`)
    tableSchema.value = data
  } finally {
    loadingSchema.value = false
  }
}

// ── SQL Query ─────────────────────────────────────────────────────
async function runQuery() {
  queryRunning.value = true
  queryError.value   = null
  queryResult.value  = null
  try {
    const { data } = await api.post('/db/query', {
      sql:   customSql.value,
      limit: queryLimit.value,
    })

    // Normalizza: aggiunge columns se mancante
    if (data.rows && data.rows.length && !data.columns) {
      data.columns = Object.keys(data.rows[0])
    } else if (!data.columns) {
      data.columns = []
    }

    queryResult.value = data
    if (data.rows && data.rows.length > 0) {
      queryDialogVisible.value = true
    }
  } catch (e) {
    queryError.value = e.response?.data?.detail || e.message
  } finally {
    queryRunning.value = false
  }
}

// ── Export ────────────────────────────────────────────────────────
function _toCsv(columns, rows) {
  const esc = v => {
    if (v == null) return ''
    const s = String(v)
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [
    columns.map(esc).join(','),
    ...rows.map(r => columns.map(c => esc(r[c])).join(','))
  ].join('\n')
}

function _download(content, filename, type = 'text/csv;charset=utf-8;') {
  const blob = new Blob(['\uFEFF' + content], { type })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

function exportCsv() {
  if (!queryResult.value?.columns?.length) return
  _download(_toCsv(queryResult.value.columns, queryResult.value.rows), 'query_result.csv')
}

function exportBrowseCsv() {
  if (!tableData.value?.columns?.length) return
  _download(_toCsv(tableData.value.columns, tableData.value.rows), `${selectedTable.value}.csv`)
}

async function _exportXlsx(columns, rows, filename) {
  try {
    const XLSX = await import('https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.mjs')
    const ws = XLSX.utils.json_to_sheet(rows.map(r => {
      const obj = {}
      columns.forEach(c => { obj[c] = r[c] ?? null })
      return obj
    }))
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Dati')
    XLSX.writeFile(wb, filename)
  } catch {
    _download(_toCsv(columns, rows), filename.replace('.xlsx', '.csv'))
  }
}

function exportExcel() {
  if (!queryResult.value?.columns?.length) return
  _exportXlsx(queryResult.value.columns, queryResult.value.rows, 'query_result.xlsx')
}

function exportBrowseExcel() {
  if (!tableData.value?.columns?.length) return
  _exportXlsx(tableData.value.columns, tableData.value.rows, `${selectedTable.value || 'tabella'}.xlsx`)
}

// ── Formatters ────────────────────────────────────────────────────
function formatCell(val) {
  if (val === null || val === undefined) return 'NULL'
  if (typeof val === 'number') return Number.isInteger(val) ? val : val.toFixed(3)
  if (typeof val === 'string' && val.length > 60) return val.slice(0, 60) + '…'
  return val
}

function formatCount(n) {
  if (n == null) return '?'
  return n.toLocaleString('it-IT')
}

// ── Watchers + mount ──────────────────────────────────────────────
watch(activeTab, (tab) => {
  if (!selectedTable.value) return
  if (tab === 'browse' && !tableData.value) loadData()
  if (tab === 'schema' && !tableSchema.value) loadSchema()
})

watch(selectedTable, () => {
  tableData.value = null
  tableSchema.value = null
  currentOffset.value = 0
  if (activeTab.value === 'browse') loadData()
  if (activeTab.value === 'schema') loadSchema()
})

onMounted(loadTables)
</script>

<style scoped>
.db-explorer {
  padding: 1.5rem 2rem;
  max-width: 1400px;
  margin: 0 auto;
  height: 100%;
  max-height: calc(100dvh - 64px);
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow: hidden;
}

.page-header { margin-bottom: 1.25rem; flex-shrink: 0; }
.page-header h1 { font-size: 1.6rem; font-weight: 700; margin: 0; }
.subtitle { color: var(--text-muted, #888); margin-top: 0.3rem; }

.card {
  background: var(--surface, #fff);
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 12px;
  padding: 1rem 1.25rem;
}

.explorer-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 1rem;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.sidebar {
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

.sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.sidebar-header h3 { margin: 0; font-size: 0.95rem; }
.btn-refresh { background: none; border: none; font-size: 1.1rem; cursor: pointer; color: var(--text-muted, #888); }
.spin { display: inline-block; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.table-list { list-style: none; margin: 0; padding: 0; }
.table-item { display: flex; justify-content: space-between; align-items: center; padding: 0.4rem 0.6rem; border-radius: 6px; cursor: pointer; font-size: 0.85rem; transition: background 0.15s; }
.table-item:hover { background: var(--bg, #f3f4f6); }
.table-item.active { background: #eff6ff; color: #1d4ed8; font-weight: 600; }
.row-count { font-size: 0.7rem; color: var(--text-muted, #aaa); background: var(--bg, #f3f4f6); padding: 0.1rem 0.4rem; border-radius: 10px; }

.main-content { display: flex; flex-direction: column; gap: 1rem; overflow: hidden; min-height: 0; height: 100%; }

.tab-bar { display: flex; gap: 0.5rem; padding: 0.5rem 0.75rem; flex-shrink: 0; }
.tab-btn { padding: 0.35rem 1rem; border: 1px solid var(--border, #e5e7eb); background: var(--bg, #f9fafb); border-radius: 6px; cursor: pointer; font-size: 0.875rem; transition: background 0.15s; }
.tab-btn:hover { background: #eff6ff; }
.tab-btn.active { background: var(--primary, #3b82f6); color: #fff; border-color: var(--primary, #3b82f6); }

/* Tab content base */
.tab-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 0;
}

/* FIX #6: Schema tab — il contenuto scrolla senza restringere il contenitore */
.tab-content-scroll {
  overflow-y: auto !important;
}

/* FIX #3/#5: Query tab — il textarea NON si rimpicciolisce dopo l'esecuzione */
.tab-content-query {
  overflow-y: auto;
}

/* Il textarea ha altezza minima garantita e non si restringe */
.sql-input {
  width: 100%;
  min-height: 160px;        /* FIX: altezza minima garantita */
  flex-shrink: 0;           /* FIX: non si restringe nel flex container */
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 0.85rem;
  line-height: 1.5;
  resize: vertical;         /* l'utente può ridimensionare manualmente */
  background: #1e1e2e;
  color: #cdd6f4;
  box-sizing: border-box;
}

/* FIX #6: schema scroll wrapper — prende tutto lo spazio disponibile e scrolla */
.schema-scroll {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.empty-state { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-muted, #aaa); font-size: 0.95rem; }
.loading { color: var(--text-muted, #888); font-size: 0.9rem; }

.browse-header { display: flex; justify-content: space-between; align-items: center; }
.browse-header h3 { margin: 0; }
.browse-controls { display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; }
.browse-controls select { padding: 0.25rem 0.5rem; border-radius: 4px; border: 1px solid var(--border, #e5e7eb); }

.table-info { font-size: 0.8rem; color: var(--text-muted, #888); }

.table-scroll { overflow: auto; flex: 1; min-height: 0; }

.data-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.data-table th { position: sticky; top: 0; background: var(--surface, #fff); padding: 0.5rem 0.6rem; text-align: left; border-bottom: 2px solid var(--border, #e5e7eb); font-weight: 600; white-space: nowrap; color: var(--text-muted, #666); font-size: 0.75rem; text-transform: uppercase; }
.data-table td { padding: 0.35rem 0.6rem; border-bottom: 1px solid var(--border, #f3f4f6); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.data-table tr:hover td { background: rgba(255,255,255,.04); }
.null-val { color: #ccc; font-style: italic; }

.btn-page { padding: 0.35rem 0.9rem; border: 1px solid var(--border, #e5e7eb); background: var(--bg, #f9fafb); border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
.btn-page:disabled { opacity: 0.4; cursor: not-allowed; }

/* Schema */
.schema-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 1rem; }
.schema-table th { position: sticky; top: 0; background: var(--surface, #fff); text-align: left; padding: 0.45rem 0.6rem; border-bottom: 2px solid var(--border, #e5e7eb); font-weight: 600; color: var(--text-muted, #666); font-size: 0.75rem; text-transform: uppercase; z-index: 1; }
.schema-table td { padding: 0.35rem 0.6rem; border-bottom: 1px solid var(--border, #f3f4f6); }
.col-idx { color: var(--text-muted, #aaa); font-size: 0.72rem; width: 2rem; }
.pk-row td { background: rgba(251, 191, 36, 0.08); }
.yes { color: #10b981; } .no { color: #6b7280; }
.indexes h4 { margin: 0.75rem 0 0.5rem; font-size: 0.9rem; }

/* Query */
.query-header { display: flex; justify-content: space-between; align-items: center; }
.query-header h3 { margin: 0; }
.query-notice { font-size: 0.75rem; background: #fef3c7; color: #92400e; padding: 0.2rem 0.6rem; border-radius: 4px; }

.query-quick { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; }
.ql-label { font-size: 0.75rem; color: var(--text-muted, #888); font-weight: 600; }
.ql-btn { padding: 0.2rem 0.6rem; border: 1px solid var(--border, #e5e7eb); background: var(--bg, #f9fafb); border-radius: 20px; cursor: pointer; font-size: 0.75rem; transition: background 0.15s; }
.ql-btn:hover { background: #eff6ff; border-color: #93c5fd; }

.query-controls { display: flex; justify-content: space-between; align-items: center; gap: 1rem; font-size: 0.85rem; }
.query-controls select { padding: 0.3rem 0.5rem; border-radius: 4px; border: 1px solid var(--border, #e5e7eb); }

.btn-run { padding: 0.5rem 1.5rem; background: var(--primary, #3b82f6); color: #fff; border: none; border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer; }
.btn-run:disabled { opacity: 0.5; cursor: not-allowed; }

.query-error { background: #fee2e2; color: #991b1b; padding: 0.6rem 0.9rem; border-radius: 6px; font-size: 0.85rem; font-family: monospace; }

.browse-actions { display: flex; gap: 0.6rem; align-items: center; }
.btn-open-dialog { padding: 0.4rem 1rem; background: var(--primary, #3b82f6); color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 600; }
.btn-open-dialog:hover { background: #1d4ed8; }
.btn-export { padding: 0.35rem 0.9rem; border: 1px solid var(--border, #e5e7eb); background: var(--bg, #f9fafb); border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
.btn-export:hover { background: #f0fdf4; border-color: #86efac; }

.dialog-hint-inline { font-size: 0.75rem; color: var(--text-muted, #9ca3af); margin: 0; }

/* Modal */
.db-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); display: flex; align-items: center; justify-content: center; z-index: 1100; padding: 1rem; }
.db-modal { background: var(--surface, #fff); border-radius: 14px; width: min(1200px, 96vw); height: min(90vh, 860px); display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
.db-modal-header { display: flex; justify-content: space-between; align-items: center; padding: 0.85rem 1.25rem; border-bottom: 1px solid var(--border, #e5e7eb); flex-shrink: 0; gap: 1rem; }
.db-modal-title { display: flex; align-items: center; gap: 0.6rem; }
.db-modal-title h3 { margin: 0; font-size: 1rem; }
.db-modal-meta { font-size: 0.78rem; color: var(--text-muted, #9ca3af); background: var(--bg, #f3f4f6); padding: 0.15rem 0.6rem; border-radius: 20px; }
.db-modal-actions { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; }
.db-modal-select { padding: 0.3rem 0.5rem; border: 1px solid var(--border, #e5e7eb); border-radius: 6px; font-size: 0.82rem; }
.db-modal-close { background: none; border: none; font-size: 1.2rem; cursor: pointer; color: var(--text-muted, #6b7280); line-height: 1; padding: 0.2rem; }
.db-modal-close:hover { color: #fff; }
.btn-reload { display: flex; align-items: center; gap: 0.3rem; padding: 0.3rem 0.75rem; border: 1px solid var(--border, #e5e7eb); background: var(--bg, #f9fafb); border-radius: 6px; cursor: pointer; font-size: 0.8rem; font-weight: 600; color: var(--primary, #3b82f6); }
.btn-reload:hover:not(:disabled) { background: #eff6ff; border-color: #93c5fd; }
.btn-reload:disabled { opacity: 0.5; cursor: not-allowed; }
.db-modal-loading { padding: 2rem; text-align: center; color: var(--text-muted, #888); }
.db-modal-body { flex: 1; overflow: auto; padding: 0; }
</style>