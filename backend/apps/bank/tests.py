"""Arranque en frío: el plan contable debe existir sin pasos manuales.

Regresión detectada en la prueba de Madrid: al crear la primera cuenta bancaria
(«Banco → Nueva cuenta»), el desplegable «Cuenta contable» aparecía vacío porque
nadie había pulsado todavía «Inicializar PGC», y el formulario no dejaba guardar.
"""
from decimal import Decimal
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


class ConciliacionToleranciaTests(TestCase):
    """El banco puede reflejar una transferencia 1-3 días hábiles después."""

    def setUp(self):
        from decimal import Decimal

        from apps.accounting.models import CuentaContable, PlanContableDefault
        from apps.bank.models import BancoCuenta, BancoMovimiento

        PlanContableDefault.crear_plan_base()
        self.cuenta = BancoCuenta.objects.create(
            nombre='Santander', iban='ES9121000418450200051332',
            cuenta_contable=CuentaContable.objects.get(codigo='572'),
        )
        self.movimiento = BancoMovimiento.objects.create(
            banco_cuenta=self.cuenta, fecha=date(2026, 7, 1),
            concepto='Deposito inicial', tipo='INGRESO',
            importe=Decimal('1000.00'),
        )

    def _conciliar(self, fecha, importe='1000.00'):
        from apps.bank.services import conciliar_extracto

        return conciliar_extracto(self.cuenta, [{
            'fecha': fecha,
            'concepto': 'Deposito inicial',
            'tipo': 'INGRESO',
            'importe': importe,
        }])[0]

    def test_coincide_el_mismo_dia(self):
        resultado = self._conciliar(date(2026, 7, 1))
        self.assertEqual(resultado['erp_match'], self.movimiento)

    def test_coincide_tres_dias_despues(self):
        resultado = self._conciliar(date(2026, 7, 4))
        self.assertEqual(resultado['erp_match'], self.movimiento)

    def test_coincide_tres_dias_antes(self):
        resultado = self._conciliar(date(2026, 6, 28))
        self.assertEqual(resultado['erp_match'], self.movimiento)

    def test_no_coincide_a_cuatro_dias(self):
        resultado = self._conciliar(date(2026, 7, 5))
        self.assertIsNone(resultado['erp_match'])

    def test_el_importe_tiene_que_ser_exacto(self):
        resultado = self._conciliar(date(2026, 7, 2), importe='1000.01')
        self.assertIsNone(resultado['erp_match'])


class DepositoInicialConFechaTests(TestCase):
    """El alta de cuenta permite indicar la fecha real del abono."""

    def setUp(self):
        from apps.accounts.models import User
        from apps.accounting.models import CuentaContable, PlanContableDefault

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.client.force_login(self.admin)
        self.cuenta_572 = CuentaContable.objects.get(codigo='572')

    def test_el_deposito_se_registra_en_la_fecha_indicada(self):
        from decimal import Decimal

        from apps.bank.models import BancoCuenta, BancoMovimiento

        respuesta = self.client.post(reverse('bank:cuenta_create'), {
            'nombre': 'Banco Santander',
            'iban': 'ES9121000418450200051999',
            'swift': '',
            'cuenta_contable': self.cuenta_572.pk,
            'activa': 'on',
            'deposito_inicial': '50000.00',
            'fecha_deposito': '2026-06-30',
            'notas_deposito': '',
        })
        self.assertEqual(respuesta.status_code, 302)

        banco = BancoCuenta.objects.get(nombre='Banco Santander')
        deposito = BancoMovimiento.objects.get(banco_cuenta=banco, tipo='INGRESO')
        self.assertEqual(deposito.fecha, date(2026, 6, 30))
        self.assertEqual(deposito.importe, Decimal('50000.00'))
        self.assertEqual(banco.saldo_a_fecha(date(2026, 6, 30)), Decimal('50000.00'))


class AltaCuentaConDepositoTests(TestCase):
    """Crear cuenta bancaria con depósito inicial: todo o nada y sin 500.

    Regresión de la prueba del 24/11: el primer intento daba error 500 y la
    cuenta quedaba creada a medias (el segundo intento avisaba de IBAN
    duplicado). Causa: `crear_movimiento_banco()` hacía `select_for_update()`
    fuera de una transacción, lo que en PostgreSQL lanza
    `TransactionManagementError`.
    """

    def setUp(self):
        from apps.accounting.models import PlanContableDefault

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.client.force_login(self.admin)
        self.cuenta_572 = CuentaContable.objects.get(codigo='572')

    def _post(self, **extra):
        datos = {
            'nombre': 'Santander Empresa',
            'iban': 'ES9121000418450200051332',
            'swift': 'BSCHESMM',
            'cuenta_contable': self.cuenta_572.pk,
            'activa': 'on',
        }
        datos.update(extra)
        return self.client.post(reverse('bank:cuenta_create'), datos)

    def test_crear_cuenta_con_deposito_registra_movimiento_y_asiento(self):
        from apps.accounting.models import AsientoContable
        from apps.bank.models import BancoCuenta, BancoMovimiento

        respuesta = self._post(
            deposito_inicial='10000.00',
            fecha_deposito='2026-11-24',
            notas_deposito='Aportación inicial',
        )

        self.assertEqual(respuesta.status_code, 302)
        cuenta = BancoCuenta.objects.get()
        self.assertEqual(cuenta.iban, 'ES9121000418450200051332')

        movimiento = BancoMovimiento.objects.get(banco_cuenta=cuenta)
        self.assertEqual(movimiento.tipo, 'INGRESO')
        self.assertEqual(movimiento.importe, 10000)
        self.assertEqual(movimiento.fecha, date(2026, 11, 24))
        self.assertIsNotNone(movimiento.asiento_asociado)

        asiento = AsientoContable.objects.get(pk=movimiento.asiento_asociado.pk)
        self.assertEqual(asiento.estado, 'POSTEADO')
        debe = sum((m.debe for m in asiento.movimientos.all()), 0)
        haber = sum((m.haber for m in asiento.movimientos.all()), 0)
        self.assertEqual(debe, haber)

    def test_si_falla_el_asiento_no_queda_la_cuenta_creada(self):
        from unittest import mock

        from django.core.exceptions import ValidationError

        from apps.bank.models import BancoCuenta

        with mock.patch(
            'apps.bank.views._crear_asiento_deposito',
            side_effect=ValidationError('No se pudo crear el asiento.'),
        ):
            respuesta = self._post(deposito_inicial='10000.00')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(BancoCuenta.objects.count(), 0)
        self.assertContains(respuesta, 'No se pudo crear el asiento')

    def test_crear_cuenta_sin_deposito_no_genera_movimientos(self):
        from apps.bank.models import BancoCuenta, BancoMovimiento

        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(BancoCuenta.objects.count(), 1)
        self.assertEqual(BancoMovimiento.objects.count(), 0)


    def test_el_deposito_manual_tambien_enlaza_su_asiento(self):
        from apps.bank.models import BancoCuenta, BancoMovimiento

        self._post()
        cuenta = BancoCuenta.objects.get()

        respuesta = self.client.post(
            reverse('bank:deposito_create', args=[cuenta.pk]),
            {
                'fecha': '2026-11-25',
                'concepto': 'Aportación de socio',
                'importe': '5000.00',
                'notas': '',
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        movimiento = BancoMovimiento.objects.get(banco_cuenta=cuenta)
        self.assertEqual(movimiento.importe, 5000)
        self.assertIsNotNone(movimiento.asiento_asociado)

    def test_crear_movimiento_banco_abre_su_propia_transaccion(self):
        """En PostgreSQL, select_for_update() exige una transacción activa."""
        from apps.bank import services

        self.assertIsNotNone(
            getattr(services.crear_movimiento_banco, '__wrapped__', None),
            'crear_movimiento_banco debe ir decorada con @transaction.atomic',
        )


class CajaEfectivoTests(TestCase):
    """Caja de efectivo: cuenta 570 sin IBAN y su saldo."""

    def setUp(self):
        from apps.accounting.models import PlanContableDefault

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.client.force_login(self.admin)

    def _post_cuenta(self, **extra):
        datos = {
            'nombre': 'Caja',
            'cuenta_contable': CuentaContable.objects.get(codigo='570').pk,
            'activa': 'on',
        }
        datos.update(extra)
        return self.client.post(reverse('bank:cuenta_create'), datos)

    def test_se_puede_crear_la_caja_sin_iban(self):
        from apps.bank.models import BancoCuenta

        respuesta = self._post_cuenta(deposito_inicial='500.00',
                                      fecha_deposito='2026-11-20')

        self.assertEqual(respuesta.status_code, 302)
        caja = BancoCuenta.objects.get()
        self.assertTrue(caja.es_caja)
        self.assertIn('Caja', str(caja))

    def test_un_banco_sigue_exigiendo_iban(self):
        from apps.bank.models import BancoCuenta

        respuesta = self._post_cuenta(
            nombre='Banco sin IBAN',
            cuenta_contable=CuentaContable.objects.get(codigo='572').pk,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(BancoCuenta.objects.count(), 0)

    def test_el_saldo_de_la_caja_cuenta_sus_movimientos(self):
        from decimal import Decimal

        from apps.bank.models import BancoCuenta, BancoMovimiento

        self._post_cuenta(deposito_inicial='500.00', fecha_deposito='2026-11-20')
        caja = BancoCuenta.objects.get()

        # Los movimientos de caja no se concilian con extracto: cuentan igual
        BancoMovimiento.objects.create(
            banco_cuenta=caja, fecha='2026-11-21', concepto='Compra menor',
            tipo='EGRESO', importe=Decimal('120.00'), conciliado=False,
        )

        self.assertEqual(caja.saldo, Decimal('380.00'))


class TraspasoTesoreriaTests(TestCase):
    """Traspaso real Banco (572) -> Caja (570) con asiento único."""

    def setUp(self):
        from apps.accounting.models import PlanContableDefault

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.client.force_login(self.admin)

        from apps.accounting.models import CuentaContable
        from apps.bank.models import BancoCuenta, BancoMovimiento

        self.banco = BancoCuenta.objects.create(
            nombre='Santander', iban='ES9121000418450200051332',
            cuenta_contable=CuentaContable.objects.get(codigo='572'),
        )
        BancoMovimiento.objects.create(
            banco_cuenta=self.banco, fecha='2026-06-30',
            concepto='Depósito inicial', tipo='INGRESO',
            importe=Decimal('5000.00'),
        )
        self.caja = BancoCuenta.objects.create(
            nombre='Caja', cuenta_contable=CuentaContable.objects.get(codigo='570'),
        )

    def _post(self, **extra):
        datos = {
            'origen': self.banco.pk,
            'destino': self.caja.pk,
            'fecha': '2026-07-01',
            'importe': '1000.00',
            'concepto': 'Fondeo de caja',
        }
        datos.update(extra)
        return self.client.post(
            reverse('bank:traspaso_create', args=[self.banco.pk]), datos
        )

    def test_el_traspaso_mueve_el_dinero_y_cuadra_la_contabilidad(self):
        from apps.accounting.models import AsientoContable
        from apps.bank.models import BancoMovimiento

        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 302)

        salida = BancoMovimiento.objects.get(
            banco_cuenta=self.banco, tipo='EGRESO'
        )
        entrada = BancoMovimiento.objects.get(
            banco_cuenta=self.caja, tipo='INGRESO'
        )
        self.assertEqual(salida.importe, Decimal('1000.00'))
        self.assertEqual(entrada.importe, Decimal('1000.00'))
        self.assertEqual(salida.asiento_asociado_id, entrada.asiento_asociado_id)

        asiento = AsientoContable.objects.get(tipo_documento='TraspasoTesoreria')
        self.assertEqual(asiento.estado, 'POSTEADO')
        self.assertTrue(asiento.esta_cuadrado)
        debe = {m.cuenta.codigo: m.debe for m in asiento.movimientos.all()}
        haber = {m.cuenta.codigo: m.haber for m in asiento.movimientos.all()}
        self.assertEqual(debe['570'], Decimal('1000.00'))
        self.assertEqual(haber['572'], Decimal('1000.00'))

        # En banco el «saldo» solo cuenta lo conciliado; el total es
        # saldo_pendiente. La caja cuenta todos sus movimientos.
        self.assertEqual(self.banco.saldo_pendiente, Decimal('4000.00'))
        self.assertEqual(self.caja.saldo, Decimal('1000.00'))

    def test_no_se_permite_traspasar_mas_que_el_saldo(self):
        from apps.bank.models import BancoMovimiento

        respuesta = self._post(importe='9000.00')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Saldo insuficiente')
        self.assertFalse(
            BancoMovimiento.objects.filter(banco_cuenta=self.caja).exists()
        )

    def test_origen_y_destino_no_pueden_ser_la_misma_cuenta(self):
        respuesta = self._post(destino=self.banco.pk)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'deben ser distintas')

    def test_el_resguardo_se_adjunta_a_los_dos_movimientos(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.bank.models import BancoMovimiento

        resguardo = SimpleUploadedFile(
            'resguardo.pdf', b'%PDF-1.4 prueba', content_type='application/pdf'
        )

        respuesta = self._post(soporte=resguardo)

        self.assertEqual(respuesta.status_code, 302)
        traspaso = BancoMovimiento.objects.filter(
            concepto__startswith='Fondeo de caja'
        )
        self.assertEqual(traspaso.count(), 2)
        for movimiento in traspaso:
            self.assertTrue(movimiento.soporte)
