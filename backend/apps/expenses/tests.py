from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.expenses.models import GastoEstructura
from apps.expenses.forms import GastoEstructuraForm, _parse_decimal_spanish
from apps.accounting.models import CuentaContable, AsientoContable, MovimientoContable
from apps.accounting.models import PlanContableDefault


User = get_user_model()


class GastoEstructuraModelTest(TestCase):

    def setUp(self):
        PlanContableDefault.crear_plan_base()
        CuentaContable.objects.get_or_create(
            codigo='4751.115',
            defaults={'nombre': 'Retenciones IRPF', 'tipo': 'P'},
        )
        self.user = User.objects.create_user(
            username='testadmin',
            password='testpass123!',
            rol='ADMIN'
        )

    def test_retencion_alquiler(self):
        """Test Case 1: Validación de operación con retención (Alquiler del Galpón)."""
        gasto = GastoEstructura.objects.create(
            fecha_factura='2026-07-01',
            proveedor_acreedor='Propietario Galpón S.L.',
            cif_nif='B12345678',
            categoria='ARRENDAMIENTO',
            base_imponible=Decimal('2000.00'),
            tipo_iva=Decimal('21.00'),
            retencion_irpf=Decimal('19.00'),
            created_by=self.user,
        )

        self.assertEqual(gasto.cuota_iva, Decimal('420.00'))
        self.assertEqual(gasto.cuota_retencion, Decimal('380.00'))
        self.assertEqual(gasto.total_factura, Decimal('2040.00'))

    def test_suministro_sin_retencion(self):
        """Factura de suministro sin retención."""
        gasto = GastoEstructura.objects.create(
            fecha_factura='2026-07-15',
            proveedor_acreedor='Endesa Energía S.A.U.',
            cif_nif='B12345678',
            categoria='SUMINISTROS',
            base_imponible=Decimal('350.00'),
            tipo_iva=Decimal('21.00'),
            retencion_irpf=Decimal('0.00'),
            created_by=self.user,
        )

        self.assertEqual(gasto.cuota_iva, Decimal('73.50'))
        self.assertEqual(gasto.cuota_retencion, Decimal('0.00'))
        self.assertEqual(gasto.total_factura, Decimal('423.50'))

    def test_creacion_asiento_contable(self):
        """Verificar que se genera el asiento contable correctamente."""
        gasto = GastoEstructura.objects.create(
            fecha_factura='2026-07-01',
            proveedor_acreedor='Propietario Galpón S.L.',
            cif_nif='B12345678',
            categoria='ARRENDAMIENTO',
            base_imponible=Decimal('2000.00'),
            tipo_iva=Decimal('21.00'),
            retencion_irpf=Decimal('19.00'),
            created_by=self.user,
        )

        asiento = gasto.crear_asiento_contable()

        self.assertIsNotNone(asiento)
        self.assertEqual(asiento.estado, 'POSTEADO')
        self.assertEqual(asiento.tipo_documento, 'GastoEstructura')
        self.assertEqual(asiento.documento_id, gasto.pk)

        movimientos = asiento.movimientos.all()
        self.assertEqual(movimientos.count(), 4)

        total_debe = sum(m.debe for m in movimientos)
        total_haber = sum(m.haber for m in movimientos)
        self.assertEqual(total_debe, total_haber)

    def test_tiene_retencion_property(self):
        """Verificar la propiedad tiene_retencion."""
        gasto_con = GastoEstructura.objects.create(
            fecha_factura='2026-07-01',
            proveedor_acreedor='Test',
            cif_nif='B00000000',
            categoria='ARRENDAMIENTO',
            base_imponible=Decimal('1000.00'),
            tipo_iva=Decimal('21.00'),
            retencion_irpf=Decimal('19.00'),
            created_by=self.user,
        )
        self.assertTrue(gasto_con.tiene_retencion)

        gasto_sin = GastoEstructura.objects.create(
            fecha_factura='2026-07-01',
            proveedor_acreedor='Test',
            cif_nif='B00000000',
            categoria='SUMINISTROS',
            base_imponible=Decimal('1000.00'),
            tipo_iva=Decimal('21.00'),
            retencion_irpf=Decimal('0.00'),
            created_by=self.user,
        )
        self.assertFalse(gasto_sin.tiene_retencion)


class FormatoNumericoFormTest(TestCase):
    """Regresión: los formularios deben aceptar formato español (1.234,56)."""

    def test_parse_decimal_spanish(self):
        self.assertEqual(_parse_decimal_spanish('1.200,00'), Decimal('1200.00'))
        self.assertEqual(_parse_decimal_spanish('2480,50'), Decimal('2480.50'))
        self.assertEqual(_parse_decimal_spanish('1200'), Decimal('1200'))
        self.assertEqual(_parse_decimal_spanish('1200.00'), Decimal('1200.00'))
        self.assertEqual(_parse_decimal_spanish('21,00'), Decimal('21.00'))
        self.assertEqual(_parse_decimal_spanish(''), None)
        self.assertEqual(_parse_decimal_spanish(None), None)

    def test_gasto_estructura_form_acepta_formato_espanol(self):
        PlanContableDefault.crear_plan_base()
        user = User.objects.create_user(
            username='testadmin',
            password='testpass123!',
            rol='ADMIN'
        )
        data = {
            'fecha_factura': '2026-07-01',
            'proveedor_acreedor': 'Test S.L.',
            'cif_nif': 'B12345678',
            'categoria': 'SUMINISTROS',
            'base_imponible': '1.200,00',
            'tipo_iva': '21,00',
            'retencion_irpf': '0,00',
            'pagado': False,
        }
        form = GastoEstructuraForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['base_imponible'], Decimal('1200.00'))
        self.assertEqual(form.cleaned_data['tipo_iva'], Decimal('21.00'))
        self.assertEqual(form.cleaned_data['retencion_irpf'], Decimal('0.00'))

    def test_gasto_estructura_form_rechaza_valor_invalido(self):
        PlanContableDefault.crear_plan_base()
        data = {
            'fecha_factura': '2026-07-01',
            'proveedor_acreedor': 'Test S.L.',
            'cif_nif': 'B12345678',
            'categoria': 'SUMINISTROS',
            'base_imponible': 'abc',
            'tipo_iva': '21,00',
            'retencion_irpf': '0,00',
            'pagado': False,
        }
        form = GastoEstructuraForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('base_imponible', form.errors)


class GastoEstructuraPagoTest(TestCase):
    """Flujo de pago automático: asiento DEBE 410 / HABER 570-572 + EGRESO bancario."""

    def setUp(self):
        PlanContableDefault.crear_plan_base()
        CuentaContable.objects.get_or_create(
            codigo='4751.115',
            defaults={'nombre': 'Retenciones IRPF', 'tipo': 'P'},
        )
        self.user = User.objects.create_user(
            username='testadmin',
            password='testpass123!',
            rol='ADMIN'
        )
        self.gasto = GastoEstructura.objects.create(
            fecha_factura='2026-07-01',
            proveedor_acreedor='Propietario Galpón S.L.',
            cif_nif='B12345678',
            categoria='ARRENDAMIENTO',
            base_imponible=Decimal('2000.00'),
            tipo_iva=Decimal('21.00'),
            retencion_irpf=Decimal('19.00'),
            created_by=self.user,
        )
        self.gasto.crear_asiento_contable()

    def test_crear_asiento_pago(self):
        """El pago genera asiento POSTEADO DEBE 410 / HABER 572."""
        self.gasto.pagado = True
        self.gasto.fecha_pago = date(2026, 7, 21)
        self.gasto.save(update_fields=['pagado', 'fecha_pago'])

        asiento = self.gasto.crear_asiento_pago()

        self.assertIsNotNone(asiento)
        self.assertEqual(asiento.estado, 'POSTEADO')
        self.assertEqual(asiento.tipo_documento, 'PagoGastoEstructura')
        self.assertEqual(asiento.documento_id, self.gasto.pk)
        self.assertEqual(asiento.fecha.isoformat(), '2026-07-21')

        movimientos = asiento.movimientos.all()
        self.assertEqual(movimientos.count(), 2)
        debe_410 = movimientos.get(cuenta__codigo='410')
        haber_572 = movimientos.get(cuenta__codigo='572')
        self.assertEqual(debe_410.debe, Decimal('2040.00'))
        self.assertEqual(haber_572.haber, Decimal('2040.00'))

    def test_pago_con_caja_no_crea_movimiento_bancario(self):
        """Pago desde caja (570): asiento correcto y sin EGRESO en Banco."""
        from apps.bank.models import BancoMovimiento

        cuenta_caja = CuentaContable.objects.get(codigo='570')
        self.gasto.pagado = True
        self.gasto.fecha_pago = date(2026, 7, 21)
        self.gasto.forma_pago = cuenta_caja
        self.gasto.save(update_fields=['pagado', 'fecha_pago', 'forma_pago'])

        asiento = self.gasto.crear_asiento_pago()

        haber = asiento.movimientos.get(haber__gt=0)
        self.assertEqual(haber.cuenta.codigo, '570')
        self.assertFalse(BancoMovimiento.objects.exists())

    def test_pago_idempotente(self):
        """Llamar dos veces no duplica el asiento de pago."""
        self.gasto.pagado = True
        self.gasto.fecha_pago = date(2026, 7, 21)
        self.gasto.save(update_fields=['pagado', 'fecha_pago'])

        primero = self.gasto.crear_asiento_pago()
        segundo = self.gasto.crear_asiento_pago()

        self.assertEqual(primero.pk, segundo.pk)
        activos = AsientoContable.objects.filter(
            tipo_documento='PagoGastoEstructura',
            documento_id=self.gasto.pk,
        ).exclude(estado='ANULADO')
        self.assertEqual(activos.count(), 1)

    def test_pago_crea_egreso_bancario(self):
        """El pago desde 572 crea EGRESO en el módulo Banco vinculado al asiento."""
        from apps.bank.models import BancoCuenta, BancoMovimiento

        cuenta_572 = CuentaContable.objects.get(codigo='572')
        banco = BancoCuenta.objects.create(
            nombre='Banco Test', iban='ES0000000000000000000000',
            cuenta_contable=cuenta_572, activa=True,
        )
        BancoMovimiento.objects.create(
            banco_cuenta=banco, fecha='2026-07-01',
            concepto='Saldo inicial', tipo='INGRESO', importe=Decimal('10000.00'),
        )

        self.gasto.pagado = True
        self.gasto.fecha_pago = date(2026, 7, 21)
        self.gasto.save(update_fields=['pagado', 'fecha_pago'])
        asiento = self.gasto.crear_asiento_pago()

        egreso = BancoMovimiento.objects.filter(
            tipo='EGRESO', importe=Decimal('2040.00')
        ).first()
        self.assertIsNotNone(egreso)
        self.assertEqual(egreso.asiento_asociado, asiento)
        self.assertEqual(egreso.banco_cuenta, banco)

    def test_anular_asiento_pago_revierte(self):
        """Anular el pago: asiento ANULADO, reversión creada y EGRESO eliminado."""
        from apps.bank.models import BancoCuenta, BancoMovimiento
        from apps.expenses.views import _anular_asiento_pago

        cuenta_572 = CuentaContable.objects.get(codigo='572')
        banco = BancoCuenta.objects.create(
            nombre='Banco Test', iban='ES0000000000000000000000',
            cuenta_contable=cuenta_572, activa=True,
        )
        BancoMovimiento.objects.create(
            banco_cuenta=banco, fecha='2026-07-01',
            concepto='Saldo inicial', tipo='INGRESO', importe=Decimal('10000.00'),
        )

        self.gasto.pagado = True
        self.gasto.fecha_pago = date(2026, 7, 21)
        self.gasto.save(update_fields=['pagado', 'fecha_pago'])
        asiento_pago = self.gasto.crear_asiento_pago()
        self.assertEqual(
            BancoMovimiento.objects.filter(asiento_asociado=asiento_pago).count(), 1
        )

        _anular_asiento_pago(self.gasto, self.user)

        asiento_pago.refresh_from_db()
        self.assertEqual(asiento_pago.estado, 'ANULADO')
        self.assertTrue(
            AsientoContable.objects.filter(
                tipo_documento='AnulacionPagoGasto',
                documento_id=self.gasto.pk,
            ).exists()
        )
        self.assertFalse(
            BancoMovimiento.objects.filter(asiento_asociado=asiento_pago).exists()
        )


class GastoEstructuraPagoViewTest(TestCase):
    """Integración de la vista de edición: marcar/desmarcar pagado."""

    def setUp(self):
        PlanContableDefault.crear_plan_base()
        CuentaContable.objects.get_or_create(
            codigo='4751.115',
            defaults={'nombre': 'Retenciones IRPF', 'tipo': 'P'},
        )
        self.user = User.objects.create_user(
            username='testadmin',
            password='testpass123!',
            rol='ADMIN'
        )
        self.client.force_login(self.user)
        self.gasto = GastoEstructura.objects.create(
            fecha_factura='2026-07-01',
            proveedor_acreedor='Propietario Galpón S.L.',
            cif_nif='B12345678',
            categoria='ARRENDAMIENTO',
            base_imponible=Decimal('2000.00'),
            tipo_iva=Decimal('21.00'),
            retencion_irpf=Decimal('19.00'),
            created_by=self.user,
        )
        self.gasto.crear_asiento_contable()

    def _post_editar(self, pagado, fecha_pago='2026-07-21'):
        return self.client.post(
            f'/erp/gastos/{self.gasto.pk}/editar/',
            {
                'fecha_factura': '2026-07-01',
                'proveedor_acreedor': 'Propietario Galpón S.L.',
                'cif_nif': 'B12345678',
                'categoria': 'ARRENDAMIENTO',
                'base_imponible': '2000,00',
                'tipo_iva': '21,00',
                'retencion_irpf': '19,00',
                'pagado': 'on' if pagado else '',
                'fecha_pago': fecha_pago,
            },
        )

    def test_marcar_pagado_genera_asiento_pago(self):
        resp = self._post_editar(pagado=True)
        self.assertEqual(resp.status_code, 302)

        self.gasto.refresh_from_db()
        self.assertTrue(self.gasto.pagado)
        pago = AsientoContable.objects.filter(
            tipo_documento='PagoGastoEstructura',
            documento_id=self.gasto.pk,
        ).exclude(estado='ANULADO').first()
        self.assertIsNotNone(pago)
        self.assertEqual(pago.estado, 'POSTEADO')

    def test_desmarcar_pagado_anula_asiento_pago(self):
        self._post_editar(pagado=True)
        self.gasto.refresh_from_db()
        self.assertTrue(self.gasto.pagado)

        resp = self._post_editar(pagado=False)
        self.assertEqual(resp.status_code, 302)

        self.gasto.refresh_from_db()
        self.assertFalse(self.gasto.pagado)
        activos = AsientoContable.objects.filter(
            tipo_documento='PagoGastoEstructura',
            documento_id=self.gasto.pk,
        ).exclude(estado='ANULADO')
        self.assertEqual(activos.count(), 0)
        self.assertTrue(
            AsientoContable.objects.filter(
                tipo_documento='AnulacionPagoGasto',
                documento_id=self.gasto.pk,
            ).exists()
        )
