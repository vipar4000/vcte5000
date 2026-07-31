from .development import *

# Staging settings for Render deployment (no Redis, no async tasks)
# Redis no está disponible en el plan Starter de Render — usamos caché en memoria
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'staging-cache',
    }
}

# Ejecutar tareas Celery de forma síncrona (sin worker, sin Redis)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_BROKER_URL = None
CELERY_RESULT_BACKEND = None

# development.py hardcodea ALLOWED_HOSTS a solo localhost — sobrescribimos
# para que Render (render.yaml) pueda controlarlo via env var
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# DEBUG desde env (render.yaml lo fija a False)
DEBUG = env('DEBUG')

# Servir estáticos con WhiteNoise (necesario cuando DEBUG=False)
MIDDLEWARE.insert(0, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
