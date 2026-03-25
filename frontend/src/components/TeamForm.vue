<template>
  <!-- Overlay -->
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem">
        <h2 style="font-size:1.1rem">{{ team ? '✏️ Modifica Squadra' : '➕ Nuova Squadra' }}</h2>
        <button class="btn btn-ghost" style="padding:.3rem .7rem" @click="$emit('close')">✕</button>
      </div>

      <div class="form-grid">
        <div>
          <label class="form-label">Nome Squadra *</label>
          <input v-model="form.name" placeholder="es. FC Demo" />
        </div>
        <div>
          <label class="form-label">Modulo</label>
          <select v-model="form.formation">
            <option value="">—</option>
            <option>4-3-3</option><option>4-4-2</option><option>4-2-3-1</option>
            <option>3-5-2</option><option>3-4-3</option><option>5-3-2</option>
          </select>
        </div>
        <div>
          <label class="form-label">Lega</label>
          <input v-model="form.league" placeholder="es. Serie A" />
        </div>
        <div>
          <label class="form-label">Stagione</label>
          <input v-model="form.season" placeholder="es. 2024/2025" />
        </div>
        <div>
          <label class="form-label">Allenatore</label>
          <input v-model="form.coach" placeholder="Nome allenatore" />
        </div>
        <div>
          <label class="form-label">Budget (€)</label>
          <input type="number" v-model.number="form.budget" placeholder="es. 5000000" />
        </div>
        <div style="grid-column:1/-1">
          <label class="form-label">Note</label>
          <textarea v-model="form.notes" rows="3" placeholder="Note libere sulla squadra..." />
        </div>
      </div>

      <p v-if="error" class="error-msg" style="margin-top:1rem">{{ error }}</p>

      <div style="display:flex; gap:.75rem; justify-content:flex-end; margin-top:1.5rem">
        <button class="btn btn-ghost" @click="$emit('close')">Annulla</button>
        <button class="btn btn-primary" :disabled="!form.name.trim() || saving" @click="save">
          {{ saving ? 'Salvo...' : 'Salva' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useTeamStore } from '@/stores/teamStore'

const props = defineProps({ team: Object })
const emit  = defineEmits(['close', 'saved'])
const teamStore = useTeamStore()
const saving    = ref(false)
const error     = ref('')

const form = ref({
  name:      props.team?.name      ?? '',
  formation: props.team?.formation ?? '',
  league:    props.team?.league    ?? '',
  season:    props.team?.season    ?? '',
  coach:     props.team?.coach     ?? '',
  budget:    props.team?.budget    ?? null,
  notes:     props.team?.notes     ?? '',
})

async function save() {
  if (!form.value.name.trim()) return
  saving.value = true
  error.value  = ''
  try {
    if (props.team) {
      await teamStore.updateTeam(props.team.id, form.value)
    } else {
      await teamStore.createTeam(form.value)
    }
    emit('saved')
    emit('close')
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
  padding: 1rem;
}
.modal { width: 100%; max-width: 560px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .9rem; }
.form-label { display: block; font-size: .8rem; color: var(--color-muted); margin-bottom: .3rem; }
</style>
