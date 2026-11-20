<template>
  <div class="py-8 bg-gray-50 min-h-screen">
    <div class="container mx-auto px-4 max-w-3xl">
      <h1 class="text-3xl font-bold text-center mb-2 text-gray-800">📅 Pedir cita</h1>
      <p class="text-center text-gray-600 mb-8">
        Ven a ver el coche sin compromiso. Elige día y hora y te confirmamos la cita.
      </p>

      <!-- Vehículo de interés -->
      <div v-if="vehiculo" class="bg-white rounded-lg shadow-lg p-6 mb-6">
        <h2 class="text-lg font-semibold mb-3">Vehículo que quieres ver</h2>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p class="font-medium text-gray-800">
              {{ vehiculo.marca }} {{ vehiculo.modelo }} ({{ vehiculo.anio }})
            </p>
            <p class="text-sm text-gray-500">{{ vehiculo.kilometraje?.toLocaleString('es-ES') }} km ·
              {{ vehiculo.combustible }}</p>
          </div>
          <p class="text-xl font-bold text-blue-800">{{ formatEUR(vehiculo.precio_venta) }}</p>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Datos de la tienda -->
        <div class="bg-white rounded-lg shadow-lg p-6">
          <h2 class="text-lg font-semibold mb-4">Dónde y cuándo</h2>
          <div class="space-y-4 text-sm">
            <div class="flex items-start gap-3">
              <span class="text-2xl">📍</span>
              <div>
                <p class="font-medium">Calle Brasil 9</p>
                <p class="text-gray-500">28806 Alcalá de Henares (Madrid)</p>
                <a :href="mapaUrl" target="_blank" rel="noopener noreferrer"
                   class="text-eurocar-blue hover:underline">Ver en el mapa →</a>
              </div>
            </div>
            <div class="flex items-start gap-3">
              <span class="text-2xl">🕐</span>
              <div>
                <p class="font-medium">Lunes a viernes: 9:00 - 19:00</p>
                <p class="text-gray-500">Sábados: 10:00 - 14:00</p>
              </div>
            </div>
            <div class="flex items-start gap-3">
              <span class="text-2xl">📞</span>
              <div>
                <a :href="'tel:' + telefono" class="font-medium hover:underline">{{ telefonoVisible }}</a>
                <p class="text-gray-500">Llama si prefieres hablarlo ahora</p>
              </div>
            </div>
          </div>

          <div class="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-900">
            <strong>La reserva se formaliza en la tienda.</strong>
            Cuando vengas a ver el coche y decidas quedártelo, el vendedor registra la reserva con la
            señal en el sistema. No se paga nada por internet.
          </div>
        </div>

        <!-- Formulario de cita -->
        <div class="bg-white rounded-lg shadow-lg p-6">
          <h2 class="text-lg font-semibold mb-4">Pide tu cita</h2>

          <form v-if="!solicitudEnviada" @submit.prevent="pedirCita" class="space-y-3">
            <input v-model="form.nombre" type="text" placeholder="Tu nombre *" required
                   class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
            <input v-model="form.telefono" type="tel" placeholder="Tu teléfono *" required
                   class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
            <input v-model="form.email" type="email" placeholder="Tu email (opcional)"
                   class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
            <div class="grid grid-cols-2 gap-3">
              <input v-model="form.fecha" type="date" required
                     :min="hoy" class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
              <select v-model="form.franja" required
                      class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
                <option value="">Franja horaria *</option>
                <option value="Mañana (9:00 - 14:00)">Mañana (9:00 - 14:00)</option>
                <option value="Tarde (16:00 - 19:00)">Tarde (16:00 - 19:00)</option>
                <option value="Sábado por la mañana">Sábado por la mañana</option>
              </select>
            </div>
            <textarea v-model="form.mensaje" rows="3" placeholder="¿Algo que debamos saber? (opcional)"
                      class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light"></textarea>
            <button type="submit" class="btn-primary w-full">📅 Solicitar cita</button>
            <p class="text-xs text-gray-500">
              Al enviar se abrirá tu correo con la solicitud redactada. También puedes llamarnos.
            </p>
          </form>

          <!-- Confirmación -->
          <div v-else class="space-y-4">
            <div class="bg-green-50 border border-green-200 rounded-lg p-4">
              <p class="text-green-800 font-medium">✅ Solicitud preparada</p>
              <p class="text-sm text-green-700 mt-1">
                Se ha abierto tu correo con los datos. Envíalo y te confirmamos la cita.
              </p>
            </div>
            <div class="text-sm bg-gray-50 rounded-lg p-4 space-y-1">
              <p><span class="text-gray-500">Nombre:</span> {{ form.nombre }}</p>
              <p><span class="text-gray-500">Teléfono:</span> {{ form.telefono }}</p>
              <p><span class="text-gray-500">Fecha:</span> {{ form.fecha }} · {{ form.franja }}</p>
              <p v-if="vehiculo">
                <span class="text-gray-500">Vehículo:</span>
                {{ vehiculo.marca }} {{ vehiculo.modelo }}
              </p>
            </div>
            <div class="flex gap-3">
              <a :href="mailtoUrl" class="btn-primary flex-1 text-center">✉️ Abrir el correo otra vez</a>
              <a :href="'tel:' + telefono" class="flex-1 text-center px-4 py-2 border rounded-lg hover:bg-gray-50">
                📞 Llamar
              </a>
            </div>
            <button type="button" @click="reiniciar" class="text-sm text-gray-500 hover:underline w-full text-center">
              Pedir otra cita
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { formatEUR } from '../utils/format'

const route = useRoute()

const EMAIL = 'vipar4000@gmail.com'
const telefono = '+34722817617'
const telefonoVisible = '+34 722 81 7617'
const mapaUrl = 'https://www.google.com/maps/search/?api=1&query=Calle+Brasil+9,+28806+Alcal%C3%A1+de+Henares'

const vehiculo = ref(null)
const solicitudEnviada = ref(false)

const form = reactive({
  nombre: '',
  telefono: '',
  email: '',
  fecha: '',
  franja: '',
  mensaje: '',
})

const hoy = computed(() => new Date().toISOString().split('T')[0])

const textoCita = computed(() => {
  const lineas = [
    'Hola, quiero pedir cita para ver un vehículo.',
    '',
    `Nombre: ${form.nombre}`,
    `Teléfono: ${form.telefono}`,
  ]
  if (form.email) lineas.push(`Email: ${form.email}`)
  lineas.push(`Fecha preferida: ${form.fecha}`)
  lineas.push(`Franja: ${form.franja}`)
  if (vehiculo.value) {
    lineas.push(`Vehículo: ${vehiculo.value.marca} ${vehiculo.value.modelo} (${vehiculo.value.anio})`)
    lineas.push(`Precio publicado: ${formatEUR(vehiculo.value.precio_venta)}`)
  }
  if (form.mensaje) {
    lineas.push('', `Comentario: ${form.mensaje}`)
  }
  return lineas.join('\n')
})

const mailtoUrl = computed(() => {
  const asunto = vehiculo.value
    ? `Cita para ver ${vehiculo.value.marca} ${vehiculo.value.modelo}`
    : 'Solicitud de cita'
  return `mailto:${EMAIL}?subject=${encodeURIComponent(asunto)}&body=${encodeURIComponent(textoCita.value)}`
})

const pedirCita = () => {
  solicitudEnviada.value = true
  window.location.href = mailtoUrl.value
}

const reiniciar = () => {
  solicitudEnviada.value = false
  form.nombre = ''
  form.telefono = ''
  form.email = ''
  form.fecha = ''
  form.franja = ''
  form.mensaje = ''
}

onMounted(async () => {
  const id = route.query.vehiculo
  if (!id) return
  try {
    const res = await fetch(`/api/vehiculos/${id}/`)
    if (res.ok) vehiculo.value = await res.json()
  } catch (e) {
    // Si falla, la cita se puede pedir igualmente sin el vehículo
  }
})
</script>
