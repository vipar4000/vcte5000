"""
Verifica que el entorno esté realmente listo para producción.

Ejecutar con: python manage.py verificar_produccion

Sale con código 1 si hay algún fallo bloqueante, para poder encadenarlo como
paso de un despliegue. Con --estricto también falla ante avisos.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Comprueba la configuración del entorno antes de dar el sistema por desplegado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--estricto',
            action='store_true',
            help='Falla también ante avisos, no solo ante fallos bloqueantes',
        )

    def handle(self, *args, **options):
        fallos = []
        avisos = []
        correctos = []

        def anotar(condicion, mensaje, es_aviso=False):
            if condicion:
                correctos.append(mensaje)
            elif es_aviso:
                avisos.append(mensaje)
            else:
                fallos.append(mensaje)

        # --- Ajustes de Django -------------------------------------------------
        modulo = os.environ.get('DJANGO_SETTINGS_MODULE', '')
        anotar(
            modulo.endswith('production'),
            f'Ajustes de producción cargados ({modulo or "sin definir"})',
            es_aviso=True,
        )

        anotar(not settings.DEBUG, 'DEBUG desactivado')

        clave = settings.SECRET_KEY or ''
        clave_solida = (
            len(clave) >= 50
            and len(set(clave)) >= 5
            and not clave.startswith('django-insecure-')
        )
        anotar(clave_solida, 'SECRET_KEY larga, aleatoria y sin prefijo inseguro')

        hosts = [h for h in (settings.ALLOWED_HOSTS or []) if h]
        anotar(
            hosts and '*' not in hosts,
            'ALLOWED_HOSTS definido sin comodín *',
        )
        anotar(
            any(h not in ('localhost', '127.0.0.1', '.localhost') for h in hosts),
            'ALLOWED_HOSTS incluye el dominio público',
            es_aviso=True,
        )

        # --- Base de datos -----------------------------------------------------
        motor = settings.DATABASES.get('default', {}).get('ENGINE', '')
        anotar('sqlite' not in motor, f'Base de datos persistente ({motor or "sin motor"})')
        anotar(
            bool(os.environ.get('DATABASE_URL')),
            'DATABASE_URL definida en el entorno',
        )

        # --- Archivos subidos --------------------------------------------------
        # Sin bucket remoto, el host (Render) borra los archivos en cada deploy:
        # facturas, fotos de vehículos y contratos se perderían.
        bucket = os.environ.get('AWS_STORAGE_BUCKET_NAME')
        anotar(
            bool(bucket),
            f'Almacenamiento de media persistente ({bucket or "sin bucket: los archivos se pierden en cada despliegue"})',
        )

        # --- Servicios opcionales ---------------------------------------------
        anotar(
            bool(os.environ.get('REDIS_URL')),
            'REDIS_URL configurada (cache y tareas Celery reales)',
            es_aviso=True,
        )
        anotar(
            bool(settings.EMAIL_HOST_USER) and bool(settings.EMAIL_HOST_PASSWORD),
            'Envío de correo configurado (EMAIL_HOST_USER/PASSWORD)',
            es_aviso=True,
        )

        # --- Seguridad ---------------------------------------------------------
        anotar(settings.SECURE_SSL_REDIRECT, 'Redirección forzada a HTTPS')
        anotar(settings.SESSION_COOKIE_SECURE, 'Cookie de sesión solo por HTTPS')
        anotar(settings.CSRF_COOKIE_SECURE, 'Cookie CSRF solo por HTTPS')
        anotar(
            getattr(settings, 'SECURE_HSTS_SECONDS', 0) > 0,
            'HSTS activo',
        )

        # --- Web pública -------------------------------------------------------
        index_spa = os.path.join(settings.STATIC_ROOT, 'web', 'index.html')
        anotar(
            os.path.exists(index_spa),
            'Web pública compilada en STATIC_ROOT/web/index.html',
            es_aviso=True,
        )

        # --- Informe -----------------------------------------------------------
        for mensaje in correctos:
            self.stdout.write(self.style.SUCCESS(f'  OK     {mensaje}'))
        for mensaje in avisos:
            self.stdout.write(self.style.WARNING(f'  AVISO  {mensaje}'))
        for mensaje in fallos:
            self.stdout.write(self.style.ERROR(f'  FALLA  {mensaje}'))

        self.stdout.write('')
        self.stdout.write(
            f'{len(correctos)} correctos, {len(avisos)} avisos, {len(fallos)} fallos'
        )

        if fallos:
            raise CommandError(
                f'{len(fallos)} fallo(s) bloqueante(s): el entorno NO está listo para producción'
            )
        if options['estricto'] and avisos:
            raise CommandError(
                f'{len(avisos)} aviso(s) con --estricto: revise la configuración'
            )

        self.stdout.write(self.style.SUCCESS('Entorno listo para producción'))
