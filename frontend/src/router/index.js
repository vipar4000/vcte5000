import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue')
  },
  {
    path: '/catalogo',
    name: 'Catalogo',
    component: () => import('../views/Catalogo.vue')
  },
  {
    path: '/vehiculo/:id',
    name: 'VehiculoDetalle',
    component: () => import('../views/VehiculoDetalle.vue')
  },
  {
    path: '/tasacion',
    name: 'Tasacion',
    component: () => import('../views/Tasacion.vue')
  },
  {
    path: '/cita',
    name: 'Cita',
    component: () => import('../views/Cita.vue')
  },
  {
    // Enlaces antiguos: /contacto lleva a la cita
    path: '/contacto',
    redirect: '/cita'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    return { top: 0 }
  }
})

export default router
