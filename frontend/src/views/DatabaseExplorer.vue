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
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'browse' }"
            @click="activeTab = 'browse'"
          >
            📋 Sfoglia dati
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'schema' }"
            @click="activeTab = 'schema'"
          >
            🏗 Schema
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'query' }"
            @click="activeTab = 'query'"
          >
            💬 SQL Query
          </button>
        </div>

        <!-- ── TAB: Sfoglia ───────────────────────────────────── -->
        <div v-if="activeTab === 'browse'" class="tab-content card">
          <div v-if="!selectedTable" class="empty-state">
            ← Seleziona una tabella dalla sidebar
          </div>

          <template v-else>
            <div class="browse-header">
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
              <div class="table-info">
                Mostrando {{ tableData.rows.length }} di {{ formatCount(tableData.total) }} righe
                (offset {{ currentOffset }})
              </div>

              <div class="table-scroll">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th v-for="col in tableData.columns" :key="col" :title="col">
                        {{ col }}
                      </th>
                    </tr>
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

              <div class="pagination">
                <button
                  class="btn-page"
                  :disabled="currentOffset === 0"
                  @click="changePage(-1)"
                >← Precedente</button>
                <span class="page-info">
                  Pagina {{ currentPage }} / {{ totalPages }}
                </span>
                <button
                  class="btn-page"
                  :disabled="currentOffset + pageSize >= tableData.total"
                  @click="changePage(1)"
                >Successiva →</button>
              </div>
            </template>
          </template>
        </div>

        <!-- ── TAB: Schema ────────────────────────────────────── -->
        <div v-if="activeTab === 'schema'" class="tab-content card">
          <div v-if="!selectedTable" class="empty-state">
            ← Seleziona una tabella dalla sidebar
          </div>

          <template v-else>
            <div v-if="loadingSchema" class="loading">Caricamento schema…</div>
            <template v-else-if="tableSchema">
              <h3>Schema: {{ tableSchema.table }}</h3>

              <table class="schema-table">
                <thead>
                  <tr>
                    <th>Colonna</th>
                    <th>Tipo</th>
                    <th>Nullable</th>
                    <th>Default</th>
                    <th>PK</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="col in tableSchema.columns"
                    :key="col.name"
                    :class="{ 'pk-row': col.primary_key }"
                  >
                    <td>
                      <span v-if="col.primary_key">🔑 </span>
                      {{ col.name }}
                    </td>
                    <td><code>{{ col.type }}</code></td>
                    <td>
                      <span :class="col.nullable ? 'yes' : 'no'">
                        {{ col.nullable ? 'Sì' : 'No' }}
                      </span>
                    </td>
                    <td><code v-if="col.default">{{ col.default }}</code><span v-else>—</span></td>
                    <td>{{ col.primary_key ? '✓' : '' }}</td>
                  </tr>
                </tbody>
              </table>

              <div v-if="tableSchema.indexes.length" class="indexes">
                <h4>Indici</h4>
                <table class="schema-table">
                  <thead>
                    <tr><th>Nome</th><th>Colonne</th><th>Unique</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="idx in tableSchema.indexes" :key="idx.name">
                      <td>{{ idx.name }}</td>
                      <td>{{ idx.columns.join(', ') }}</td>
                      <td>{{ idx.unique ? '✓' : '' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
          </template>
        </div>

        <!-- ── TAB: SQL Query ─────────────────────────────────── -->
        <div v-if="activeTab === 'query'" class="tab-content card">
          <div class="query-header">
            <h3>SQL Query</h3>
            <span class="query-notice">Solo SELECT e WITH…SELECT sono permessi</span>
          </div>

          <div class="query-quick">
            <span class="ql-label">Query rapide:</span>
            <button
              v-for="q in quickQueries"
              :key="q.label"
              class="ql-btn"
              @click="applySqlTemplate(q.sql)"
            >
              {{ q.label }}
            </button>
          </div>

          <textarea
            v-model="customSql"
            class="sql-input"
            placeholder="SELECT * FROM scouting_players WHERE position = 'ST' LIMIT 20"
            rows="6"
            spellcheck="false"
          ></textarea>

          <div class="query-controls">
            <div>
              <label>Max righe: </label>
              <select v-model.number="queryLimit">
                <option :value="50">50</option>
                <option :value="100">100</option>
                <option :value="200">200</option>
                <option :value="500">500</option>
              </select>
            </div>
            <button
              class="btn-run"
              :disabled="!customSql.trim() || queryRunning"
              @click="runQuery"
            >
              <span v-if="queryRunning">⏳ Esecuzione…</span>
              <span v-else>▶ Esegui Query</span>
            </button>
          </div>

          <div v-if="queryError" class="query-error">
            ❌ {{ queryError }}
          </div>

          <template v-if="queryResult">
            <div class="table-info">
              {{ queryResult.showing }} righe restituite
              ({{ queryResult.total }} totali nell'insieme completo)
            </div>

            <div class="table-scroll">
              <table class="data-table">
                <thead>
                  <tr>
                    <th v-for="col in queryResult.columns" :key="col">{{ col }}</th>
                  </tr>
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

            <div class="export-bar">
              <button class="btn-export" @click="exportCsv">📥 Esporta CSV</button>
            </div>
          </template>
        </div>

      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
//import api from '@/services/api'
import api from '@/api/client'

// ── Stato ─────────────────────────────────────────────────────────
const tables       = ref([])
const loadingTables = ref(false)
const selectedTable = ref(null)
const activeTab     = ref('browse')

// Browse
const tableData    = ref(null)
const loadingData  = ref(false)
const pageSize     = ref(50)
const currentOffset = ref(0)
const currentPage  = computed(() => Math.floor(currentOffset.value / pageSize.value) + 1)
const totalPages   = computed(() =>
  tableData.value ? Math.ceil(tableData.value.total / pageSize.value) : 1
)

// Schema
const tableSchema  = ref(null)
const loadingSchema = ref(false)

// Query
const customSql    = ref('')
const queryLimit   = ref(100)
const queryRunning = ref(false)
const queryResult  = ref(null)
const queryError   = ref(null)

// ── Quick queries ─────────────────────────────────────────────────
const quickQueries = [
  { label: 'Top scorer xG', sql: "SELECT name, position, club, xg_per90, xa_per90 FROM scouting_players WHERE xg_per90 IS NOT NULL ORDER BY xg_per90 DESC LIMIT 20" },
  { label: 'Difensori Serie A', sql: "SELECT name, age, club, defending, physical FROM scouting_players WHERE position IN ('CB','LB','RB') AND nationality LIKE '%Italian%' LIMIT 50" },
  { label: 'Conteggio per posizione', sql: "SELECT position, COUNT(*) AS totale FROM scouting_players GROUP BY position ORDER BY totale DESC" },
  { label: 'Distribuzione nazionalità', sql: "SELECT nationality, COUNT(*) AS n FROM scouting_players GROUP BY nationality ORDER BY n DESC LIMIT 20" },
  { label: 'Giocatori senza xG', sql: "SELECT COUNT(*) AS senza_xg, COUNT(xg_per90) AS con_xg FROM scouting_players" },
  { label: 'Ultime squadre', sql: "SELECT DISTINCT club FROM scouting_players WHERE club IS NOT NULL ORDER BY club" },
]

function applySqlTemplate(sql) {
  customSql.value = sql
  activeTab.value = 'query'
}

// ── Carica lista tabelle ──────────────────────────────────────────
async function loadTables() {
  loadingTables.value = true
  try {
    const { data } = await api.get('/db/tables')
    tables.value = data
  } finally {
    loadingTables.value = false
  }
}

// ── Seleziona tabella ─────────────────────────────────────────────
function selectTable(name) {
  selectedTable.value = name
  tableData.value = null
  tableSchema.value = null
  currentOffset.value = 0
  if (activeTab.value === 'browse') loadData()
  else if (activeTab.value === 'schema') loadSchema()
}

// ── Cambio tab → carica i dati necessari ─────────────────────────
function onTabChange(tab) {
  activeTab.value = tab
  if (!selectedTable.value) return
  if (tab === 'browse' && !tableData.value) loadData()
  if (tab === 'schema' && !tableSchema.value) loadSchema()
}

// ── Sfoglia dati ─────────────────────────────────────────────────
async function loadData() {
  if (!selectedTable.value) return
  loadingData.value = true
  try {
    const { data } = await api.get(`/db/tables/${selectedTable.value}/data`, {
      params: { limit: pageSize.value, offset: currentOffset.value },
    })
    // Estrai colonne dai dati
    tableData.value = {
      ...data,
      columns: data.rows.length ? Object.keys(data.rows[0]) : [],
    }
  } finally {
    loadingData.value = false
  }
}

function changePage(direction) {
  currentOffset.value = Math.max(0, currentOffset.value + direction * pageSize.value)
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
  queryError.value = null
  queryResult.value = null
  try {
    const { data } = await api.post('/db/query', {
      sql: customSql.value,
      limit: queryLimit.value,
    })
    queryResult.value = data
  } catch (e) {
    queryError.value = e.response?.data?.detail || e.message
  } finally {
    queryRunning.value = false
  }
}

// ── Esporta CSV ───────────────────────────────────────────────────
function exportCsv() {
  if (!queryResult.value) return
  const cols = queryResult.value.columns
  const rows = queryResult.value.rows
  const lines = [
    cols.join(','),
    ...rows.map(r => cols.map(c => JSON.stringify(r[c] ?? '')).join(','))
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'query_result.csv'
  a.click()
}

// ── Formatters ────────────────────────────────────────────────────
function formatCell(val) {
  if (val === null || val === undefined) return 'NULL'
  if (typeof val === 'number') {
    return Number.isInteger(val) ? val : val.toFixed(3)
  }
  if (typeof val === 'string' && val.length > 60) return val.slice(0, 60) + '…'
  return val
}

function formatCount(n) {
  if (n == null) return '?'
  return n.toLocaleString('it-IT')
}

// ── Montaggio ─────────────────────────────────────────────────────
onMounted(loadTables)

// Reagisce ai cambi tab con caricamento lazy
import { watch } from 'vue'
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
</script>

<style scoped>
.db-explorer {
  padding: 1.5rem 2rem;
  max-width: 1400px;
  margin: 0 auto;
  height: calc(100vh - 4rem);
  display: flex;
  flex-direction: column;
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

/* Layout */
.explorer-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 1rem;
  flex: 1;
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}
.sidebar-header h3 { margin: 0; font-size: 0.95rem; }
.btn-refresh {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: var(--text-muted, #888);
}
.spin { display: inline-block; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.table-list { list-style: none; margin: 0; padding: 0; }
.table-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.15s;
}
.table-item:hover { background: var(--bg, #f3f4f6); }
.table-item.active {
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}
.row-count {
  font-size: 0.7rem;
  color: var(--text-muted, #aaa);
  background: var(--bg, #f3f4f6);
  padding: 0.1rem 0.4rem;
  border-radius: 10px;
}

/* Main */
.main-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow: hidden;
}

/* Tabs */
.tab-bar {
  display: flex;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  flex-shrink: 0;
}
.tab-btn {
  padding: 0.35rem 1rem;
  border: 1px solid var(--border, #e5e7eb);
  background: var(--bg, #f9fafb);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.15s;
}
.tab-btn:hover { background: #eff6ff; }
.tab-btn.active {
  background: var(--primary, #3b82f6);
  color: #fff;
  border-color: var(--primary, #3b82f6);
}

/* Tab content */
.tab-content {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted, #aaa);
  font-size: 0.95rem;
}

.loading { color: var(--text-muted, #888); font-size: 0.9rem; }

/* Browse */
.browse-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.browse-header h3 { margin: 0; }
.browse-controls { display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; }
.browse-controls select { padding: 0.25rem 0.5rem; border-radius: 4px; border: 1px solid var(--border, #e5e7eb); }

.table-info {
  font-size: 0.8rem;
  color: var(--text-muted, #888);
}

.table-scroll { overflow: auto; flex: 1; }

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}
.data-table th {
  position: sticky;
  top: 0;
  background: var(--surface, #fff);
  padding: 0.5rem 0.6rem;
  text-align: left;
  border-bottom: 2px solid var(--border, #e5e7eb);
  font-weight: 600;
  white-space: nowrap;
  color: var(--text-muted, #666);
  font-size: 0.75rem;
  text-transform: uppercase;
}
.data-table td {
  padding: 0.35rem 0.6rem;
  border-bottom: 1px solid var(--border, #f3f4f6);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.data-table tr:hover td { background: #f9fafb; }
.null-val { color: #ccc; font-style: italic; }

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  padding-top: 0.5rem;
}
.btn-page {
  padding: 0.35rem 0.9rem;
  border: 1px solid var(--border, #e5e7eb);
  background: var(--bg, #f9fafb);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}
.btn-page:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 0.85rem; color: var(--text-muted, #888); }

/* Schema */
.schema-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  margin-bottom: 1rem;
}
.schema-table th {
  text-align: left;
  padding: 0.45rem 0.6rem;
  border-bottom: 2px solid var(--border, #e5e7eb);
  font-weight: 600;
  color: var(--text-muted, #666);
  font-size: 0.75rem;
  text-transform: uppercase;
}
.schema-table td { padding: 0.35rem 0.6rem; border-bottom: 1px solid var(--border, #f3f4f6); }
.pk-row td { background: #fffbeb; }
.yes { color: #10b981; } .no { color: #6b7280; }
.indexes h4 { margin: 0.75rem 0 0.5rem; font-size: 0.9rem; }

/* Query */
.query-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.query-header h3 { margin: 0; }
.query-notice {
  font-size: 0.75rem;
  background: #fef3c7;
  color: #92400e;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
}

.query-quick {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}
.ql-label { font-size: 0.75rem; color: var(--text-muted, #888); font-weight: 600; }
.ql-btn {
  padding: 0.2rem 0.6rem;
  border: 1px solid var(--border, #e5e7eb);
  background: var(--bg, #f9fafb);
  border-radius: 20px;
  cursor: pointer;
  font-size: 0.75rem;
  transition: background 0.15s;
}
.ql-btn:hover { background: #eff6ff; border-color: #93c5fd; }

.sql-input {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 0.85rem;
  line-height: 1.5;
  resize: vertical;
  background: #1e1e2e;
  color: #cdd6f4;
  box-sizing: border-box;
}

.query-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  font-size: 0.85rem;
}
.query-controls select { padding: 0.3rem 0.5rem; border-radius: 4px; border: 1px solid var(--border, #e5e7eb); }

.btn-run {
  padding: 0.5rem 1.5rem;
  background: var(--primary, #3b82f6);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
}
.btn-run:disabled { opacity: 0.5; cursor: not-allowed; }

.query-error {
  background: #fee2e2;
  color: #991b1b;
  padding: 0.6rem 0.9rem;
  border-radius: 6px;
  font-size: 0.85rem;
  font-family: monospace;
}

.export-bar { display: flex; justify-content: flex-end; }
.btn-export {
  padding: 0.35rem 0.9rem;
  border: 1px solid var(--border, #e5e7eb);
  background: var(--bg, #f9fafb);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}
</style>