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


class LimpiarDatosPruebaTests(TestCase):
    """Limpieza de staging conservando usuarios y plan contable."""

    def setUp(self):
        from datetime import date
        from decimal import Decimal

        from apps.accounts.models import User
        from apps.accounting.models import CuentaContable, PlanContableDefault
        from apps.bank.models import BancoCuenta, BancoMovimiento, Reserva
        from apps.payroll.models import NominaEstructura
        from apps.vehicles.models import Vehiculo

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.operario = User.objects.create_user(
            username='mecanico1', email='mecanico1@eurocar.local',
            password='mecanico123!', rol='OPERARIO',
        )
        cuentas_antes = CuentaContable.objects.count()

        vehiculo = Vehiculo.objects.create(
            matricula='1234ABC', bastidor='WVWZZZ3CZWE123456',
            marca='Volkswagen', modelo='Golf', anio=2020,
            combustible='DIESEL', kilometraje=90000, tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='C', estado='EN_VENTA',
            fecha_adquisicion=date(2026, 10, 1),
            precio_subasta=Decimal('7500.00'), tasas_sala=Decimal('400.00'),
            logistica_grua=Decimal('250.00'), precio_venta=Decimal('11500.00'),
            created_by=self.admin,
        )
        vehiculo.crear_asiento_contable()

        banco = BancoCuenta.objects.create(
            nombre='Santander', iban='ES9121000418450200051332',
            cuenta_contable=CuentaContable.objects.get(codigo='572'),
        )
        movimiento = BancoMovimiento.objects.create(
            banco_cuenta=banco, fecha=date(2026, 11, 20),
            concepto='Reserva/Señal de prueba', tipo='INGRESO',
            importe=Decimal('1000.00'), vehiculo_asociado=vehiculo,
        )
        Reserva.objects.create(
            vehiculo=vehiculo, cliente_nombre='Carlos Ruiz',
            cliente_dni='12345678A', fecha_reserva=date(2026, 11, 20),
            importe_reserva=Decimal('1000.00'), banco_movimiento=movimiento,
            created_by=self.admin,
        )
        NominaEstructura.objects.create(
            empleado=self.operario, fecha_nomina=date(2026, 11, 20),
            salario_bruto=Decimal('1500.00'), ss_patronal=Decimal('472.50'),
            retencion_irpf=Decimal('90.00'), ss_obrera=Decimal('95.25'),
            created_by=self.admin,
        )
        self.cuentas_antes = cuentas_antes

    def test_la_simulacion_no_borra_nada(self):
        from django.core.management import call_command
        from apps.bank.models import Reserva
        from apps.vehicles.models import Vehiculo

        call_command('limpiar_datos_prueba', verbosity=0)

        self.assertEqual(Vehiculo.objects.count(), 1)
        self.assertEqual(Reserva.objects.count(), 1)

    def test_la_limpieza_conserva_usuarios_y_plan_contable(self):
        from django.core.management import call_command

        from apps.accounting.models import AsientoContable, CuentaContable
        from apps.accounts.models import User
        from apps.bank.models import BancoCuenta, BancoMovimiento, Reserva
        from apps.payroll.models import NominaEstructura
        from apps.vehicles.models import Vehiculo

        call_command('limpiar_datos_prueba', '--confirmar', verbosity=0)

        # Datos de negocio: fuera
        self.assertEqual(Vehiculo.objects.count(), 0)
        self.assertEqual(Reserva.objects.count(), 0)
        self.assertEqual(BancoMovimiento.objects.count(), 0)
        self.assertEqual(BancoCuenta.objects.count(), 0)
        self.assertEqual(NominaEstructura.objects.count(), 0)
        self.assertEqual(AsientoContable.objects.count(), 0)

        # Usuarios y configuración: intactos
        self.assertEqual(User.objects.count(), 2)
        self.assertTrue(
            User.objects.get(username='admin').check_password('admin123!')
        )
        self.assertEqual(CuentaContable.objects.count(), self.cuentas_antes)
        self.assertTrue(CuentaContable.objects.filter(codigo='572').exists())
