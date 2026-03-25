import { createRouter, createWebHistory } from 'vue-router'
import TeamDashboard from '@/views/TeamDashboard.vue'
import TeamTraits    from '@/views/TeamTraits.vue'
import ScoutingSearch from '@/views/ScoutingSearch.vue'
import TeamRoster    from '@/views/TeamRoster.vue'

const routes = [
  { path: '/',           name: 'dashboard', component: TeamDashboard },
  { path: '/traits',     name: 'traits',    component: TeamTraits },
  { path: '/roster',     name: 'roster',    component: TeamRoster },
  { path: '/scouting',   name: 'scouting',  component: ScoutingSearch },
  { path: '/data-ingestion', name: 'DataIngestion', component: () => import('@/views/DataIngestion.vue'),meta: { title: 'Gestione Dati' }},
  { path: '/db-explorer', name: 'DatabaseExplorer', component: () => import('@/views/DatabaseExplorer.vue'), meta: { title: 'Database Explorer' }},
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
