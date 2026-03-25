<template>
  <div>
    <h1 class="page-title">🏠 Dashboard Squadra</h1>

    <!-- Loading -->
    <div v-if="teamStore.loading" class="spinner" />

    <!-- Nessuna squadra -->
    <div v-else-if="teamStore.teams.length === 0" class="card" style="text-align:center; padding:3rem">
      <p style="font-size:3rem">⚽</p>
      <p style="margin:.5rem 0 1.5rem; color:var(--color-muted)">Nessuna squadra trovata. Creane una per iniziare.</p>
      <button class="btn btn-primary" @click="showForm = true">+ Crea Squadra</button>
    </div>

    <template v-else>
      <!-- Selezione squadra -->
      <div class="card" style="margin-bottom:1.5rem">
        <div style="display:flex; align-items:center; gap:1rem; flex-wrap:wrap">
          <label style="color:var(--color-muted); font-size:.9rem">Squadra attiva:</label>
          <select style="max-width:260px" @change="teamStore.selectTeam(+$event.target.value)">
            <option v-for="t in teamStore.teams" :key="t.id" :value="t.id"
              :selected="t.id === teamStore.activeTeam?.id">
              {{ t.name }}
            </option>
          </select>
          <button class="btn btn-primary" style="margin-left:auto" @click="showForm = true">
            + Nuova Squadra
          </button>
        </div>
      </div>

      <!-- Dettagli squadra -->
      <div v-if="teamStore.activeTeam" class="grid-2" style="gap:1.5rem; display:grid; grid-template-columns:1fr 1fr">

        <div class="card">
          <h2 style="font-size:1.1rem; margin-bottom:1rem; color:var(--color-primary)">📋 Informazioni Generali</h2>
          <div class="info-grid">
            <InfoRow label="Nome"       :value="teamStore.activeTeam.name" />
            <InfoRow label="Modulo"     :value="teamStore.activeTeam.formation" />
            <InfoRow label="Lega"       :value="teamStore.activeTeam.league" />
            <InfoRow label="Stagione"   :value="teamStore.activeTeam.season" />
            <InfoRow label="Allenatore" :value="teamStore.activeTeam.coach" />
            <InfoRow label="Budget"     :value="teamStore.activeTeam.budget ? `€${teamStore.activeTeam.budget.toLocaleString('it')}` : '—'" />
          </div>
          <button class="btn btn-ghost" style="margin-top:1rem; width:100%" @click="showForm = true">
            ✏️ Modifica
          </button>
        </div>

        <!-- Traits summary -->
        <div class="card">
          <h2 style="font-size:1.1rem; margin-bottom:1rem; color:var(--color-primary)">📊 Analisi Squadra</h2>

          <p style="font-size:.85rem; color:var(--color-muted); margin-bottom:.5rem">✅ Punti di Forza</p>
          <div style="display:flex; flex-wrap:wrap; gap:.4rem; margin-bottom:1rem">
            <span v-for="t in teamStore.positiveTraits" :key="t.id" class="badge badge-positive">
              {{ t.description }}
            </span>
            <span v-if="!teamStore.positiveTraits.length" style="color:var(--color-muted); font-size:.85rem">Nessuno</span>
          </div>

          <p style="font-size:.85rem; color:var(--color-muted); margin-bottom:.5rem">❌ Punti Deboli</p>
          <div style="display:flex; flex-wrap:wrap; gap:.4rem; margin-bottom:1rem">
            <span v-for="t in teamStore.negativeTraits" :key="t.id" class="badge badge-negative">
              {{ t.description }}
            </span>
            <span v-if="!teamStore.negativeTraits.length" style="color:var(--color-muted); font-size:.85rem">Nessuno</span>
          </div>

          <RouterLink to="/traits" class="btn btn-ghost" style="display:flex; justify-content:center; text-decoration:none">
            📋 Gestisci Caratteristiche
          </RouterLink>
        </div>
      </div>

      <!-- Note -->
      <div v-if="teamStore.activeTeam?.notes" class="card" style="margin-top:1.5rem">
        <h3 style="font-size:.9rem; color:var(--color-muted); margin-bottom:.5rem">📝 Note</h3>
        <p style="line-height:1.6">{{ teamStore.activeTeam.notes }}</p>
      </div>
    </template>

    <!-- Modal form -->
    <ModalForm v-if="showForm" :team="teamStore.activeTeam" @close="showForm = false" @saved="showForm = false" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useTeamStore } from '@/stores/teamStore'
import ModalForm from '@/components/TeamForm.vue'
import InfoRow from '@/components/InfoRow.vue'

const teamStore = useTeamStore()
const showForm  = ref(false)
</script>
