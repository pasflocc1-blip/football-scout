<template>
  <div>
    <h1 class="page-title">🔍 Scouting Giocatori</h1>

    <!-- Suggerimenti dai punti deboli -->
    <div v-if="suggestions.length" class="card" style="margin-bottom:1.5rem; border-color:rgba(59,130,246,.3)">
      <p style="font-size:.85rem; color:var(--color-muted); margin-bottom:.6rem">
        💡 Cerca in base ai punti deboli della squadra:
      </p>
      <div style="display:flex; flex-wrap:wrap; gap:.4rem">
        <button
          v-for="s in suggestions"
          :key="s"
          class="badge badge-blue"
          style="cursor:pointer; border:none"
          @click="quickSearch(s)"
        >
          {{ s }}
        </button>
      </div>
    </div>

    <!-- Barra di ricerca -->
    <div class="card" style="margin-bottom:1.5rem">
      <div style="display:flex; gap:.75rem; margin-bottom:.75rem">
        <input
          v-model="query"
          placeholder="es: centravanti mancino bravo di testa under 25"
          style="flex:1"
          @keyup.enter="doSearch"
        />
        <button class="btn btn-primary" :disabled="scoutingStore.loading || !query.trim()" @click="doSearch">
          {{ scoutingStore.loading ? '...' : '🔍 Cerca' }}
        </button>
        <button v-if="scoutingStore.results.length" class="btn btn-ghost" @click="clearSearch">
          ✕ Pulisci
        </button>
      </div>

      <!-- Filtri avanzati -->
      <details>
        <summary style="cursor:pointer; font-size:.85rem; color:var(--color-muted)">⚙️ Filtri avanzati</summary>
        <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:.75rem; margin-top:.75rem">
          <div>
            <label class="form-label">Posizione</label>
            <select v-model="filters.position">
              <option value="">Tutte</option>
              <option>GK</option><option>CB</option><option>LB</option><option>RB</option>
              <option>DM</option><option>CM</option><option>AM</option>
              <option>LW</option><option>RW</option><option>ST</option>
            </select>
          </div>
          <div>
            <label class="form-label">Età min</label>
            <input type="number" v-model.number="filters.min_age" min="15" max="45" placeholder="15" />
          </div>
          <div>
            <label class="form-label">Età max</label>
            <input type="number" v-model.number="filters.max_age" min="15" max="45" placeholder="40" />
          </div>
          <div>
            <label class="form-label">Nazionalità</label>
            <input v-model="filters.nationality" placeholder="es. Italiana" />
          </div>
        </div>
      </details>
    </div>

    <!-- Errore -->
    <div v-if="scoutingStore.error" class="error-msg" style="margin-bottom:1rem">
      {{ scoutingStore.error }}
    </div>

    <!-- Spinner -->
    <div v-if="scoutingStore.loading" class="spinner" />

    <!-- Risultati -->
    <template v-else-if="scoutingStore.results.length">
      <p style="font-size:.85rem; color:var(--color-muted); margin-bottom:1rem">
        {{ scoutingStore.results.length }} giocatori trovati per
        <strong>"{{ scoutingStore.lastQuery }}"</strong>
      </p>
      <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:1rem">
        <PlayerCard v-for="p in scoutingStore.results" :key="p.id" :player="p" />
      </div>
    </template>

    <!-- Stato vuoto dopo ricerca -->
    <div v-else-if="searched && !scoutingStore.loading" class="card" style="text-align:center; padding:2.5rem">
      <p style="font-size:2rem">🤷</p>
      <p style="color:var(--color-muted); margin-top:.5rem">Nessun giocatore trovato. Prova a modificare la ricerca.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useScoutingStore } from '@/stores/scoutingStore'
import { useTeamStore }     from '@/stores/teamStore'
import PlayerCard from '@/components/PlayerCard.vue'

const scoutingStore = useScoutingStore()
const teamStore     = useTeamStore()
const route         = useRoute()

const query    = ref('')
const searched = ref(false)
const filters  = ref({ position: '', min_age: null, max_age: null, nationality: '' })

// Suggerimenti dai punti deboli della squadra
const suggestions = computed(() => teamStore.scoutingSuggestions)

// Avvia ricerca da query-string (es: dal link in TeamTraits)
onMounted(() => {
  if (route.query.q) {
    query.value = route.query.q
    doSearch()
  }
})

async function doSearch() {
  if (!query.value.trim()) return
  searched.value = true
  const params = { q: query.value, limit: 20 }
  if (filters.value.position)    params.position    = filters.value.position
  if (filters.value.min_age)     params.min_age     = filters.value.min_age
  if (filters.value.max_age)     params.max_age     = filters.value.max_age
  if (filters.value.nationality) params.nationality = filters.value.nationality
  await scoutingStore.search(params)
}

function quickSearch(text) {
  query.value = text
  doSearch()
}

function clearSearch() {
  query.value = ''
  searched.value = false
  scoutingStore.clear()
}
</script>

<style scoped>
.form-label { display:block; font-size:.8rem; color:var(--color-muted); margin-bottom:.3rem; }
</style>
