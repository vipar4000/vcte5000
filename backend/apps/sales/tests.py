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
            'tipo_cliente': 'PARTICULAR',
            'cliente_nombre': 'Carlos Ruiz',
            'cliente_dni': '12345678A',
            'cliente_direccion': 'Calle Mayor 1',
            'cliente_poblacion': 'Madrid',
            'cliente_provincia': 'Madrid',
            'cliente_cp': '28001',
            'cliente_telefono': '612345678',
            'cliente_email': 'carlos@example.com',
            'fecha_reserva': '2026-11-20',
            'importe_reserva': importe,
            'metodo_pago': 'TRANSFERENCIA',
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

        # La entrega a cuenta (sin IVA) queda cancelada por completo
        self.assertEqual(saldo('438'), Decimal('1000.00'))
        self.assertEqual(saldo('477'), Decimal('0'))
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

    def test_anular_una_venta_sin_factura_deshace_todo(self):
        from apps.accounting.models import AsientoContable

        reserva = self._crear_reserva()
        self._vender(reserva=reserva)
        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)
        asiento = venta.asiento_contable

        respuesta = self.client.post(
            reverse('sales:anular', args=[venta.pk]),
            {'motivo': 'El cliente no formalizó la financiación'},
        )

        self.assertEqual(respuesta.status_code, 302)

        # La venta NO se borra: queda anulada en el histórico
        venta.refresh_from_db()
        self.assertTrue(venta.anulada)
        self.assertIsNotNone(venta.fecha_anulacion)
        self.assertIn('financiación', venta.motivo_anulacion)

        # Asiento anulado con contrapartida, no borrado
        asiento.refresh_from_db()
        self.assertEqual(asiento.estado, 'ANULADO')
        self.assertTrue(
            AsientoContable.objects.filter(tipo_documento='AnulacionVenta').exists()
        )

        # El cobro no se borra: se compensa con un EGRESO del mismo importe.
        self.assertEqual(
            sorted(
                m.importe
                for m in BancoMovimiento.objects.filter(tipo='INGRESO')
            ),
            [Decimal('1000.00'), Decimal('10500.00')],
        )
        self.assertTrue(BancoMovimiento.objects.filter(
            tipo='EGRESO', concepto__startswith='Anulación venta'
        ).exists())

        # Vehículo disponible y reserva activa otra vez
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'EN_VENTA')
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, 'ACTIVA')
        self.assertIsNone(reserva.venta_id)

    def test_anular_una_venta_con_factura_genera_rectificativa(self):
        self._vender()
        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)
        factura = self._crear_factura(venta)

        respuesta = self.client.post(
            reverse('sales:anular', args=[venta.pk]), {'motivo': 'Error de precio'}
        )

        self.assertEqual(respuesta.status_code, 302)

        venta.refresh_from_db()
        self.assertTrue(venta.anulada)

        # La factura original se conserva (normativa de facturación)
        self.assertTrue(FacturaVenta.objects.filter(pk=factura.pk).exists())
        rectificativa = FacturaVenta.objects.filter(
            tipo_factura='R1', factura_rectificada=factura
        ).first()
        self.assertIsNotNone(rectificativa)
        self.assertTrue(rectificativa.codigo_factura.startswith('R-'))

    def test_eliminar_una_venta_con_movimientos_esta_bloqueado(self):
        self._vender()
        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)

        respuesta = self.client.post(
            reverse('sales:delete', args=[venta.pk]), follow=True
        )

        self.assertTrue(VentaVehiculo.objects.filter(pk=venta.pk).exists())
        self.assertContains(respuesta, 'Anular venta')

    def test_eliminar_un_borrador_sin_movimientos_si_permite(self):
        """Eliminar queda para ventas sin asiento, cobro ni factura."""
        venta = VentaVehiculo.objects.create(
            vehiculo=self.vehiculo,
            tipo_cliente='PARTICULAR',
            cliente_nombre='Borrador',
            cliente_dni='12345678A',
            cliente_direccion='Calle 1',
            cliente_poblacion='Madrid',
            cliente_provincia='Madrid',
            cliente_cp='28001',
            cliente_telefono='600000000',
            fecha_venta='2026-11-20',
            metodo_pago='TRANSFERENCIA',
            precio_venta=Decimal('11500.00'),
            coste_total=Decimal('8000.00'),
            base_imponible=Decimal('8000.00'),
            cuota_iva=Decimal('2000.00'),
            created_by=self.admin,
        )

        respuesta = self.client.post(
            reverse('sales:delete', args=[venta.pk])
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(VentaVehiculo.objects.filter(pk=venta.pk).exists())

    def test_la_ficha_ofrece_anular_venta(self):
        self._vender()
        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)

        html = self.client.get(
            reverse('sales:detail', args=[venta.pk])
        ).content.decode()

        self.assertIn(reverse('sales:anular', args=[venta.pk]), html)
        self.assertIn('Anular venta', html)

    def test_la_reserva_guarda_los_datos_fiscales_del_comprador(self):
        reserva = self._crear_reserva()

        self.assertEqual(reserva.tipo_cliente, 'PARTICULAR')
        self.assertEqual(reserva.cliente_direccion, 'Calle Mayor 1')
        self.assertEqual(reserva.cliente_poblacion, 'Madrid')
        self.assertEqual(reserva.cliente_provincia, 'Madrid')
        self.assertEqual(reserva.cliente_cp, '28001')
        self.assertEqual(reserva.cliente_telefono, '612345678')
        self.assertEqual(reserva.cliente_email, 'carlos@example.com')
        self.assertEqual(reserva.metodo_pago, 'TRANSFERENCIA')

    def test_la_reserva_exige_direccion_fiscal(self):
        respuesta = self.client.post(reverse('bank:reserva_create'), {
            'vehiculo': self.vehiculo.pk,
            'tipo_cliente': 'PARTICULAR',
            'cliente_nombre': 'Carlos Ruiz',
            'cliente_dni': '12345678A',
            'cliente_direccion': '',
            'cliente_poblacion': '',
            'cliente_provincia': '',
            'cliente_cp': '',
            'cliente_telefono': '',
            'fecha_reserva': '2026-11-20',
            'importe_reserva': '1000.00',
            'metodo_pago': 'TRANSFERENCIA',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_factura_de_anticipo_con_numeracion_correlativa(self):
        from django.utils import timezone

        from apps.bank.models import FacturaReserva

        reserva = self._crear_reserva()
        respuesta = self.client.get(
            reverse('bank:reserva_factura', args=[reserva.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertTrue(respuesta.content.startswith(b'%PDF'))

        factura = FacturaReserva.objects.get(reserva=reserva)
        anio = timezone.localdate().year
        self.assertEqual(factura.codigo, f'A-{anio}-0001')

        # Reemitirla no cambia el número
        self.client.get(reverse('bank:reserva_factura', args=[reserva.pk]))
        self.assertEqual(FacturaReserva.objects.count(), 1)

        # Otra reserva toma el siguiente correlativo
        otro = Vehiculo.objects.create(
            matricula='5678DEF', bastidor='WVWZZZ1KZAW123456',
            marca='Seat', modelo='León', anio=2019, combustible='GASOLINA',
            kilometraje=120000, tipo_dano='ACCIDENTAL', etiqueta_ambiental='B',
            estado='EN_VENTA', fecha_adquisicion=date(2026, 10, 1),
            precio_subasta=Decimal('6000.00'), tasas_sala=Decimal('300.00'),
            logistica_grua=Decimal('200.00'), precio_venta=Decimal('9000.00'),
            created_by=self.admin,
        )
        self.vehiculo = otro
        segunda = self._crear_reserva(importe='500.00')
        self.client.get(reverse('bank:reserva_factura', args=[segunda.pk]))
        self.assertEqual(
            FacturaReserva.objects.get(reserva=segunda).codigo,
            f'A-{anio}-0002',
        )


    def test_la_ficha_de_la_reserva_muestra_datos_fiscales_y_factura(self):
        reserva = self._crear_reserva()

        respuesta = self.client.get(
            reverse('bank:reserva_detail', args=[reserva.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Datos fiscales del comprador')
        self.assertContains(respuesta, 'Calle Mayor 1')
        self.assertContains(respuesta, 'Factura de entrega a cuenta')
        self.assertContains(respuesta, 'Emitir factura de anticipo')

    def test_la_venta_precarga_los_datos_del_comprador_de_la_reserva(self):
        reserva = self._crear_reserva()

        respuesta = self.client.get(
            reverse('sales:create'),
            {'vehiculo': self.vehiculo.pk, 'reserva': reserva.pk},
        )

        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn('Carlos Ruiz', html)
        self.assertIn('12345678A', html)
        self.assertIn('Calle Mayor 1', html)
        self.assertIn('28001', html)
        self.assertIn('612345678', html)


class ImagenesAlVenderYAnularTests(TestCase):
    """Las fotos del vehículo no se tocan al vender ni al anular la venta."""

    def setUp(self):
        import shutil
        import tempfile
        from datetime import date
        from decimal import Decimal
        from io import BytesIO

        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings

        from apps.accounting.models import CuentaContable, PlanContableDefault
        from apps.bank.models import BancoCuenta
        from apps.sales.models import VentaVehiculo
        from apps.vehicles.models import ImagenVehiculo

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
            combustible='DIESEL', kilometraje=95000, tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='C', estado='EN_VENTA',
            fecha_adquisicion=date(2026, 10, 1),
            precio_subasta=Decimal('7500.00'), tasas_sala=Decimal('400.00'),
            logistica_grua=Decimal('250.00'), precio_venta=Decimal('11500.00'),
            created_by=self.admin,
        )

        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        self._media = override_settings(MEDIA_ROOT=media)
        self._media.enable()
        self.addCleanup(self._media.disable)

        def png(nombre):
            buf = BytesIO()
            Image.new('RGB', (30, 20), color='blue').save(buf, 'PNG')
            return SimpleUploadedFile(nombre, buf.getvalue(), content_type='image/png')

        self.vehiculo.imagen_principal = png('portada.png')
        self.vehiculo.save(update_fields=['imagen_principal'])

        self.fotos = [
            ImagenVehiculo.objects.create(
                vehiculo=self.vehiculo, orden=n + 1, imagen=png(f'foto{n + 1}.png')
            )
            for n in range(3)
        ]
        self.rutas = [self.vehiculo.imagen_principal.name] + [
            foto.imagen.name for foto in self.fotos
        ]

    def _existen_todos_los_archivos(self):
        from django.core.files.storage import default_storage

        return all(default_storage.exists(ruta) for ruta in self.rutas)

    def test_las_fotos_sobreviven_a_la_venta_y_a_la_anulacion(self):
        from apps.sales.models import VentaVehiculo
        from apps.vehicles.models import ImagenVehiculo

        self.assertTrue(self._existen_todos_los_archivos())

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
            'metodo_pago': 'TRANSFERENCIA',
            'precio_venta': '11500.00',
        })
        self.assertEqual(respuesta.status_code, 302)

        # Al vender: siguen los registros y los archivos
        self.assertEqual(ImagenVehiculo.objects.filter(vehiculo=self.vehiculo).count(), 3)
        self.assertTrue(self._existen_todos_los_archivos())

        venta = VentaVehiculo.objects.get(vehiculo=self.vehiculo)
        respuesta = self.client.post(
            reverse('sales:anular', args=[venta.pk]), {'motivo': 'Prueba'}
        )
        self.assertEqual(respuesta.status_code, 302)

        # Al anular: el coche vuelve a la venta con sus 5 fotos intactas
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'EN_VENTA')
        self.assertEqual(ImagenVehiculo.objects.filter(vehiculo=self.vehiculo).count(), 3)
        self.assertTrue(self.vehiculo.imagen_principal)
        self.assertTrue(self._existen_todos_los_archivos())


class DetalleRebuVariasFacturasTests(TestCase):
    """Un vehículo puede tener varios DetalleRebu (rectificativa o reventa).

    Regresión: `sales_detallerebu_vehiculo_id_key` al crear una rectificativa.
    """

    def setUp(self):
        from datetime import date
        from decimal import Decimal

        from apps.accounting.models import CuentaContable, PlanContableDefault
        from apps.bank.models import BancoCuenta
        from apps.vehicles.models import Vehiculo

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.client.force_login(self.admin)
        BancoCuenta.objects.create(
            nombre='Santander', iban='ES9121000418450200051332',
            cuenta_contable=CuentaContable.objects.get(codigo='572'),
        )
        self.vehiculo = Vehiculo.objects.create(
            matricula='1234ABC', bastidor='WVWZZZ3CZWE123456',
            marca='Volkswagen', modelo='Golf 1.6 TDI', anio=2020,
            combustible='DIESEL', kilometraje=95000, tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='C', estado='EN_VENTA',
            fecha_adquisicion=date(2026, 10, 1),
            precio_subasta=Decimal('7500.00'), tasas_sala=Decimal('400.00'),
            logistica_grua=Decimal('250.00'), precio_venta=Decimal('11500.00'),
            created_by=self.admin,
        )

    def _vender(self):
        self.client.post(reverse('sales:create'), {
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
        })
        return VentaVehiculo.objects.filter(
            vehiculo=self.vehiculo, anulada=False
        ).get()

    def test_la_rectificativa_no_duplica_el_detalle_rebu(self):
        from apps.sales.models import DetalleRebu
        from apps.sales.services import crear_factura_rectificativa, crear_factura_venta

        venta = self._vender()
        factura = crear_factura_venta(venta, self.admin)
        self.assertEqual(DetalleRebu.objects.filter(vehiculo=self.vehiculo).count(), 1)

        rectificativa = crear_factura_rectificativa(
            factura, 'R4', 'Devolución', self.admin
        )

        self.assertEqual(rectificativa.factura_rectificada_id, factura.pk)
        self.assertEqual(
            DetalleRebu.objects.filter(vehiculo=self.vehiculo).count(), 2
        )
        self.assertEqual(
            rectificativa.detalles_rebu.first().vehiculo_id, self.vehiculo.pk
        )


    def test_la_pantalla_de_rectificativa_r4_funciona(self):
        """Caso real: «Nueva Factura Rectificativa» con R4 sobre la factura."""
        from apps.sales.models import DetalleRebu, FacturaVenta
        from apps.sales.services import crear_factura_venta

        venta = self._vender()
        factura = crear_factura_venta(venta, self.admin)

        respuesta = self.client.post(
            reverse('sales:factura_rectificativa', args=[factura.pk]),
            {'tipo_rectificacion': 'R4', 'motivo': 'Devolución del vehículo'},
            follow=True,
        )

        self.assertEqual(respuesta.status_code, 200)
        rectificativa = FacturaVenta.objects.filter(
            tipo_factura='R4', factura_rectificada=factura
        ).first()
        self.assertIsNotNone(rectificativa)
        self.assertEqual(
            DetalleRebu.objects.filter(vehiculo=self.vehiculo).count(), 2
        )

    def test_el_mismo_vehiculo_se_puede_vender_otra_vez_tras_anular(self):
        from apps.sales.models import DetalleRebu, FacturaVenta
        from apps.sales.services import crear_factura_rectificativa, crear_factura_venta

        venta = self._vender()
        factura = crear_factura_venta(venta, self.admin)

        # Anular la venta (genera rectificativa) y volver a venderlo
        respuesta = self.client.post(
            reverse('sales:anular', args=[venta.pk]), {'motivo': 'Devolución'}
        )
        self.assertEqual(respuesta.status_code, 302)
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'EN_VENTA')

        segunda = self._vender()
        segunda_factura = crear_factura_venta(segunda, self.admin)

        self.assertNotEqual(segunda_factura.pk, factura.pk)
        self.assertEqual(
            DetalleRebu.objects.filter(vehiculo=self.vehiculo).count(), 3
        )
        self.assertEqual(FacturaVenta.objects.filter(tipo_factura='R1').count(), 1)
