<template>
  <div id="app-shell">

    <!-- ── Sidebar ──────────────────────────────────────────── -->
    <aside class="sidebar">
      <div class="logo">
        <span class="logo-icon">⚽</span>
        <span class="logo-text">Football Scout</span>
      </div>

      <nav class="nav">
        <RouterLink to="/"          class="nav-item"><span>🏠</span> Dashboard</RouterLink>
        <RouterLink to="/traits"    class="nav-item"><span>📋</span> Caratteristiche</RouterLink>
        <RouterLink to="/roster"    class="nav-item"><span>👥</span> Rosa</RouterLink>
        <RouterLink to="/scouting"  class="nav-item"><span>🔍</span> Scouting</RouterLink>
        <router-link to="/data-ingestion" class="nav-item">
          <span>🔄</span> Gestione Dati
        </router-link>
        <router-link to="/db-explorer" class="nav-item">
          <span>🗄️</span> Database Explorer
        </router-link>
      </nav>

      <!-- Squadra attiva -->
      <div v-if="teamStore.activeTeam" class="active-team">
        <p class="active-label">Squadra attiva</p>
        <p class="active-name">{{ teamStore.activeTeam.name }}</p>
        <p class="active-sub">{{ teamStore.activeTeam.formation }} · {{ teamStore.activeTeam.season }}</p>
      </div>
    </aside>

    <!-- ── Main ─────────────────────────────────────────────── -->
    <main class="main-content">
      <RouterView />
    </main>

  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useTeamStore } from '@/stores/teamStore'

const teamStore = useTeamStore()
onMounted(() => teamStore.fetchTeams())
</script>

<style>
/* ── Reset & variabili ─────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --color-bg:        #0f172a;
  --color-surface:   #1e293b;
  --color-border:    #334155;
  --color-primary:   #3b82f6;
  --color-primary-h: #2563eb;
  --color-success:   #22c55e;
  --color-danger:    #ef4444;
  --color-warning:   #f59e0b;
  --color-text:      #f1f5f9;
  --color-muted:     #94a3b8;
  --radius:          10px;
  --shadow:          0 4px 20px rgba(0,0,0,.4);
  font-family: 'Segoe UI', system-ui, sans-serif;
}

body { background: var(--color-bg); color: var(--color-text); }

/* ── Layout ────────────────────────────────────────────────────── */
#app-shell {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 240px;
  flex-shrink: 0;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  padding: 1.5rem 1rem;
  gap: 2rem;
  position: sticky;
  top: 0;
  height: 100vh;
}

.logo { display: flex; align-items: center; gap: .6rem; }
.logo-icon { font-size: 1.8rem; }
.logo-text { font-size: 1.1rem; font-weight: 700; color: var(--color-primary); }

.nav { display: flex; flex-direction: column; gap: .25rem; }
.nav-item {
  display: flex;
  align-items: center;
  gap: .6rem;
  padding: .65rem .9rem;
  border-radius: var(--radius);
  color: var(--color-muted);
  text-decoration: none;
  font-size: .92rem;
  transition: background .15s, color .15s;
}
.nav-item:hover,
.nav-item.router-link-active {
  background: rgba(59,130,246,.15);
  color: var(--color-primary);
}

.active-team {
  margin-top: auto;
  background: rgba(59,130,246,.08);
  border: 1px solid rgba(59,130,246,.25);
  border-radius: var(--radius);
  padding: .9rem 1rem;
}
.active-label { font-size: .72rem; text-transform: uppercase; color: var(--color-muted); letter-spacing: .06em; }
.active-name  { font-weight: 700; font-size: 1rem; margin-top: .2rem; }
.active-sub   { font-size: .78rem; color: var(--color-muted); margin-top: .15rem; }

.main-content {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
}

/* ── Utility classes ────────────────────────────────────────────── */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1.5rem;
  box-shadow: var(--shadow);
}
.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 1.5rem;
}
.btn {
  display: inline-flex;
  align-items: center;
  gap: .4rem;
  padding: .55rem 1.2rem;
  border-radius: var(--radius);
  border: none;
  cursor: pointer;
  font-size: .9rem;
  font-weight: 600;
  transition: opacity .15s, transform .1s;
}
.btn:hover { opacity: .88; transform: translateY(-1px); }
.btn-primary  { background: var(--color-primary);  color: #fff; }
.btn-danger   { background: var(--color-danger);   color: #fff; }
.btn-ghost    { background: transparent; border: 1px solid var(--color-border); color: var(--color-text); }

input, select, textarea {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text);
  padding: .6rem .9rem;
  font-size: .9rem;
  width: 100%;
  outline: none;
  transition: border-color .15s;
}
input:focus, select:focus, textarea:focus {
  border-color: var(--color-primary);
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: .3rem;
  padding: .25rem .7rem;
  border-radius: 20px;
  font-size: .78rem;
  font-weight: 600;
}
.badge-positive { background: rgba(34,197,94,.15);  color: var(--color-success); }
.badge-negative { background: rgba(239,68,68,.15);  color: var(--color-danger);  }
.badge-blue     { background: rgba(59,130,246,.15); color: var(--color-primary); }

.error-msg {
  background: rgba(239,68,68,.12);
  border: 1px solid rgba(239,68,68,.3);
  border-radius: var(--radius);
  padding: .8rem 1rem;
  color: var(--color-danger);
  font-size: .9rem;
}
.spinner {
  width: 36px; height: 36px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin .7s linear infinite;
  margin: 3rem auto;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
