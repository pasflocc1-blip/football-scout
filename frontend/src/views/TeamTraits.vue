<template>
  <div>
    <h1 class="page-title">📋 Caratteristiche Squadra</h1>

    <div v-if="!teamStore.activeTeam" class="error-msg">
      Nessuna squadra attiva. Torna alla <RouterLink to="/">Dashboard</RouterLink> e crea una squadra.
    </div>

    <template v-else>
      <!-- Form aggiunta trait -->
      <div class="card" style="margin-bottom:1.5rem">
        <h2 style="font-size:1rem; margin-bottom:1rem">➕ Aggiungi Caratteristica</h2>
        <div style="display:grid; grid-template-columns:1fr 1fr 2fr auto; gap:.75rem; align-items:end">
          <div>
            <label class="form-label">Tipo</label>
            <select v-model="form.trait_type">
              <option value="positive">✅ Positiva</option>
              <option value="negative">❌ Negativa</option>
            </select>
          </div>
          <div>
            <label class="form-label">Priorità</label>
            <select v-model.number="form.priority">
              <option :value="1">Alta</option>
              <option :value="2">Media</option>
              <option :value="3">Bassa</option>
            </select>
          </div>
          <div>
            <label class="form-label">Descrizione</label>
            <input v-model="form.description" placeholder="es. Scarsa efficacia di testa" @keyup.enter="addTrait" />
          </div>
          <button class="btn btn-primary" :disabled="!form.description.trim()" @click="addTrait">
            Aggiungi
          </button>
        </div>
        <p v-if="error" class="error-msg" style="margin-top:.75rem">{{ error }}</p>
      </div>

      <!-- Colonne positive / negative -->
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:1.5rem">

        <div class="card">
          <h2 style="font-size:1rem; color:var(--color-success); margin-bottom:1rem">
            ✅ Punti di Forza ({{ teamStore.positiveTraits.length }})
          </h2>
          <div v-if="!teamStore.positiveTraits.length" style="color:var(--color-muted); font-size:.9rem">
            Nessun punto di forza inserito.
          </div>
          <TraitItem
            v-for="t in teamStore.positiveTraits"
            :key="t.id"
            :trait="t"
            @delete="deleteTrait(t)"
          />
        </div>

        <div class="card">
          <h2 style="font-size:1rem; color:var(--color-danger); margin-bottom:1rem">
            ❌ Punti Deboli ({{ teamStore.negativeTraits.length }})
          </h2>
          <div v-if="!teamStore.negativeTraits.length" style="color:var(--color-muted); font-size:.9rem">
            Nessun punto debole inserito.
          </div>
          <TraitItem
            v-for="t in teamStore.negativeTraits"
            :key="t.id"
            :trait="t"
            @delete="deleteTrait(t)"
          />
        </div>
      </div>

      <!-- Suggerimento scouting -->
      <div v-if="teamStore.negativeTraits.length" class="card" style="margin-top:1.5rem; border-color:rgba(59,130,246,.3)">
        <h3 style="font-size:.95rem; color:var(--color-primary); margin-bottom:.75rem">
          💡 Suggerimenti Scouting dai tuoi Punti Deboli
        </h3>
        <p style="font-size:.85rem; color:var(--color-muted); margin-bottom:.75rem">
          Clicca su un suggerimento per avviare una ricerca mirata:
        </p>
        <div style="display:flex; flex-wrap:wrap; gap:.5rem">
          <RouterLink
            v-for="s in teamStore.scoutingSuggestions"
            :key="s"
            :to="`/scouting?q=${encodeURIComponent(s)}`"
            class="badge badge-blue"
            style="text-decoration:none; cursor:pointer"
          >
            🔍 {{ s }}
          </RouterLink>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useTeamStore } from '@/stores/teamStore'
import TraitItem from '@/components/TraitItem.vue'

const teamStore = useTeamStore()
const error     = ref('')

const form = ref({ trait_type: 'positive', description: '', priority: 1 })

async function addTrait() {
  if (!form.value.description.trim()) return
  error.value = ''
  try {
    await teamStore.addTrait(teamStore.activeTeam.id, form.value)
    form.value.description = ''
  } catch (e) {
    error.value = e.message
  }
}

async function deleteTrait(trait) {
  await teamStore.deleteTrait(teamStore.activeTeam.id, trait.id)
}
</script>

<style scoped>
.form-label { display:block; font-size:.8rem; color:var(--color-muted); margin-bottom:.3rem; }
</style>
