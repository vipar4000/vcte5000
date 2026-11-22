"""Arranque en frío: el plan contable debe existir sin pasos manuales.

Regresión detectada en la prueba de Madrid: al crear la primera cuenta bancaria
(«Banco → Nueva cuenta»), el desplegable «Cuenta contable» aparecía vacío porque
nadie había pulsado todavía «Inicializar PGC», y el formulario no dejaba guardar.
"""
from datetime import date

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


class ControlSaldoPorFechaTests(TestCase):
    """No se puede pagar con dinero que la cuenta aún no tenía en esa fecha.

    Caso de Madrid: depósito inicial del 10/08/2026 y una compra fechada el
    01/07/2026. El saldo de hoy cubría el pago, pero a 01/07 la cuenta estaba
    a cero: el banco quedaba en negativo.
    """

    def setUp(self):
        from decimal import Decimal

        from apps.accounting.models import CuentaContable, PlanContableDefault
        from apps.bank.models import BancoCuenta, BancoMovimiento
        from apps.bank.services import crear_movimiento_banco

        PlanContableDefault.crear_plan_base()
        self.cuenta = BancoCuenta.objects.create(
            nombre='Santander', iban='ES9121000418450200051332',
            cuenta_contable=CuentaContable.objects.get(codigo='572'),
        )
        self.deposito = crear_movimiento_banco(
            banco_cuenta=self.cuenta,
            fecha=date(2026, 8, 10),
            concepto='Deposito inicial',
            tipo='INGRESO',
            importe=Decimal('1000.00'),
        )

    def test_el_saldo_a_fecha_no_cuenta_el_deposito_anterior(self):
        from decimal import Decimal

        self.assertEqual(self.cuenta.saldo_a_fecha(date(2026, 7, 1)), Decimal('0'))
        self.assertEqual(
            self.cuenta.saldo_a_fecha(date(2026, 8, 10)), Decimal('1000.00')
        )
        self.assertEqual(
            self.cuenta.saldo_pendiente, Decimal('1000.00')
        )

    def test_no_permite_pagar_antes_de_que_entre_el_dinero(self):
        from decimal import Decimal

        from django.core.exceptions import ValidationError

        from apps.bank.models import BancoMovimiento
        from apps.bank.services import crear_movimiento_banco

        with self.assertRaises(ValidationError) as contexto:
            crear_movimiento_banco(
                banco_cuenta=self.cuenta,
                fecha=date(2026, 7, 1),
                concepto='Compra antes del deposito',
                tipo='EGRESO',
                importe=Decimal('300.00'),
            )

        mensaje = contexto.exception.messages[0]
        self.assertIn('Saldo insuficiente en la cuenta bancaria en la fecha indicada', mensaje)
        self.assertIn('Registre primero el ingreso/depósito', mensaje)
        self.assertIn('0,00', mensaje)
        self.assertEqual(
            BancoMovimiento.objects.filter(tipo='EGRESO').count(), 0
        )

    def test_permite_pagar_el_dia_del_deposito(self):
        from decimal import Decimal

        from apps.bank.models import BancoMovimiento
        from apps.bank.services import crear_movimiento_banco

        movimiento = crear_movimiento_banco(
            banco_cuenta=self.cuenta,
            fecha=date(2026, 8, 10),
            concepto='Compra pagada el mismo dia',
            tipo='EGRESO',
            importe=Decimal('800.00'),
        )

        self.assertEqual(movimiento.importe, Decimal('800.00'))
        self.assertEqual(self.cuenta.saldo_a_fecha(date(2026, 8, 10)), Decimal('200.00'))

    def test_no_permite_un_egreso_que_deje_el_saldo_negativo(self):
        from decimal import Decimal

        from django.core.exceptions import ValidationError

        from apps.bank.services import crear_movimiento_banco

        with self.assertRaises(ValidationError):
            crear_movimiento_banco(
                banco_cuenta=self.cuenta,
                fecha=date(2026, 8, 11),
                concepto='Pago demasiado grande',
                tipo='EGRESO',
                importe=Decimal('1000.01'),
            )

    def test_un_ingreso_retroactivo_si_esta_permitido(self):
        """Corregir con un ingreso antiguo es válido: es dinero que ya existía."""
        from decimal import Decimal

        from apps.bank.services import crear_movimiento_banco

        movimiento = crear_movimiento_banco(
            banco_cuenta=self.cuenta,
            fecha=date(2026, 7, 1),
            concepto='Ingreso anterior corregido',
            tipo='INGRESO',
            importe=Decimal('500.00'),
        )

        self.assertEqual(movimiento.importe, Decimal('500.00'))
        self.assertEqual(self.cuenta.saldo_a_fecha(date(2026, 7, 1)), Decimal('500.00'))
