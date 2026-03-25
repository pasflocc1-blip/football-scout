import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { teamApi, traitApi } from '@/api/client'

export const useTeamStore = defineStore('team', () => {
  // ── State ──────────────────────────────────────────────────────
  const teams       = ref([])
  const activeTeam  = ref(null)
  const loading     = ref(false)
  const error       = ref(null)

  // ── Getters ────────────────────────────────────────────────────
  const positiveTraits = computed(() =>
    activeTeam.value?.traits?.filter(t => t.trait_type === 'positive') ?? []
  )
  const negativeTraits = computed(() =>
    activeTeam.value?.traits?.filter(t => t.trait_type === 'negative') ?? []
  )
  // Suggerimenti di scouting basati sui punti deboli
  const scoutingSuggestions = computed(() =>
    negativeTraits.value.map(t => t.description)
  )

  // ── Actions ────────────────────────────────────────────────────
  async function fetchTeams() {
    loading.value = true
    error.value = null
    try {
      const { data } = await teamApi.list()
      teams.value = data
      if (data.length > 0 && !activeTeam.value) {
        await selectTeam(data[0].id)
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function selectTeam(id) {
    const { data } = await teamApi.get(id)
    activeTeam.value = data
  }

  async function createTeam(formData) {
    const { data } = await teamApi.create(formData)
    teams.value.push(data)
    activeTeam.value = data
    return data
  }

  async function updateTeam(id, formData) {
    const { data } = await teamApi.update(id, formData)
    activeTeam.value = data
    const idx = teams.value.findIndex(t => t.id === id)
    if (idx !== -1) teams.value[idx] = data
    return data
  }

  async function addTrait(teamId, traitData) {
    const { data } = await traitApi.add(teamId, traitData)
    activeTeam.value?.traits?.push(data)
    return data
  }

  async function deleteTrait(teamId, traitId) {
    await traitApi.delete(teamId, traitId)
    if (activeTeam.value) {
      activeTeam.value.traits = activeTeam.value.traits.filter(t => t.id !== traitId)
    }
  }

  return {
    teams, activeTeam, loading, error,
    positiveTraits, negativeTraits, scoutingSuggestions,
    fetchTeams, selectTeam, createTeam, updateTeam,
    addTrait, deleteTrait,
  }
})
