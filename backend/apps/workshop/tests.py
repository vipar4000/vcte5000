from django.test import TestCase, Client
from django.urls import reverse
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
