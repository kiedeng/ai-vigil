import { createRouter, createWebHistory } from 'vue-router';
import Login from './views/Login.vue';
import Dashboard from './views/Dashboard.vue';
import Checks from './views/Checks.vue';
import Runs from './views/Runs.vue';
import Models from './views/Models.vue';
import Quality from './views/Quality.vue';
import Samples from './views/Samples.vue';
import Trends from './views/Trends.vue';
import Alerts from './views/Alerts.vue';
import Settings from './views/Settings.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', component: Dashboard },
    { path: '/checks', component: Checks },
    { path: '/runs', component: Runs },
    { path: '/trends', component: Trends },
    { path: '/quality', component: Quality },
    { path: '/samples', component: Samples },
    { path: '/models', component: Models },
    { path: '/alerts', component: Alerts },
    { path: '/settings', component: Settings }
  ]
});

router.beforeEach((to) => {
  const token = localStorage.getItem('ai-eye-token');
  if (!token && to.path !== '/login') {
    return '/login';
  }
  if (token && to.path === '/login') {
    return '/';
  }
  return true;
});
