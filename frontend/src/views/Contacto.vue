<template>
  <div class="py-8 bg-gray-50 min-h-screen">
    <div class="container mx-auto px-4 max-w-2xl">
      <h1 class="text-3xl font-bold text-center mb-8 text-gray-800">
        📞 Contacto
      </h1>
      
      <div class="bg-white rounded-lg shadow-lg p-8">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
          <!-- Contact Info -->
          <div>
            <h2 class="text-lg font-semibold mb-4">Información de contacto</h2>
            <div class="space-y-4">
              <div class="flex items-center gap-3">
                <span class="text-2xl">📞</span>
                <div>
                  <p class="font-medium">+34 722 81 7617</p>
                  <p class="text-sm text-gray-500">Lunes - Sábado</p>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-2xl">📧</span>
                <div>
                  <p class="font-medium">info@rcarrogil.com</p>
                  <p class="text-sm text-gray-500">Respuesta en 24h</p>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-2xl">📍</span>
                <div>
                  <p class="font-medium">Calle Brasil 9</p>
                  <p class="text-sm text-gray-500">28806 Alcalá de Henares</p>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-2xl">🕐</span>
                <div>
                  <p class="font-medium">Lun - Vie: 9:00 - 19:00</p>
                  <p class="text-sm text-gray-500">Sáb: 10:00 - 14:00</p>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Contact Form -->
          <div>
            <h2 class="text-lg font-semibold mb-4">Envíanos un mensaje</h2>
            <form @submit.prevent="enviarMensaje" class="space-y-4">
              <div>
                <input v-model="form.nombre" type="text" placeholder="Tu nombre" required
                       class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
              </div>
              <div>
                <input v-model="form.email" type="email" placeholder="Tu email" required
                       class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
              </div>
              <div>
                <input v-model="form.asunto" type="text" placeholder="Asunto" required
                       class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light">
              </div>
              <div>
                <textarea v-model="form.mensaje" placeholder="Tu mensaje" rows="4" required
                          class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-eurocar-light"></textarea>
              </div>
              <button type="submit" class="btn-primary w-full">
                📨 Enviar mensaje
              </button>
            </form>
            
            <div v-if="enviado" class="mt-4 bg-green-50 border border-green-200 rounded-lg p-3 text-center">
              <p class="text-green-800 text-sm">✅ Mensaje enviado correctamente</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'

const enviado = ref(false)

const form = reactive({
  nombre: '',
  email: '',
  asunto: '',
  mensaje: '',
})

const enviarMensaje = () => {
  // TODO: Send to backend API
  console.log('Mensaje enviado:', form)
  enviado.value = true
}
</script>
