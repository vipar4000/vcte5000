<template>
  <div class="py-8">
    <div class="container mx-auto px-4">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-gray-800">Catálogo de Vehículos</h1>
        <p class="text-gray-500">{{ vehiculos.length }} vehículos disponibles</p>
      </div>
      
      <!-- Filters -->
      <div class="bg-white rounded-lg shadow p-4 mb-8">
        <div class="flex flex-wrap gap-4">
          <input v-model="busqueda" 
                 type="text" 
                 placeholder="Buscar por marca, modelo..."
                 class="flex-1 min-w-[200px] px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
          
          <select v-model="filtroMarca" class="px-4 py-2 border rounded-lg">
            <option value="">Todas las marcas</option>
            <option v-for="marca in marcas" :key="marca" :value="marca">{{ marca }}</option>
          </select>
          
          <select v-model="filtroPrecio" class="px-4 py-2 border rounded-lg">
            <option value="">Cualquier precio</option>
            <option value="0-5000">Hasta €5.000</option>
            <option value="5000-10000">€5.000 - €10.000</option>
            <option value="10000-20000">€10.000 - €20.000</option>
            <option value="20000-999999">Más de €20.000</option>
          </select>
          
          <select v-model="filtroEtiqueta" class="px-4 py-2 border rounded-lg">
            <option value="">Cualquier etiqueta</option>
            <option value="0">Cero emisiones (0)</option>
            <option value="ECO">ECO</option>
            <option value="B">B</option>
            <option value="C">C</option>
          </select>
        </div>
      </div>
      
      <!-- Results -->
      <div v-if="loading" class="text-center py-12">
        <p class="text-gray-500 text-lg">Cargando vehículos...</p>
      </div>
      <div v-else-if="vehiculosFiltrados.length === 0" class="text-center py-12">
        <p class="text-gray-500 text-lg">No se encontraron vehículos con esos filtros</p>
        <button @click="limpiarFiltros" class="mt-4 text-eurocar-light hover:underline">
          Limpiar filtros
        </button>
      </div>
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div v-for="vehiculo in vehiculosFiltrados" :key="vehiculo.id" 
             class="bg-white rounded-lg shadow-lg overflow-hidden card-hover transition-all duration-300">
          <!-- Carousel de imágenes -->
          <div class="relative h-48 bg-gray-200 overflow-hidden group">
            <div :ref="el => { if (el) carouselRefs[vehiculo.id] = el }"
                 class="flex h-full overflow-x-auto snap-x snap-mandatory scrollbar-hide"
                 style="-ms-overflow-style:none; scrollbar-width:none;">
              <!-- Imagen principal -->
              <div class="min-w-full h-full snap-center flex-shrink-0">
                <img v-if="vehiculo.imagen_url" :src="vehiculo.imagen_url" 
                     :alt="vehiculo.marca + ' ' + vehiculo.modelo" 
                     class="w-full h-full object-contain bg-white">
                <span v-else class="text-6xl flex items-center justify-center h-full">🚗</span>
              </div>
              <!-- Imágenes adicionales -->
              <div v-for="(img, idx) in (vehiculo.imagenes_urls || [])" :key="idx" 
                   class="min-w-full h-full snap-center flex-shrink-0">
                <img :src="img" :alt="vehiculo.marca + ' ' + vehiculo.modelo + ' (' + (idx+2) + ')'" 
                     class="w-full h-full object-contain bg-white">
              </div>
            </div>
            <!-- Flechas -->
            <template v-if="(vehiculo.imagenes_urls || []).length > 0">
              <button @click="prevImage(vehiculo.id)" 
                      class="absolute left-1 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/60 text-white rounded-full w-7 h-7 flex items-center justify-center text-sm opacity-0 group-hover:opacity-100 transition-opacity">
                ‹
              </button>
              <button @click="nextImage(vehiculo.id, (vehiculo.imagenes_urls || []).length + 1)" 
                      class="absolute right-1 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/60 text-white rounded-full w-7 h-7 flex items-center justify-center text-sm opacity-0 group-hover:opacity-100 transition-opacity">
                ›
              </button>
              <!-- Dots -->
              <div class="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1">
                <span v-for="i in (vehiculo.imagenes_urls || []).length + 1" :key="i"
                      class="w-1.5 h-1.5 rounded-full bg-white/50"
                      :class="{'bg-white': carouselIndexes[vehiculo.id] === i-1}">
                </span>
              </div>
            </template>
          </div>
          <div class="p-6">
            <div class="flex justify-between items-start mb-2">
              <h3 class="text-xl font-bold text-gray-800">{{ vehiculo.marca }} {{ vehiculo.modelo }}</h3>
              <span class="px-2 py-1 text-xs rounded-full bg-eurocar-light text-white">
                {{ vehiculo.etiqueta_ambiental }}
              </span>
            </div>
            <p class="text-gray-500 text-sm mb-4">{{ vehiculo.anio }} | {{ vehiculo.kilometraje }} km | {{ vehiculo.combustible }}</p>
            <div class="flex justify-between items-center">
              <span class="text-2xl font-bold text-eurocar-blue">{{ formatEUR(vehiculo.precio_venta) }}</span>
              <router-link :to="`/vehiculo/${vehiculo.id}`" class="text-eurocar-light hover:underline">
                Ver detalles →
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { formatEUR } from '../utils/format'

const busqueda = ref('')
const filtroMarca = ref('')
const filtroPrecio = ref('')
const filtroEtiqueta = ref('')
const loading = ref(true)

const marcas = ref([])
const vehiculos = ref([])
const carouselRefs = ref({})
const carouselIndexes = ref({})

onMounted(async () => {
  try {
    const res = await fetch('/api/vehiculos/')
    const data = await res.json()
    vehiculos.value = data.vehiculos
    marcas.value = [...new Set(data.vehiculos.map(v => v.marca))].sort()
    // Inicializar índices
    data.vehiculos.forEach(v => { carouselIndexes.value[v.id] = 0 })
  } catch (e) {
    console.error('Error cargando vehículos:', e)
  } finally {
    loading.value = false
  }
})

const nextImage = (id, total) => {
  const el = carouselRefs.value[id]
  if (!el) return
  const current = carouselIndexes.value[id] || 0
  const next = (current + 1) % total
  carouselIndexes.value[id] = next
  el.scrollTo({ left: next * el.clientWidth, behavior: 'smooth' })
}

const prevImage = (id) => {
  const el = carouselRefs.value[id]
  if (!el) return
  const current = carouselIndexes.value[id] || 0
  const total = el.children.length
  const prev = (current - 1 + total) % total
  carouselIndexes.value[id] = prev
  el.scrollTo({ left: prev * el.clientWidth, behavior: 'smooth' })
}

const combustibleMap = {
  'GASOLINA': 'Gasolina',
  'DIESEL': 'Diésel',
  'HIBRIDO': 'Híbrido',
  'ELECTRICO': 'Eléctrico',
  'GAS_LPG': 'Gas (LPG)',
  'GAS_CNG': 'Gas (CNG)',
}

const vehiculosFiltrados = computed(() => {
  return vehiculos.value.filter(v => {
    const matchBusqueda = !busqueda.value || 
      v.marca.toLowerCase().includes(busqueda.value.toLowerCase()) ||
      v.modelo.toLowerCase().includes(busqueda.value.toLowerCase())
    
    const matchMarca = !filtroMarca.value || v.marca === filtroMarca.value
    
    const matchEtiqueta = !filtroEtiqueta.value || v.etiqueta_ambiental === filtroEtiqueta.value
    
    let matchPrecio = true
    if (filtroPrecio.value) {
      const [min, max] = filtroPrecio.value.split('-').map(Number)
      matchPrecio = v.precio_venta >= min && v.precio_venta <= max
    }
    
    return matchBusqueda && matchMarca && matchEtiqueta && matchPrecio
  })
})

const limpiarFiltros = () => {
  busqueda.value = ''
  filtroMarca.value = ''
  filtroPrecio.value = ''
  filtroEtiqueta.value = ''
}
</script>
