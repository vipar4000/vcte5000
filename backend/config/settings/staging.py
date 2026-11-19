from .base import *
import os

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

# --- Media (PDFs de facturas, contratos, fotos) ------------------------------
# Sin bucket, los archivos van al disco local de Render (efímero) y esta
# bandera permite que la propia app los sirva en /media/ durante las pruebas:
# sin ella, con DEBUG=False cualquier PDF daba 404.
SERVE_MEDIA_LOCAL = True

# Si se define AWS_STORAGE_BUCKET_NAME, se usa R2/S3 igual que en producción y
# los archivos persisten entre despliegues (mismo bloque que production.py).
if os.environ.get('AWS_STORAGE_BUCKET_NAME'):
    DEFAULT_FILE_STORAGE = 'storages.backends.s3.S3Storage'
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ACCESS_KEY_ID = os.environ.get('AWS_S3_ACCESS_KEY_ID') or os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_S3_SECRET_ACCESS_KEY = os.environ.get('AWS_S3_SECRET_ACCESS_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL', '')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'auto')
    AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN', '')
    AWS_DEFAULT_ACL = os.environ.get('AWS_S3_DEFAULT_ACL', None)
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False
    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'
    elif AWS_S3_ENDPOINT_URL:
        MEDIA_URL = f'{AWS_S3_ENDPOINT_URL.rstrip("/")}/{AWS_STORAGE_BUCKET_NAME}/'
    else:
        MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/'
    # Con bucket la media no la sirve la app
    SERVE_MEDIA_LOCAL = False

# Render proxy SSL — necesario para que Django detecte HTTPS detrás del proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Email backend para staging (consola/logs)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
