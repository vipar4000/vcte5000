<template>
  <div>
    <!-- Hero Section -->
    <section class="hero-gradient text-white py-20">
      <div class="container mx-auto px-4 text-center">
        <h1 class="text-4xl md:text-6xl font-bold mb-6">
          Encuentra tu coche perfecto
        </h1>
        <p class="text-xl md:text-2xl text-eurocar-light mb-8">
          Vehículos de ocasión de calidad con garantía en Madrid
        </p>
        
        <!-- Buscador Rápido -->
        <div class="max-w-3xl mx-auto bg-white rounded-lg shadow-xl p-6">
          <div class="flex flex-col md:flex-row gap-4">
            <select v-model="filtroMarca" class="flex-1 px-4 py-3 text-gray-800 rounded-lg border focus:ring-2 focus:ring-eurocar-light">
              <option value="">Todas las marcas</option>
              <option v-for="marca in marcas" :key="marca" :value="marca">{{ marca }}</option>
            </select>
            
            <select v-model="filtroPrecio" class="flex-1 px-4 py-3 text-gray-800 rounded-lg border focus:ring-2 focus:ring-eurocar-light">
              <option value="">Cualquier precio</option>
              <option value="0-5000">Hasta €5.000</option>
              <option value="5000-10000">€5.000 - €10.000</option>
              <option value="10000-20000">€10.000 - €20.000</option>
              <option value="20000-999999">Más de €20.000</option>
            </select>
            
            <select v-model="filtroEtiqueta" class="flex-1 px-4 py-3 text-gray-800 rounded-lg border focus:ring-2 focus:ring-eurocar-light">
              <option value="">Cualquier etiqueta</option>
              <option value="0">Cero emisiones (0)</option>
              <option value="ECO">ECO</option>
              <option value="B">B</option>
              <option value="C">C</option>
            </select>
            
            <router-link to="/catalogo" class="btn-primary text-center">
              🔍 Buscar
            </router-link>
          </div>
        </div>
      </div>
    </section>
    
    <!-- Featured Cars -->
    <section class="py-16 bg-gray-50">
      <div class="container mx-auto px-4">
        <h2 class="text-3xl font-bold text-center mb-12 text-gray-800">
          Vehículos Destacados
        </h2>
        
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <div v-for="vehiculo in vehiculosDestacados" :key="vehiculo.id" 
               class="bg-white rounded-lg shadow-lg overflow-hidden card-hover transition-all duration-300">
            <div class="h-48 bg-gray-200 flex items-center justify-center">
              <img v-if="vehiculo.imagen_url" :src="vehiculo.imagen_url" :alt="vehiculo.marca + ' ' + vehiculo.modelo" class="w-full h-full object-contain">
              <span v-else class="text-6xl">🚗</span>
            </div>
            <div class="p-6">
              <div class="flex justify-between items-start mb-2">
                <h3 class="text-xl font-bold text-gray-800">{{ vehiculo.marca }} {{ vehiculo.modelo }}</h3>
                <span class="px-2 py-1 text-xs rounded-full bg-eurocar-light text-white">
                  {{ vehiculo.etiqueta_ambiental }}
                </span>
              </div>
              <p class="text-gray-500 text-sm mb-4">{{ vehiculo.anio }} | {{ vehiculo.kilometraje }} km</p>
              <div class="flex justify-between items-center">
                <span class="text-2xl font-bold text-eurocar-blue">{{ formatEUR(vehiculo.precio_venta) }}</span>
                <router-link :to="`/vehiculo/${vehiculo.id}`" class="text-eurocar-light hover:underline">
                  Ver detalles →
                </router-link>
              </div>
            </div>
          </div>
        </div>
        
        <div class="text-center mt-8">
          <router-link to="/catalogo" class="btn-primary inline-block">
            Ver todo el catálogo →
          </router-link>
        </div>
      </div>
    </section>
    
    <!-- Benefits -->
    <section class="py-16">
      <div class="container mx-auto px-4">
        <h2 class="text-3xl font-bold text-center mb-12 text-gray-800">
          ¿Por qué elegir R Car Rogil?
        </h2>
        
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div class="text-center p-6">
            <div class="text-5xl mb-4">🛡️</div>
            <h3 class="text-xl font-bold mb-2">Garantía 1 Año</h3>
            <p class="text-gray-600">
              Todos nuestros vehículos incluyen garantía legal de 1 año según Real Decreto-ley 7/2021.
            </p>
          </div>
          
          <div class="text-center p-6">
            <div class="text-5xl mb-4">🔍</div>
            <h3 class="text-xl font-bold mb-2">Revisados</h3>
            <p class="text-gray-600">
              Cada vehículo pasa por un riguroso control de calidad antes de salir a la venta.
            </p>
          </div>
          
          <div class="text-center p-6">
            <div class="text-5xl mb-4">📋</div>
            <h3 class="text-xl font-bold mb-2">Gestoría Incluida</h3>
            <p class="text-gray-600">
              Nos encargamos del cambio de titularidad y todos los trámites administrativos.
            </p>
          </div>
        </div>
      </div>
    </section>
    
    <!-- CTA Section -->
    <section class="py-16 bg-eurocar-blue text-white">
      <div class="container mx-auto px-4 text-center">
        <h2 class="text-3xl font-bold mb-4">¿Tienes un coche que vender?</h2>
        <p class="text-xl text-eurocar-light mb-8">
          Te tasamos tu vehículo sin compromiso
        </p>
        <router-link to="/tasacion" class="btn-secondary inline-block text-lg">
          📝 Tasar mi coche
        </router-link>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { formatEUR } from '../utils/format'

const filtroMarca = ref('')
const filtroPrecio = ref('')
const filtroEtiqueta = ref('')

const marcas = ref([])
const vehiculosDestacados = ref([])

onMounted(async () => {
  try {
    const [marcasRes, vehiculosRes] = await Promise.all([
      fetch('/api/marcas/'),
      fetch('/api/vehiculos/')
    ])
    const marcasData = await marcasRes.json()
    const vehiculosData = await vehiculosRes.json()
    marcas.value = marcasData.marcas || []
    vehiculosDestacados.value = (vehiculosData.vehiculos || []).slice(0, 6)
  } catch (e) {
    console.error('Error cargando datos:', e)
  }
})
</script>

