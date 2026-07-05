<template>
  <div class="py-8">
    <div class="max-w-6xl mx-auto px-4">
      <!-- Back link -->
      <router-link to="/catalogo" class="text-eurocar-light hover:underline mb-6 inline-block text-sm">
        &larr; Volver al catálogo
      </router-link>

      <div v-if="loading" class="text-center py-12">
        <p class="text-gray-500 text-lg">Cargando vehículo...</p>
      </div>

      <div v-else-if="error" class="text-center py-12">
        <p class="text-red-500 text-lg">{{ error }}</p>
      </div>

      <!-- Bloque principal: Galería + Panel de datos -->
      <div v-else class="car-listing-container">

        <!-- Bloque 1: Galería Interactiva -->
        <div class="product-gallery">
          <!-- Imagen principal -->
          <div class="main-display">
            <img v-if="todasImagenes[0]"
                 :src="todasImagenes[0]"
                 :alt="vehiculo.marca + ' ' + vehiculo.modelo"
                 class="featured-image"
                 loading="eager"
                 @click="openLightbox(selectedImage)">
            <div v-else class="no-image-placeholder">
              <span class="text-8xl">🚗</span>
            </div>
          </div>

          <!-- Thumbnails -->
          <div v-if="todasImagenes.length > 1" class="thumbnails-container">
            <img v-for="(img, idx) in todasImagenes"
                 :key="idx"
                 :src="img"
                 :alt="'Imagen ' + (idx + 1)"
                 class="thumb"
                 :class="{ active: selectedImage === idx }"
                 :loading="idx === 0 ? 'eager' : 'lazy'"
                 @click="selectImage(idx)">
          </div>
        </div>

        <!-- Bloque 2: Panel de Especificaciones Técnicas -->
        <div class="car-details-panel">
          <h1 class="car-title">{{ vehiculo.marca }} {{ vehiculo.modelo }}</h1>
          <div class="car-price-tag">{{ formatEUR(vehiculo.precio_venta) }}</div>
          <p class="car-subtitle">Estado garantizado · Papeles al día · Revisión mecánica aprobada</p>

          <div class="specs-grid">
            <div class="spec-item">
              <span class="spec-label">Año</span>
              <span class="spec-value">{{ vehiculo.anio }}</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">Kilometraje</span>
              <span class="spec-value">{{ vehiculo.kilometraje?.toLocaleString('es-ES') }} km</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">Combustible</span>
              <span class="spec-value">{{ vehiculo.combustible }}</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">Etiqueta</span>
              <span class="spec-value">{{ vehiculo.etiqueta_ambiental }}</span>
            </div>
          </div>

          <!-- Botón WhatsApp -->
          <a :href="whatsappUrl" target="_blank" rel="noopener noreferrer" class="btn-contact">
            📞 Contactar por WhatsApp
          </a>

          <!-- Garantía -->
          <div class="guarantee-badge">
            <span>🛡️ Garantía de 1 año incluida · Según Real Decreto-ley 7/2021</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Bloque 3: Lightbox Modal -->
    <Teleport to="body">
      <div v-if="lightboxOpen"
           class="modal-overlay"
           @click.self="closeLightbox"
           @keydown.esc="closeLightbox"
           tabindex="0"
           ref="modalRef">
        <span class="close-btn" @click="closeLightbox">&times;</span>
        <button v-if="todasImagenes.length > 1"
                class="nav-btn prev-btn"
                aria-label="Anterior"
                @click.stop="prevLightbox">&#10094;</button>
        <div class="zoom-container"
             @mousemove="onMouseMove"
             @mouseleave="onMouseLeave">
          <img :src="todasImagenes[lightboxIndex]"
               :alt="vehiculo.marca + ' ' + vehiculo.modelo"
               class="lightbox-img"
               :style="zoomStyle">
        </div>
        <button v-if="todasImagenes.length > 1"
                class="nav-btn next-btn"
                aria-label="Siguiente"
                @click.stop="nextLightbox">&#10095;</button>
        <div class="lightbox-counter">
          {{ lightboxIndex + 1 }} / {{ todasImagenes.length }}
        </div>
        <div class="lightbox-hint">
          Hover para zoom · ← → navegar · ESC cerrar
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { formatEUR } from '../utils/format'
import { useRoute } from 'vue-router'

const route = useRoute()

const vehiculo = ref({})
const loading = ref(true)
const error = ref(null)
const selectedImage = ref(0)

const lightboxOpen = ref(false)
const lightboxIndex = ref(0)
const modalRef = ref(null)

const zoomX = ref(50)
const zoomY = ref(50)
const isZooming = ref(false)

const todasImagenes = computed(() => {
  const imgs = []
  if (vehiculo.value.imagen) imgs.push(vehiculo.value.imagen)
  if (vehiculo.value.imagenes) {
    vehiculo.value.imagenes.forEach(img => imgs.push(img.url))
  }
  return imgs
})

const zoomStyle = computed(() => ({
  transformOrigin: `${zoomX.value}% ${zoomY.value}%`,
  transform: isZooming.value ? 'scale(2.5)' : 'scale(1)',
  transition: isZooming.value ? 'none' : 'transform 0.15s ease-out'
}))

const selectImage = (idx) => {
  selectedImage.value = idx
  const el = document.querySelector('.featured-image')
  if (el && todasImagenes.value[idx]) {
    el.src = todasImagenes.value[idx]
  }
}

const openLightbox = (index) => {
  lightboxIndex.value = index
  lightboxOpen.value = true
  isZooming.value = false
}

const closeLightbox = () => {
  lightboxOpen.value = false
  isZooming.value = false
}

const nextLightbox = () => {
  lightboxIndex.value = (lightboxIndex.value + 1) % todasImagenes.value.length
  selectedImage.value = lightboxIndex.value
  isZooming.value = false
}

const prevLightbox = () => {
  lightboxIndex.value = (lightboxIndex.value - 1 + todasImagenes.value.length) % todasImagenes.value.length
  selectedImage.value = lightboxIndex.value
  isZooming.value = false
}

const onMouseMove = (e) => {
  const rect = e.target.getBoundingClientRect()
  zoomX.value = ((e.clientX - rect.left) / rect.width) * 100
  zoomY.value = ((e.clientY - rect.top) / rect.height) * 100
  isZooming.value = true
}

const onMouseLeave = () => {
  isZooming.value = false
}

const whatsappUrl = computed(() => {
  const tel = '34722817617'
  const msg = `Hola, estoy interesado en el auto que vi en su sitio web:\n\n🚗 *Vehículo:* ${vehiculo.value.marca} ${vehiculo.value.modelo}\n💰 *Precio:* ${formatEUR(vehiculo.value.precio_venta)}\n\n¿Sigue disponible? Me gustaría agendar una cita para verlo.`
  return `https://wa.me/${tel}?text=${encodeURIComponent(msg)}`
})

const handleKeydown = (e) => {
  if (!lightboxOpen.value) return
  if (e.key === 'Escape') closeLightbox()
  if (e.key === 'ArrowRight') nextLightbox()
  if (e.key === 'ArrowLeft') prevLightbox()
}

onMounted(async () => {
  try {
    const res = await fetch(`/api/vehiculos/${route.params.id}/`)
    if (!res.ok) throw new Error('Vehículo no encontrado')
    vehiculo.value = await res.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.car-listing-container {
  display: flex;
  flex-direction: row;
  gap: 40px;
  max-width: 1200px;
  margin: 0 auto;
}
.product-gallery {
  display: flex;
  flex-direction: column;
  gap: 15px;
  flex: 1.2;
}
.main-display {
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  background: #fff;
}
.featured-image {
  width: 100%;
  height: auto;
  cursor: zoom-in;
  display: block;
  object-fit: contain;
}
.no-image-placeholder {
  width: 100%;
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f3f4f6;
  border-radius: 8px;
}
.thumbnails-container {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 4px;
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.thumbnails-container::-webkit-scrollbar {
  display: none;
}
.thumb {
  width: 90px;
  height: 65px;
  object-fit: cover;
  cursor: pointer;
  opacity: 0.5;
  border: 2px solid transparent;
  border-radius: 4px;
  transition: all 0.2s ease;
  flex-shrink: 0;
}
.thumb.active, .thumb:hover {
  opacity: 1;
  border-color: #3b82f6;
}
.car-details-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.car-title {
  font-size: 28px;
  color: #1a1a1a;
  margin: 0 0 10px 0;
  font-weight: 700;
}
.car-price-tag {
  font-size: 32px;
  font-weight: bold;
  color: #1e40af;
  margin-bottom: 5px;
}
.car-subtitle {
  color: #6c757d;
  font-size: 14px;
  margin: 0 0 25px 0;
}
.specs-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
  margin-bottom: 30px;
}
.spec-item {
  background: #f8f9fa;
  padding: 12px 15px;
  border-radius: 6px;
  border-left: 4px solid #3b82f6;
}
.spec-label {
  display: block;
  font-size: 11px;
  color: #777;
  text-transform: uppercase;
  margin-bottom: 4px;
  letter-spacing: 0.5px;
}
.spec-value {
  font-size: 16px;
  font-weight: 600;
  color: #212529;
}
.btn-contact {
  display: block;
  background: #25d366;
  color: white;
  border: none;
  padding: 16px;
  font-size: 16px;
  font-weight: bold;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s ease;
  text-align: center;
  text-decoration: none;
  margin-bottom: 20px;
}
.btn-contact:hover {
  background: #1da851;
}
.guarantee-badge {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  padding: 12px 16px;
  color: #166534;
  font-size: 14px;
}
.modal-overlay {
  display: flex;
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  background: rgba(0, 0, 0, 0.95);
  z-index: 2000;
  justify-content: center;
  align-items: center;
  outline: none;
}
.close-btn {
  position: absolute;
  top: 20px; right: 30px;
  color: white;
  font-size: 45px;
  cursor: pointer;
  user-select: none;
  z-index: 2010;
  line-height: 1;
}
.close-btn:hover {
  color: #ccc;
}
.zoom-container {
  overflow: hidden;
  max-width: 85%;
  max-height: 85%;
  border-radius: 4px;
  cursor: move;
}
.lightbox-img {
  width: 100%;
  height: auto;
  display: block;
}
.nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.1);
  color: white;
  border: none;
  font-size: 32px;
  padding: 15px 22px;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.2s;
  z-index: 2010;
  user-select: none;
}
.nav-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}
.prev-btn { left: 25px; }
.next-btn { right: 25px; }
.lightbox-counter {
  position: absolute;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.5);
  color: white;
  padding: 8px 20px;
  border-radius: 20px;
  font-size: 14px;
  z-index: 2010;
}
.lightbox-hint {
  position: absolute;
  top: 25px;
  left: 30px;
  background: rgba(0, 0, 0, 0.5);
  color: white;
  padding: 6px 14px;
  border-radius: 15px;
  font-size: 12px;
  z-index: 2010;
}
@media (max-width: 768px) {
  .car-listing-container {
    flex-direction: column;
    gap: 25px;
  }
  .specs-grid {
    grid-template-columns: 1fr;
  }
  .nav-btn {
    padding: 10px 15px;
    font-size: 24px;
  }
  .prev-btn { left: 10px; }
  .next-btn { right: 10px; }
  .zoom-container {
    max-width: 95%;
  }
}
</style>