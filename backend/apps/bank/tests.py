"""Arranque en frío: el plan contable debe existir sin pasos manuales.

Regresión detectada en la prueba de Madrid: al crear la primera cuenta bancaria
(«Banco → Nueva cuenta»), el desplegable «Cuenta contable» aparecía vacío porque
nadie había pulsado todavía «Inicializar PGC», y el formulario no dejaba guardar.
"""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounting.models import CuentaContable


class ArranqueCuentaBancariaTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.client.force_login(self.admin)

    def test_el_desplegable_de_cuentas_contiene_el_pgc(self):
        response = self.client.get(reverse('bank:cuenta_create'))
        self.assertEqual(response.status_code, 200)
        self.assertGreater(CuentaContable.objects.count(), 0)
        self.assertIn('572', response.content.decode())

    def test_si_el_plan_esta_vacio_la_vista_lo_crea(self):
        """Base restaurada o migrada antes de existir la inicialización automática."""
        CuentaContable.objects.all().delete()
        self.assertEqual(CuentaContable.objects.count(), 0)

        response = self.client.get(reverse('bank:cuenta_create'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            CuentaContable.objects.filter(codigo='572').exists(),
            'La vista debe recrear el plan contable para que el formulario sea usable',
        )
