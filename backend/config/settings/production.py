import os
import dj_database_url
from .base import *

DEBUG = False

# La aplicación NO sirve /media/ en producción: los archivos subidos deben ir a
# S3/R2 (MEDIA_URL apunta al bucket). El disco de Render es efímero, así que
# servirlos desde aquí daría enlaces que se rompen en el siguiente despliegue.
SERVE_MEDIA_LOCAL = False

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '.onrender.com').split(',')

# Origenes de confianza para CSRF. Es opcional: solo hace falta si el sitio se
# sirve desde varios dominios a la vez (por ejemplo rogil.co y www.rogil.co) o
# si hay un proxy por delante que no conserva el Host original. Formato:
#   CSRF_TRUSTED_ORIGINS=https://rogil.co,https://www.rogil.co
_csrf_origenes = os.environ.get('CSRF_TRUSTED_ORIGINS', '').strip()
if _csrf_origenes:
    CSRF_TRUSTED_ORIGINS = [
        origen.strip() for origen in _csrf_origenes.split(',') if origen.strip()
    ]

# Database via Render DATABASE_URL
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Production security settings
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# El preload de HSTS se puede desactivar por entorno (HSTS_PRELOAD=false).
# Mientras se use un dominio temporal conviene dejarlo en false: incluir un
# dominio en la lista de preload de los navegadores es practicamente
# irreversible durante un año.
SECURE_HSTS_PRELOAD = os.environ.get('HSTS_PRELOAD', 'True').lower() not in (
    'false', '0', 'no'
)
SECURE_HSTS_SECONDS = 31536000
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'

# Static files whitenoise
# Sin manifest: los assets de la SPA Vue (backend/static/web) se referencian
# por nombre en index.html; el manifest renombraría los archivos y rompería la SPA.
MIDDLEWARE.insert(0, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Media storage (S3-compatible: R2, B2, Wasabi, AWS S3) - solo activo si hay bucket
if os.environ.get('AWS_STORAGE_BUCKET_NAME'):
    DEFAULT_FILE_STORAGE = 'storages.backends.s3.S3Storage'
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ACCESS_KEY_ID = os.environ.get('AWS_S3_ACCESS_KEY_ID') or os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_S3_SECRET_ACCESS_KEY = os.environ.get('AWS_S3_SECRET_ACCESS_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL', '')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'auto')
    AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN', '')
    # R2 y otros proveedores S3-compatible no usan ACL de objeto; el acceso público se configura a nivel de bucket.
    AWS_DEFAULT_ACL = os.environ.get('AWS_S3_DEFAULT_ACL', None)
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False
    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'
    elif AWS_S3_ENDPOINT_URL:
        MEDIA_URL = f'{AWS_S3_ENDPOINT_URL.rstrip("/")}/{AWS_STORAGE_BUCKET_NAME}/'
    else:
        MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/'

# Redis opcional: si REDIS_URL no existe, degradar a locmem + Celery eager (como staging)
if not os.environ.get('REDIS_URL'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'production-cache',
        }
    }
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_BROKER_URL = None
    CELERY_RESULT_BACKEND = None

# Email via SMTP
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'R Car Rogil <vipar4000@gmail.com>')

# Logging to console (Render captures stdout)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'apps': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    },
}
