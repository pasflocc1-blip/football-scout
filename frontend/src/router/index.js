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
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
