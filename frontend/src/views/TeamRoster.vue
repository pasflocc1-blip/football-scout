<template>
  <div>
    <h1 class="page-title">👥 Rosa</h1>

    <div v-if="!teamStore.activeTeam" class="error-msg">Nessuna squadra attiva.</div>

    <template v-else>
      <!-- Form aggiunta giocatore -->
      <div class="card" style="margin-bottom:1.5rem">
        <h2 style="font-size:1rem; margin-bottom:1rem">➕ Aggiungi Giocatore</h2>
        <div style="display:grid; grid-template-columns:2fr 1fr 1fr 1fr auto; gap:.75rem; align-items:end">
          <div>
            <label class="form-label">Nome</label>
            <input v-model="form.name" placeholder="Nome giocatore" />
          </div>
          <div>
            <label class="form-label">Posizione</label>
            <!-- Select con codice + descrizione -->
            <select v-model="form.position">
              <option v-for="opt in posOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
          <div>
            <label class="form-label">Età</label>
            <input type="number" v-model.number="form.age" min="15" max="45" placeholder="25" />
          </div>
          <div>
            <label class="form-label">Piede</label>
            <select v-model="form.preferred_foot">
              <option value="">—</option>
              <option value="Right">Destro</option>
              <option value="Left">Mancino</option>
            </select>
          </div>
          <button class="btn btn-primary" :disabled="!form.name.trim()" @click="addPlayer">
            Aggiungi
          </button>
        </div>
      </div>

      <!-- Tabella rosa -->
      <div class="card">
        <div v-if="!players.length" style="text-align:center; padding:2rem; color:var(--color-muted)">
          Nessun giocatore in rosa. Aggiungine uno sopra.
        </div>
        <table v-else style="width:100%; border-collapse:collapse">
          <thead>
            <tr style="border-bottom:1px solid var(--color-border)">
              <th class="th">Giocatore</th>
              <th class="th">Ruolo</th>
              <th class="th">Età</th>
              <th class="th">Piede</th>
              <th class="th">Rating</th>
              <th class="th"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in players" :key="p.id" style="border-bottom:1px solid var(--color-border)">
              <td class="td name-cell">{{ p.name }}</td>
              <td class="td">
                <div class="pos-cell">
                  <!-- Badge con codice tecnico -->
                  <span class="badge badge-blue pos-code">{{ p.position || '—' }}</span>
                  <!-- Descrizione ruolo per esteso -->
                  <span class="pos-desc">{{ posLabel(p.position) }}</span>
                </div>
              </td>
              <td class="td">{{ p.age || '—' }}</td>
              <td class="td">{{ footLabel(p.preferred_foot) }}</td>
              <td class="td">
                <span v-if="p.rating" :style="`color:${ratingColor(p.rating)}`">
                  {{ p.rating.toFixed(1) }}
                </span>
                <span v-else>—</span>
              </td>
              <td class="td">
                <button
                  class="btn btn-danger"
                  style="padding:.3rem .7rem; font-size:.8rem"
                  @click="removePlayer(p)"
                >✕</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useTeamStore } from '@/stores/teamStore'
import { rosterApi }    from '@/api/client'
import { posLabel, posOptions } from '@/utils/positions.js'

const teamStore = useTeamStore()
const players   = ref([])
const form      = ref({ name: '', position: '', age: null, preferred_foot: '' })

onMounted(fetchPlayers)

async function fetchPlayers() {
  if (!teamStore.activeTeam) return
  const { data } = await rosterApi.list(teamStore.activeTeam.id)
  players.value = data
}

async function addPlayer() {
  if (!form.value.name.trim()) return
  const { data } = await rosterApi.add(teamStore.activeTeam.id, form.value)
  players.value.push(data)
  form.value = { name: '', position: '', age: null, preferred_foot: '' }
}

async function removePlayer(p) {
  await rosterApi.remove(teamStore.activeTeam.id, p.id)
  players.value = players.value.filter(x => x.id !== p.id)
}

function footLabel(foot) {
  const map = { Right: 'Destro', Left: 'Mancino' }
  // Usiamo le parentesi per dire a JS di valutare prima il ??
  return (map[foot] ?? foot) || '—'
}
function ratingColor(r) {
  if (r >= 80) return 'var(--color-success)'
  if (r >= 65) return 'var(--color-warning)'
  return 'var(--color-danger)'
}
</script>

<style scoped>
.form-label {
  display: block;
  font-size: .8rem;
  color: var(--color-muted);
  margin-bottom: .3rem;
}
.th {
  text-align: left;
  padding: .6rem 1rem;
  font-size: .8rem;
  color: var(--color-muted);
  text-transform: uppercase;
  letter-spacing: .05em;
}
.td { padding: .75rem 1rem; font-size: .9rem; }
.name-cell { font-weight: 600; }

/* Ruolo: badge codice + testo descrizione affiancati */
.pos-cell {
  display: flex;
  align-items: center;
  gap: .5rem;
}
.pos-code {
  font-size: .72rem;
  flex-shrink: 0;
  font-family: 'Fira Code', monospace;
  letter-spacing: .03em;
}
.pos-desc {
  font-size: .82rem;
  color: var(--color-muted);
}
</style>