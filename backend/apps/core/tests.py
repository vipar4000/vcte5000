"""Comprobaciones de la configuración de desarrollo.

Regresión que ya ocurrió una vez: al no existir `backend/.env`, `base.py` no ve
`DEBUG` y aplica los ajustes de producción (HTTPS obligatorio, cookies Secure).
Como `development.py` fuerza `DEBUG = True` después de importar `base`, el
resultado era un servidor de desarrollo que respondía 301 hacia HTTPS y dejaba
el login inaccesible.
"""
from django.conf import settings
from django.test import SimpleTestCase


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
