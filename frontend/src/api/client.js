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

// ── Scouting (team-based) ─────────────────────────────────────────
export const scoutingApi = {
  search: (params) => api.get('/scouting/search', { params }),
}

// ── Global Scouting 🔥 ───────────────────────────────────────────
// Esplorazione libera del database, ranking, confronto e discovery.
export const globalScoutingApi = {
  /**
   * Ricerca avanzata con filtri combinabili.
   * @param {Object} params - { q, position, min_age, max_age, nationality, club,
   *                            min_xg, min_xa, preferred_foot, sort_by, sort_dir, limit }
   */
  search: (params) => api.get('/scouting/search', { params }),

  /**
   * Classifica per xG/90.
   * @param {Object} params - { limit, min_minutes, position }
   */
  topXg: (params = {}) => api.get('/scouting/top-xg', { params }),

  /**
   * Giocatori che segnano più del loro xG previsto.
   * @param {Object} params - { limit, min_minutes, position }
   */
  overperforming: (params = {}) => api.get('/scouting/overperforming', { params }),

  /**
   * Giocatori che segnano meno del loro xG previsto.
   * @param {Object} params - { limit, min_minutes, position }
   */
  underperforming: (params = {}) => api.get('/scouting/underperforming', { params }),

  /**
   * Confronto testa-a-testa tra due giocatori.
   * @param {string} name1 - Nome (parziale) del primo giocatore
   * @param {string} name2 - Nome (parziale) del secondo giocatore
   */
  compare: (name1, name2) => api.get('/scouting/compare', { params: { name1, name2 } }),
}

export default api