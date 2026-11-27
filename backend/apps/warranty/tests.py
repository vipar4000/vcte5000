from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User


class GarantiaAnuladaConVentaTests(TestCase):
    """Al anular la venta se anula su garantía y baja del contador."""

    def setUp(self):
        from datetime import date
        from decimal import Decimal

        from apps.accounting.models import PlanContableDefault

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        from apps.accounting.models import CuentaContable
        from apps.bank.models import BancoCuenta
        from apps.vehicles.models import Vehiculo

        BancoCuenta.objects.create(
            nombre='Santander', iban='ES9121000418450200051332',
            cuenta_contable=CuentaContable.objects.get(codigo='572'),
        )
        self.vehiculo = Vehiculo.objects.create(
            matricula='1234ABC', bastidor='WVWZZZ3CZWE123456',
            marca='Volkswagen', modelo='Golf', anio=2020,
            combustible='DIESEL', kilometraje=90000, tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='C', estado='EN_VENTA',
            fecha_adquisicion=date(2026, 10, 1),
            precio_subasta=Decimal('8150.00'), created_by=self.admin,
        )
        self.client.force_login(self.admin)

    def _datos(self):
        return {
            'vehiculo': self.vehiculo.pk,
            'tipo_cliente': 'PARTICULAR',
            'cliente_nombre': 'Carlos Ruiz',
            'cliente_dni': '12345678A',
            'cliente_direccion': 'Calle Mayor 1',
            'cliente_poblacion': 'Madrid',
            'cliente_provincia': 'Madrid',
            'cliente_cp': '28001',
            'cliente_telefono': '612345678',
            'cliente_email': 'carlos@example.com',
            'fecha_venta': '2026-11-25',
            'metodo_pago': 'TRANSFERENCIA',
            'precio_venta': '11500.00',
        }

    def test_anular_la_venta_anula_la_garantia_y_el_contador(self):
        from apps.sales.models import VentaVehiculo
        from apps.warranty.models import GarantiaVehiculo

        self.client.post(reverse('sales:create'), self._datos())
        venta = VentaVehiculo.objects.get()
        garantia = GarantiaVehiculo.objects.get(venta=venta)
        self.assertTrue(garantia.esta_vigente)

        self.client.post(reverse('sales:anular', args=[venta.pk]),
                         {'motivo': 'prueba'})

        garantia.refresh_from_db()
        self.assertTrue(garantia.anulada)
        self.assertFalse(garantia.esta_vigente)
        self.assertEqual(garantia.estado_mostrado, 'ANULADA')
        self.assertEqual(garantia.meses_restantes, 0)
        self.assertIsNotNone(garantia.fecha_anulacion)

        respuesta = self.client.get(reverse('warranty:list'))
        self.assertEqual(respuesta.context['total_vigentes'], 0)

    def test_revender_crea_una_garantia_nueva_vigente(self):
        from apps.sales.models import VentaVehiculo
        from apps.warranty.models import GarantiaVehiculo

        self.client.post(reverse('sales:create'), self._datos())
        venta1 = VentaVehiculo.objects.get()
        self.client.post(reverse('sales:anular', args=[venta1.pk]),
                         {'motivo': 'prueba'})
        self.vehiculo.estado = 'EN_VENTA'
        self.vehiculo.save(update_fields=['estado'])

        self.client.post(reverse('sales:create'), self._datos())

        self.assertEqual(GarantiaVehiculo.objects.count(), 2)
        self.assertEqual(
            GarantiaVehiculo.objects.filter(anulada=False).count(), 1,
        )
        respuesta = self.client.get(reverse('warranty:list'))
        self.assertEqual(respuesta.context['total_vigentes'], 1)
