from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.expenses.models import GastoEstructura
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
        self.assertEqual(asiento.estado, 'BORRADOR')
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
