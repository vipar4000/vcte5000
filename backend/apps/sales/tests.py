"""Venta de un vehículo que tenía una reserva (señal) activa.

Regresión detectada en Madrid: precio 11.500 €, señal de 1.000 €. Al registrar la
venta, el ERP apuntaba dos ingresos (1.000 de la señal y 11.500 del cobro) y la
reserva seguía «Activa», con los 1.000 en el anticipo (438) sin cancelar.
"""
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounting.models import CuentaContable, PlanContableDefault
from apps.bank.models import BancoCuenta, BancoMovimiento, Reserva
from apps.sales.models import FacturaVenta, VentaVehiculo
from apps.vehicles.models import Vehiculo


class VentaConReservaTests(TestCase):
    def setUp(self):
        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.client.force_login(self.admin)

        self.banco = BancoCuenta.objects.create(
            nombre='Santander', iban='ES9121000418450200051332',
            cuenta_contable=CuentaContable.objects.get(codigo='572'),
        )
        self.vehiculo = Vehiculo.objects.create(
            matricula='1234ABC', bastidor='WVWZZZ3CZWE123456',
            marca='Volkswagen', modelo='Golf 1.6 TDI', anio=2020,
            combustible='DIESEL', kilometraje=90000, tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='C', estado='EN_VENTA',
            fecha_adquisicion=date(2026, 10, 1),
            precio_subasta=Decimal('7500.00'), tasas_sala=Decimal('400.00'),
            logistica_grua=Decimal('250.00'), tipo_iva=Decimal('136.50'),
            precio_venta=Decimal('11500.00'),
            created_by=self.admin,
        )

    def _crear_reserva(self, importe='1000.00'):
        respuesta = self.client.post(reverse('bank:reserva_create'), {
            'vehiculo': self.vehiculo.pk,
            'cliente_nombre': 'Carlos Ruiz',
            'cliente_dni': '12345678A',
            'fecha_reserva': '2026-11-20',
            'importe_reserva': importe,
            'notas': '',
        })
        self.assertEqual(respuesta.status_code, 302, 'no se creó la reserva')
        return Reserva.objects.get(vehiculo=self.vehiculo)

    def _vender(self, precio='11500.00', reserva=None):
        datos = {
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
            'precio_venta': precio,
        }
        if reserva is not None:
            datos['reserva'] = reserva.pk
        return self.client.post(reverse('sales:create'), datos)

    def test_la_venta_descuenta_la_senal_y_convierte_la_reserva(self):
        reserva = self._crear_reserva()

        respuesta = self._vender(reserva=reserva)
        self.assertEqual(respuesta.status_code, 302)

        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)
        self.assertEqual(venta.precio_venta, Decimal('11500.00'))

        # El banco suma exactamente el precio, no los 1.000 de más
        ingresos = BancoMovimiento.objects.filter(tipo='INGRESO')
        importes = sorted(m.importe for m in ingresos)
        self.assertEqual(importes, [Decimal('1000.00'), Decimal('10500.00')])
        self.assertEqual(sum(importes), Decimal('11500.00'))

        # La reserva queda convertida y enlazada
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, 'CONVERTIDA')
        self.assertEqual(reserva.venta_id, venta.pk)

        # El asiento de la venta aplica el anticipo y cuadra
        asiento = venta.asiento_contable
        self.assertIsNotNone(asiento)
        self.assertTrue(asiento.esta_cuadrado)
        self.assertEqual(asiento.estado, 'POSTEADO')

        def saldo(codigo):
            total = Decimal('0')
            for mov in asiento.movimientos.filter(cuenta__codigo=codigo):
                total += mov.debe - mov.haber
            return total

        # 438 y 477 del anticipo quedan cancelados por el debe
        base_anticipo = (Decimal('1000.00') / Decimal('1.21')).quantize(Decimal('0.01'))
        self.assertEqual(saldo('438'), base_anticipo)
        self.assertEqual(saldo('477'), Decimal('1000.00') - base_anticipo)
        # El banco solo recibe el resto
        self.assertEqual(saldo('572'), Decimal('10500.00'))

    def test_la_venta_sin_reserva_cobra_el_precio_completo(self):
        respuesta = self._vender()
        self.assertEqual(respuesta.status_code, 302)

        ingresos = BancoMovimiento.objects.filter(tipo='INGRESO')
        self.assertEqual([m.importe for m in ingresos], [Decimal('11500.00')])

        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)
        self.assertTrue(venta.asiento_contable.esta_cuadrado)

    def test_la_reserva_activa_se_aplica_aunque_no_se_indique(self):
        """Si el vendedor olvida pasar la reserva, se detecta y se descuenta."""
        reserva = self._crear_reserva()

        self._vender()  # sin el campo reserva

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, 'CONVERTIDA')
        ingresos = BancoMovimiento.objects.filter(tipo='INGRESO')
        self.assertEqual(
            sorted(m.importe for m in ingresos),
            [Decimal('1000.00'), Decimal('10500.00')],
        )

    def test_no_se_aplica_una_reserva_ya_convertida(self):
        reserva = self._crear_reserva()
        self._vender(reserva=reserva)

        otro_vehiculo = Vehiculo.objects.create(
            matricula='5678DEF', bastidor='WVWZZZ1KZAW123456',
            marca='Seat', modelo='León', anio=2019, combustible='GASOLINA',
            kilometraje=120000, tipo_dano='ACCIDENTAL', etiqueta_ambiental='B',
            estado='EN_VENTA', fecha_adquisicion=date(2026, 10, 1),
            precio_subasta=Decimal('6000.00'), tasas_sala=Decimal('300.00'),
            logistica_grua=Decimal('200.00'), precio_venta=Decimal('9000.00'),
            created_by=self.admin,
        )
        self.vehiculo = otro_vehiculo
        self._vender(precio='9000.00')

        ingresos = BancoMovimiento.objects.filter(tipo='INGRESO')
        self.assertEqual(
            sorted(m.importe for m in ingresos),
            [Decimal('1000.00'), Decimal('9000.00'), Decimal('10500.00')],
        )

    def test_el_comando_repara_una_venta_registrada_a_la_antigua(self):
        """Venta vieja (cobró el total sin descontar la señal) + reserva activa."""
        reserva = self._crear_reserva()

        # Se reproduce el comportamiento anterior al arreglo
        venta = VentaVehiculo.objects.create(
            vehiculo=self.vehiculo, tipo_cliente='PARTICULAR',
            cliente_nombre='Carlos Ruiz', cliente_dni='12345678A',
            cliente_direccion='Calle Mayor 1', cliente_poblacion='Madrid',
            cliente_provincia='Madrid', cliente_cp='28001',
            cliente_telefono='612345678', cliente_email='carlos@example.com',
            fecha_venta=date(2026, 11, 25), metodo_pago='TRANSFERENCIA',
            precio_venta=Decimal('11500.00'),
            coste_total=self.vehiculo.coste_total,
            created_by=self.admin,
        )
        self.vehiculo.estado = 'VENDIDO'
        self.vehiculo.save()
        venta.crear_asiento_contable()
        venta.registrar_movimiento_banco(asiento=venta.asiento_contable)

        self.assertEqual(
            sum(m.importe for m in BancoMovimiento.objects.filter(tipo='INGRESO')),
            Decimal('12500.00'),
        )

        call_command('reparar_venta_con_reserva', venta=venta.pk)

        self.assertEqual(
            sum(m.importe for m in BancoMovimiento.objects.filter(tipo='INGRESO')),
            Decimal('11500.00'),
        )

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, 'CONVERTIDA')

        venta.refresh_from_db()
        self.assertTrue(venta.asiento_contable.esta_cuadrado)
        self.assertEqual(venta.asiento_contable.estado, 'POSTEADO')

    def test_no_se_pueden_crear_dos_reservas_activas_del_mismo_coche(self):
        self._crear_reserva()

        respuesta = self.client.post(reverse('bank:reserva_create'), {
            'vehiculo': self.vehiculo.pk,
            'cliente_nombre': 'Otro Cliente',
            'cliente_dni': '87654321B',
            'fecha_reserva': '2026-11-21',
            'importe_reserva': '500.00',
            'notas': '',
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            Reserva.objects.filter(vehiculo=self.vehiculo, estado='ACTIVA').count(), 1
        )
        self.assertEqual(
            sum(m.importe for m in BancoMovimiento.objects.filter(tipo='INGRESO')),
            Decimal('1000.00'),
        )

    def test_la_venta_por_transferencia_avisa_del_cobro_en_banco(self):
        respuesta = self._vender()
        self.assertEqual(respuesta.status_code, 302)

        from django.contrib.messages import get_messages

        mensajes = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertTrue(
            any('Cobro registrado en Banco' in m for m in mensajes), mensajes
        )

    def test_la_venta_financiada_no_crea_ingreso_en_banco(self):
        respuesta = self.client.post(reverse('sales:create'), {
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
            'metodo_pago': 'FINANCIADO',
            'precio_venta': '11500.00',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            BancoMovimiento.objects.filter(tipo='INGRESO').count(), 0
        )

    def test_si_falla_el_cobro_no_se_guarda_la_venta(self):
        """Todo o nada: sin cuenta bancaria no queda una venta sin ingreso."""
        from apps.bank.models import BancoCuenta

        BancoCuenta.objects.all().delete()

        respuesta = self._vender()

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'No hay ninguna cuenta bancaria activa')
        self.assertEqual(VentaVehiculo.objects.count(), 0)

    def test_el_detalle_de_la_venta_muestra_el_cobro(self):
        reserva = self._crear_reserva()
        self._vender(reserva=reserva)
        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)

        respuesta = self.client.get(reverse('sales:detail', args=[venta.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Cobro en banco')
        self.assertContains(respuesta, '10.500,00')
        self.assertNotContains(respuesta, 'no tiene ingreso en Banco')

    def test_el_detalle_avisa_si_falta_el_cobro(self):
        venta = VentaVehiculo.objects.create(
            vehiculo=self.vehiculo, tipo_cliente='PARTICULAR',
            cliente_nombre='Carlos Ruiz', cliente_dni='12345678A',
            cliente_direccion='Calle Mayor 1', cliente_poblacion='Madrid',
            cliente_provincia='Madrid', cliente_cp='28001',
            cliente_telefono='612345678', cliente_email='carlos@example.com',
            fecha_venta=date(2026, 11, 15), metodo_pago='TRANSFERENCIA',
            precio_venta=Decimal('11500.00'),
            coste_total=self.vehiculo.coste_total,
            created_by=self.admin,
        )

        respuesta = self.client.get(reverse('sales:detail', args=[venta.pk]))

        self.assertContains(respuesta, 'no tiene ingreso en Banco')
        self.assertContains(respuesta, 'reparar_cobro_venta')

    def test_el_comando_repara_una_venta_sin_cobro(self):
        from django.core.management import call_command

        self._vender()
        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)

        # Simula el fallo: se borra el ingreso
        BancoMovimiento.objects.filter(tipo='INGRESO').delete()
        self.assertEqual(BancoMovimiento.objects.count(), 0)

        call_command('reparar_cobro_venta', venta=venta.pk)

        ingresos = BancoMovimiento.objects.filter(tipo='INGRESO')
        self.assertEqual(ingresos.count(), 1)
        self.assertEqual(ingresos.first().importe, Decimal('11500.00'))
        self.assertEqual(ingresos.first().asiento_asociado, venta.asiento_contable)

        # No duplica si se ejecuta otra vez
        call_command('reparar_cobro_venta', venta=venta.pk)
        self.assertEqual(BancoMovimiento.objects.filter(tipo='INGRESO').count(), 1)

    def _crear_factura(self, venta):
        from apps.sales.models import FacturaVenta

        return FacturaVenta.objects.create(
            codigo_factura=f'F2026-{venta.pk:04d}', venta=venta,
            fecha_operacion=venta.fecha_venta,
            cliente_nif=venta.cliente_dni,
            cliente_nombre=venta.cliente_nombre,
            precio_venta_total=venta.precio_venta,
            base_imponible_rebu=venta.base_imponible,
            iva_repercutido=venta.cuota_iva,
        )

    def test_eliminar_una_venta_sin_factura_deshace_todo(self):
        from apps.accounting.models import AsientoContable

        reserva = self._crear_reserva()
        self._vender(reserva=reserva)
        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)
        asiento = venta.asiento_contable

        respuesta = self.client.post(reverse('sales:delete', args=[venta.pk]))

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(VentaVehiculo.objects.filter(pk=venta.pk).exists())

        # Asiento anulado con contrapartida, no borrado
        asiento.refresh_from_db()
        self.assertEqual(asiento.estado, 'ANULADO')
        self.assertTrue(
            AsientoContable.objects.filter(tipo_documento='AnulacionVenta').exists()
        )

        # Cobro de la venta fuera del banco; la señal sigue
        self.assertEqual(
            [m.importe for m in BancoMovimiento.objects.filter(tipo='INGRESO')],
            [Decimal('1000.00')],
        )

        # Vehículo disponible y reserva activa otra vez
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'EN_VENTA')
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, 'ACTIVA')
        self.assertIsNone(reserva.venta_id)

    def test_eliminar_una_venta_con_factura_avisa_sin_error_500(self):
        self._vender()
        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)
        factura = self._crear_factura(venta)

        respuesta = self.client.post(reverse('sales:delete', args=[venta.pk]))

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(VentaVehiculo.objects.filter(pk=venta.pk).exists())
        self.assertTrue(FacturaVenta.objects.filter(pk=factura.pk).exists())

    def test_eliminar_una_venta_con_factura_confirmando_la_borra(self):
        self._vender()
        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)
        self._crear_factura(venta)

        respuesta = self.client.post(
            reverse('sales:delete', args=[venta.pk]),
            {'eliminar_factura': 'on'},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(VentaVehiculo.objects.filter(pk=venta.pk).exists())
        self.assertEqual(FacturaVenta.objects.count(), 0)

    def test_la_casilla_de_la_factura_va_dentro_del_formulario(self):
        """Regresión: si la casilla queda fuera del <form>, el navegador no la envía."""
        self._vender()
        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)
        self._crear_factura(venta)

        html = self.client.get(
            reverse('sales:delete', args=[venta.pk])
        ).content.decode()

        apertura = html.index('<form method="post"')
        casilla = html.index('name="eliminar_factura"')
        cierre = html.index('</form>')
        self.assertTrue(
            apertura < casilla < cierre,
            'La casilla debe estar dentro del formulario para enviarse',
        )
