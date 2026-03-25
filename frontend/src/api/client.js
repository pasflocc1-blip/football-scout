import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// Intercettore risposta: gestione errori globale
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const msg = error.response?.data?.detail || error.message || 'Errore di rete'
    console.error('[API Error]', msg)
    return Promise.reject(new Error(msg))
  }
)

// ── Team ─────────────────────────────────────────────────────────
export const teamApi = {
  list:   ()           => api.get('/teams'),
  get:    (id)         => api.get(`/teams/${id}`),
  create: (data)       => api.post('/teams', data),
  update: (id, data)   => api.put(`/teams/${id}`, data),
  delete: (id)         => api.delete(`/teams/${id}`),
}

// ── Traits ───────────────────────────────────────────────────────
export const traitApi = {
  add:    (teamId, data) => api.post(`/teams/${teamId}/traits`, data),
  delete: (teamId, id)   => api.delete(`/teams/${teamId}/traits/${id}`),
}

// ── Rosa (giocatori squadra) ──────────────────────────────────────
export const rosterApi = {
  list:   (teamId)       => api.get(`/teams/${teamId}/players`),
  add:    (teamId, data) => api.post(`/teams/${teamId}/players`, data),
  remove: (teamId, id)   => api.delete(`/teams/${teamId}/players/${id}`),
}

// ── Scouting ─────────────────────────────────────────────────────
export const scoutingApi = {
  search: (params) => api.get('/scouting/search', { params }),
}

export default api
