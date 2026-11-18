from .base import *
import os

DEBUG = True

# `base.py` aplica los ajustes de seguridad de producción cuando el entorno no
# define DEBUG (por ejemplo en un clon sin backend/.env). Como aquí forzamos
# DEBUG después de importar base, hay que desactivarlos explícitamente: si no,
# el servidor de desarrollo redirige a HTTPS (301) y el navegador no puede
# entrar al ERP. Se refuerzan aquí, además del valor de DEBUG.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', 'testserver']

# Use SQLite for local dev, PostgreSQL when DATABASE_URL is set (Docker)
if os.environ.get('DATABASE_URL'):
    # Docker / PostgreSQL - use base settings (reads DATABASE_URL)
    DATABASES = {
        'default': env.db('DATABASE_URL'),
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }

# debug_toolbar removed - incompatible with Python 3.14

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# CORS allow all in development
CORS_ALLOW_ALL_ORIGINS = True

# Less strict password validation in development
AUTH_PASSWORD_VALIDATORS = []

# Logging
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
            'level': 'DEBUG',
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}
