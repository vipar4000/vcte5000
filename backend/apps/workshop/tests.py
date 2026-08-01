import unittest
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.db import connections
from apps.accounts.models import User
from apps.vehicles.models import Vehiculo
from apps.accounting.models import PlanContableDefault
from apps.workshop.models import Material


class OrdenTrabajoFormTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@eurocar.local',
            password='admin123!',
            rol='ADMIN',
        )
        self.operario = User.objects.create_user(
            username='mecanico1',
            email='mecanico1@eurocar.local',
            password='mecanico123!',
            rol='OPERARIO',
            salario_base_mensual=1800,
            pin_kiosco='1234',
        )
        self.vehiculo = Vehiculo.objects.create(
            matricula='1234ABC',
            bastidor='WVWZZZ3CZWE123456',
            marca='Volkswagen',
            modelo='Golf',
            anio=2019,
            combustible='DIESEL',
            kilometraje=85000,
            tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='ECO',
            estado='ADQUIRIDO',
            fecha_adquisicion='2026-07-01',
            precio_subasta=7500,
            tasas_sala=400,
            logistica_grua=250,
            created_by=self.admin,
        )

    def test_form_renderiza_operarios(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('workshop:create_ot'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="id_operario"', html)
        self.assertIn('mecanico1 (Operario de Taller)', html)
        self.assertIn(f'value="{self.operario.pk}"', html)

    def test_crear_ot_cambia_estado_vehiculo(self):
        self.client.force_login(self.admin)
        data = {
            'vehiculo': self.vehiculo.pk,
            'operario': self.operario.pk,
            'titulo': 'Diagnóstico general',
            'descripcion': 'Revisión general',
            'horas_estimadas': 4,
            'horas_reales': 0,
            'estado': 'PENDIENTE',
        }
        response = self.client.post(reverse('workshop:create_ot'), data)
        self.assertEqual(response.status_code, 302)
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'TALLER')

    @unittest.skipIf(
        'sqlite' in connections.databases['default']['ENGINE'].lower(),
        'SQLite compartido en memoria no ve datos entre requests del cliente en TestCase'
    )
    def test_completar_ot_desde_edicion_genera_asiento(self):
        """Completar una OT desde el formulario de edición genera el asiento contable."""
        from apps.accounting.models import PlanContableDefault
        PlanContableDefault.crear_plan_base()

        self.client.force_login(self.admin)
        # Crear la OT via el formulario (mismo cliente/connection que la vista)
        create_data = {
            'vehiculo': self.vehiculo.pk,
            'operario': self.operario.pk,
            'titulo': 'Diagnóstico general',
            'descripcion': 'Revisión general',
            'horas_estimadas': 4,
            'horas_reales': 0,
            'estado': 'PENDIENTE',
        }
        response = self.client.post(reverse('workshop:create_ot'), create_data)
        self.assertEqual(response.status_code, 302)
        from apps.workshop.models import OrdenTrabajo
        ot = OrdenTrabajo.objects.get()
        self.assertEqual(ot.estado, 'PENDIENTE')

        data = {
            'vehiculo': self.vehiculo.pk,
            'operario': self.operario.pk,
            'titulo': 'Diagnóstico general',
            'descripcion': 'Revisión general',
            'horas_estimadas': 4,
            'horas_reales': 3,
            'estado': 'COMPLETADA',
        }
        response = self.client.post(
            reverse('workshop:update_ot', kwargs={'pk': ot.pk}), data
        )
        self.assertEqual(response.status_code, 302)
        from apps.accounting.models import AsientoContable
        ot.refresh_from_db()
        asiento = AsientoContable.objects.filter(
            tipo_documento='OrdenTrabajo', documento_id=ot.pk
        ).first()
        self.assertIsNotNone(asiento)
        self.assertEqual(asiento.estado, 'POSTEADO')
        self.assertTrue(asiento.esta_cuadrado)


class OrdenTrabajoCosteTests(TestCase):
    def setUp(self):
        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@eurocar.local',
            password='admin123!',
            rol='ADMIN',
        )
        self.operario = User.objects.create_user(
            username='mecanico1',
            email='mecanico1@eurocar.local',
            password='mecanico123!',
            rol='OPERARIO',
            salario_base_mensual=1800,
            porcentaje_ss_patronal=31.50,
            pin_kiosco='1234',
        )
        self.vehiculo = Vehiculo.objects.create(
            matricula='1234ABC',
            bastidor='WVWZZZ3CZWE123456',
            marca='Volkswagen',
            modelo='Golf',
            anio=2019,
            combustible='DIESEL',
            kilometraje=85000,
            tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='ECO',
            estado='ADQUIRIDO',
            fecha_adquisicion='2026-07-01',
            precio_subasta=7500,
            tasas_sala=400,
            logistica_grua=250,
            created_by=self.admin,
        )
        self.aceite = Material.objects.create(
            nombre='Aceite', unidad='litros', stock_actual=20,
            stock_minimo=5, precio_unitario=8.50,
        )

    def test_coste_hora_redondeado_a_dos_decimales(self):
        self.assertEqual(self.operario.coste_hora.as_tuple().exponent, -2)

    def test_costes_ot_redondeados_a_dos_decimales(self):
        from apps.workshop.models import OrdenTrabajo
        ot = OrdenTrabajo.objects.create(
            vehiculo=self.vehiculo,
            operario=self.operario,
            titulo='Diagnóstico',
            descripcion='Revisión',
            horas_estimadas=4,
            horas_reales=3,
            estado='PENDIENTE',
            created_by=self.admin,
        )
        ot.materiales_usados.create(material=self.aceite, cantidad=5)

        self.assertEqual(ot.coste_mano_obra.as_tuple().exponent, -2)
        self.assertEqual(ot.coste_materiales.as_tuple().exponent, -2)
        self.assertEqual(ot.coste_total.as_tuple().exponent, -2)
        self.assertEqual(ot.coste_materiales, Decimal('42.50'))
        self.assertEqual(ot.coste_mano_obra, Decimal('40.35'))
        self.assertEqual(ot.coste_total, Decimal('82.85'))

    def test_crear_asiento_ot_desde_modelo(self):
        from apps.workshop.models import OrdenTrabajo
        from apps.accounting.models import AsientoContable
        ot = OrdenTrabajo.objects.create(
            vehiculo=self.vehiculo,
            operario=self.operario,
            titulo='Diagnóstico',
            descripcion='Revisión',
            horas_estimadas=4,
            horas_reales=3,
            estado='COMPLETADA',
            created_by=self.admin,
        )
        ot.materiales_usados.create(material=self.aceite, cantidad=5)
        asiento = ot.crear_asiento_contable()

        self.assertIsNotNone(asiento)
        self.assertEqual(asiento.estado, 'POSTEADO')
        self.assertTrue(asiento.esta_cuadrado)
        movimientos = asiento.movimientos.all()
        self.assertEqual(movimientos.count(), 3)
        total_debe = sum(m.debe for m in movimientos)
        total_haber = sum(m.haber for m in movimientos)
        self.assertEqual(total_debe, total_haber)
        self.assertEqual(total_debe, ot.coste_total)


class CompraMaterialTests(TestCase):
    def setUp(self):
        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@eurocar.local',
            password='admin123!',
            rol='ADMIN',
        )
        self.aceite = Material.objects.create(
            nombre='Aceite motor 5W30',
            unidad='litros',
            stock_actual=0,
            stock_minimo=5,
            precio_unitario=8.50,
        )
        self.pastillas = Material.objects.create(
            nombre='Pastillas de freno',
            unidad='juegos',
            stock_actual=0,
            stock_minimo=1,
            precio_unitario=35.00,
        )

    def test_compra_material_con_linea_vacia_no_falla(self):
        """Una línea rellena y otra vacía debe procesar solo la rellena."""
        self.client.force_login(self.admin)
        url = reverse('workshop:compra_material_create')
        data = {
            'proveedor': 'Distribuciones Auto S.L.',
            'cif_nif': 'B12345678',
            'fecha_compra': '2026-07-01',
            'numero_factura': 'FC-AUTO-2026-001',
            'tipo_inventario': '300',
            'tipo_iva': '21.00',
            'lineas-TOTAL_FORMS': '2',
            'lineas-INITIAL_FORMS': '0',
            'lineas-MIN_NUM_FORMS': '0',
            'lineas-MAX_NUM_FORMS': '1000',
            'lineas-0-material': str(self.aceite.pk),
            'lineas-0-cantidad': '20',
            'lineas-0-precio_unitario': '8.50',
            'lineas-0-DELETE': '',
            'lineas-1-material': '',
            'lineas-1-cantidad': '',
            'lineas-1-precio_unitario': '',
            'lineas-1-DELETE': '',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.stock_actual, 20)
        self.pastillas.refresh_from_db()
        self.assertEqual(self.pastillas.stock_actual, 0)
