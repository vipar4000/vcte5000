from .base import *

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

# Servir estáticos con WhiteNoise (necesario cuando DEBUG=False)
# Sin manifest: los assets de la SPA Vue (backend/static/web) se referencian
# por nombre en index.html; el manifest renombraría los archivos y rompería la SPA.
MIDDLEWARE.insert(0, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Render proxy SSL — necesario para que Django detecte HTTPS detrás del proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Email backend para staging (consola/logs)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
