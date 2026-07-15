<template>
  <div class="min-h-screen flex flex-col">
    <!-- Navbar -->
    <header class="bg-eurocar-blue text-white shadow-lg sticky top-0 z-50">
      <div class="container mx-auto px-4">
        <div class="flex justify-between items-center py-4">
          <!-- Logo -->
          <router-link to="/" class="flex items-center gap-3">
            <img :src="logoUrl" alt="R Car Rogil" class="h-10">
            <div>
              <h1 class="text-2xl font-bold">R Car Rogil</h1>
              <p class="text-xs text-eurocar-light">Vehículos de Ocasión</p>
            </div>
          </router-link>
          
          <!-- Nav Links -->
          <nav class="hidden md:flex items-center gap-6">
            <router-link to="/" class="hover:text-eurocar-light transition">Inicio</router-link>
            <router-link to="/catalogo" class="hover:text-eurocar-light transition">Catálogo</router-link>
            <router-link to="/tasacion" class="hover:text-eurocar-light transition">Tasamos tu coche</router-link>
            <router-link to="/contacto" class="hover:text-eurocar-light transition">Contacto</router-link>
          </nav>
          
          <!-- Mobile Menu Button -->
          <button @click="mobileMenuOpen = !mobileMenuOpen" class="md:hidden">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
            </svg>
          </button>
        </div>
        
        <!-- Mobile Menu -->
        <div v-if="mobileMenuOpen" class="md:hidden pb-4">
          <nav class="flex flex-col gap-2">
            <router-link to="/" class="hover:text-eurocar-light transition py-2">Inicio</router-link>
            <router-link to="/catalogo" class="hover:text-eurocar-light transition py-2">Catálogo</router-link>
            <router-link to="/tasacion" class="hover:text-eurocar-light transition py-2">Tasamos tu coche</router-link>
            <router-link to="/contacto" class="hover:text-eurocar-light transition py-2">Contacto</router-link>
          </nav>
        </div>
      </div>
    </header>
    
    <!-- Main Content -->
    <main class="flex-1">
      <router-view />
    </main>
    
    <!-- Footer -->
    <footer class="bg-gray-900 text-white py-12">
      <div class="container mx-auto px-4">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-8">
          <!-- Logo & Info -->
          <div>
            <h3 class="text-xl font-bold mb-4">R Car Rogil</h3>
            <p class="text-gray-400 text-sm">
              Vehículos de ocasión de calidad en Madrid. 
              Garantía incluida en todas nuestras ventas.
            </p>
          </div>
          
          <!-- Enlaces -->
          <div>
            <h4 class="font-semibold mb-4">Enlaces</h4>
            <ul class="space-y-2 text-gray-400 text-sm">
              <li><router-link to="/" class="hover:text-white">Inicio</router-link></li>
              <li><router-link to="/catalogo" class="hover:text-white">Catálogo</router-link></li>
              <li><router-link to="/tasacion" class="hover:text-white">Tasación</router-link></li>
              <li><router-link to="/contacto" class="hover:text-white">Contacto</router-link></li>
            </ul>
          </div>
          
          <!-- Contacto -->
          <div>
            <h4 class="font-semibold mb-4">Contacto</h4>
            <ul class="space-y-2 text-gray-400 text-sm">
              <li>📞 +34 722 81 7617</li>
              <li>info@rcarrogil.com <span class="text-xs text-yellow-300">(por actualizar)</span></li>
              <li>📍 Calle Brasil 9, Alcalá de Henares</li>
            </ul>
          </div>
          
          <!-- Horario -->
          <div>
            <h4 class="font-semibold mb-4">Horario</h4>
            <ul class="space-y-2 text-gray-400 text-sm">
              <li>Lunes - Viernes: 9:00 - 19:00</li>
              <li>Sábados: 10:00 - 14:00</li>
              <li>Domingos: Cerrado</li>
            </ul>
          </div>
        </div>
        
        <div class="border-t border-gray-800 mt-8 pt-8 text-center text-gray-500 text-sm">
          <p>&copy; {{ currentYear }} R Car Rogil. Todos los derechos reservados.</p>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const mobileMenuOpen = ref(false)
const currentYear = computed(() => new Date().getFullYear())
const logoUrl = import.meta.env.BASE_URL + 'img/logo_rcarrogil.svg'
</script>
