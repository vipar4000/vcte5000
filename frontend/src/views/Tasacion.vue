<template>
  <div class="py-8 bg-gray-50 min-h-screen">
    <div class="container mx-auto px-4 max-w-2xl">
      <h1 class="text-3xl font-bold text-center mb-8 text-gray-800">
        📝 Tasamos tu coche
      </h1>
      
      <div class="bg-white rounded-lg shadow-lg p-8">
        <p class="text-gray-600 mb-6">
          Rellena el formulario y te daremos una tasación de tu vehículo sin compromiso.
        </p>
        
        <form @submit.prevent="enviarTasacion" class="space-y-6">
          <!-- Datos del vehículo -->
          <div>
            <h2 class="text-lg font-semibold mb-4">🚗 Datos del vehículo</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Marca *</label>
                <input v-model="form.marca" type="text" required
                       class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Modelo *</label>
                <input v-model="form.modelo" type="text" required
                       class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Año *</label>
                <input v-model="form.anio" type="number" required min="1990" max="2030"
                       class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Kilometraje *</label>
                <input v-model="form.kilometraje" type="number" required min="0"
                       class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Combustible *</label>
                <select v-model="form.combustible" required
                        class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
                  <option value="">Seleccionar...</option>
                  <option value="gasolina">Gasolina</option>
                  <option value="diesel">Diésel</option>
                  <option value="hibrido">Híbrido</option>
                  <option value="electrico">Eléctrico</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Matrícula</label>
                <input v-model="form.matricula" type="text"
                       class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light"
                       placeholder="1234ABC">
              </div>
            </div>
          </div>
          
          <!-- Datos de contacto -->
          <div>
            <h2 class="text-lg font-semibold mb-4">👤 Tus datos</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">Nombre completo *</label>
                <input v-model="form.nombre" type="text" required
                       class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Teléfono *</label>
                <input v-model="form.telefono" type="tel" required
                       class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Email *</label>
                <input v-model="form.email" type="email" required
                       class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
              </div>
            </div>
          </div>
          
          <!-- Submit -->
          <div class="text-center">
            <button type="submit" class="btn-secondary text-lg px-8 py-4">
              📨 Enviar tasación
            </button>
            <p class="text-sm text-gray-500 mt-2">
              Te contactaremos en menos de 24 horas
            </p>
          </div>
        </form>
        
        <!-- Success message -->
        <div v-if="enviado" class="mt-6 bg-green-50 border border-green-200 rounded-lg p-4 text-center">
          <p class="text-green-800 font-medium">✅ ¡Formulario enviado correctamente!</p>
          <p class="text-green-600 text-sm">Te contactaremos pronto.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'

const enviado = ref(false)

const form = reactive({
  marca: '',
  modelo: '',
  anio: '',
  kilometraje: '',
  combustible: '',
  matricula: '',
  nombre: '',
  telefono: '',
  email: '',
})

const enviarTasacion = () => {
  // TODO: Send to backend API
  console.log('Tasación enviada:', form)
  enviado.value = true
}
</script>
