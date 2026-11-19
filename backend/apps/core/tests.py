"""Comprobaciones de configuración y del servicio de media.

Dos regresiones que ya ocurrieron:

1. Sin `backend/.env`, `base.py` no ve `DEBUG` y aplica los ajustes de
   producción (HTTPS obligatorio), mientras que `development.py` pone
   `DEBUG = True` después de importar base. Resultado: el servidor de
   desarrollo redirigía a HTTPS y el login quedaba inaccesible.
2. Con `DEBUG = False` (staging/producción) Django no sirve `/media/`, así que
   los PDFs adjuntos daban 404. Ahora la ruta existe siempre y solo responde
   cuando el entorno lo autoriza (`SERVE_MEDIA_LOCAL`), pensado para staging
   mientras no haya bucket S3/R2.
"""
import os
import shutil
import tempfile

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings


class AjustesDesarrolloTest(SimpleTestCase):
    def test_desarrollo_no_fuerza_https(self):
        # Nota: el runner de tests pone DEBUG=False durante la ejecución, así que
        # aquí solo se comprueban los ajustes de seguridad, que development.py
        # fija explícitamente.
        self.assertFalse(
            settings.SECURE_SSL_REDIRECT,
            'El servidor de desarrollo no debe redirigir a HTTPS',
        )
        self.assertFalse(
            settings.SESSION_COOKIE_SECURE,
            'En desarrollo la cookie de sesión debe viajar por HTTP',
        )
        self.assertFalse(settings.CSRF_COOKIE_SECURE)

    def test_desarrollo_no_envia_hsts(self):
        self.assertEqual(getattr(settings, 'SECURE_HSTS_SECONDS', 0), 0)
        self.assertFalse(getattr(settings, 'SECURE_HSTS_PRELOAD', False))


class ServicioDeMediaTest(TestCase):
    """La app sirve /media/ solo si el entorno lo autoriza."""

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        os.makedirs(os.path.join(self.media_root, 'facturas_gastos'), exist_ok=True)
        with open(
            os.path.join(self.media_root, 'facturas_gastos', 'prueba.pdf'), 'wb'
        ) as archivo:
            archivo.write(b'%PDF-1.4\n')

        self._media = override_settings(MEDIA_ROOT=self.media_root)
        self._media.enable()
        self.addCleanup(self._media.disable)

    def test_sirve_la_media_si_el_entorno_lo_permite(self):
        with override_settings(SERVE_MEDIA_LOCAL=True):
            respuesta = self.client.get('/media/facturas_gastos/prueba.pdf')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')

    def test_no_sirve_la_media_si_el_entorno_no_lo_permite(self):
        # En los tests DEBUG=False (lo fuerza el runner), como en staging real.
        with override_settings(SERVE_MEDIA_LOCAL=False):
            respuesta = self.client.get('/media/facturas_gastos/prueba.pdf')
        self.assertEqual(respuesta.status_code, 404)

    def test_archivo_inexistente_da_404(self):
        with override_settings(SERVE_MEDIA_LOCAL=True):
            respuesta = self.client.get('/media/facturas_gastos/no_existe.pdf')
        self.assertEqual(respuesta.status_code, 404)
