import { defineStore } from 'pinia'
import { ref } from 'vue'
import { scoutingApi } from '@/api/client'

export const useScoutingStore = defineStore('scouting', () => {
  const results  = ref([])
  const loading  = ref(false)
  const error    = ref(null)
  const lastQuery = ref('')

  async function search(params) {
    loading.value  = true
    error.value    = null
    lastQuery.value = params.q || ''
    try {
      const { data } = await scoutingApi.search(params)
      results.value = data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  function clear() {
    results.value = []
    lastQuery.value = ''
  }

  return { results, loading, error, lastQuery, search, clear }
})
