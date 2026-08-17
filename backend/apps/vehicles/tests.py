import tempfile
from io import BytesIO
from PIL import Image
from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import User
from apps.vehicles.models import Vehiculo, ImagenVehiculo


def _png_bytes():
    buf = BytesIO()
    Image.new('RGB', (10, 10), color='red').save(buf, 'PNG')
    return buf.getvalue()


class VehiculoImagenesFormTests(TestCase):
    """La sección de imágenes aparece dinámicamente al seleccionar EN_VENTA."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@eurocar.local',
            password='admin123!',
            rol='ADMIN',
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
            estado='ACONDICIONADO',
            fecha_adquisicion='2026-07-01',
            precio_subasta=7500,
            tasas_sala=400,
            logistica_grua=250,
            created_by=self.admin,
        )
        self.datos = {
            'matricula': '1234ABC',
            'bastidor': 'WVWZZZ3CZWE123456',
            'marca': 'Volkswagen',
            'modelo': 'Golf',
            'anio': 2019,
            'combustible': 'DIESEL',
            'kilometraje': 85000,
            'tipo_dano': 'ACCIDENTAL',
            'etiqueta_ambiental': 'ECO',
            'fecha_adquisicion': '2026-07-01',
            'plataforma_subasta': '',
            'precio_subasta': '7500',
            'tasas_sala': '400',
            'logistica_grua': '250',
            'proveedor': '',
            'cif_nif': '',
            'numero_factura': '',
            'tipo_iva': '0',
            'forma_pago': '',
            'precio_venta': '0',
            'descripcion_dano': '',
        }

    def test_edicion_sin_en_venta_oculta_seccion_imagenes(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('vehicles:update', kwargs={'pk': self.vehiculo.pk})
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="imagenes-section"', html)
        self.assertIn('id="imagenes-aviso"', html)
        self.assertIn('id_imagenes-TOTAL_FORMS', html)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_post_en_venta_guarda_imagen_principal(self):
        from apps.accounting.models import PlanContableDefault
        PlanContableDefault.crear_plan_base()
        self.client.force_login(self.admin)
        datos = dict(self.datos, estado='EN_VENTA', precio_venta='11900')
        datos.update({
            'imagenes-TOTAL_FORMS': '1',
            'imagenes-INITIAL_FORMS': '0',
            'imagenes-MIN_NUM_FORMS': '0',
            'imagenes-MAX_NUM_FORMS': '1000',
            'imagenes-0-imagen': '',
            'imagenes-0-es_principal': '',
            'imagenes-0-orden': '1',
            'imagenes-0-id': '',
        })
        datos['imagen_principal'] = SimpleUploadedFile(
            'foto.png', _png_bytes(), content_type='image/png'
        )
        response = self.client.post(
            reverse('vehicles:update', kwargs={'pk': self.vehiculo.pk}), datos
        )
        self.assertEqual(response.status_code, 302)
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'EN_VENTA')
        self.assertTrue(self.vehiculo.imagen_principal)
        self.assertFalse(ImagenVehiculo.objects.filter(vehiculo=self.vehiculo).exists())

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_post_en_venta_guarda_imagen_adicional(self):
        from apps.accounting.models import PlanContableDefault
        PlanContableDefault.crear_plan_base()
        self.client.force_login(self.admin)
        datos = dict(self.datos, estado='EN_VENTA', precio_venta='11900')
        datos.update({
            'imagenes-TOTAL_FORMS': '1',
            'imagenes-INITIAL_FORMS': '0',
            'imagenes-MIN_NUM_FORMS': '0',
            'imagenes-MAX_NUM_FORMS': '1000',
            'imagenes-0-imagen': SimpleUploadedFile(
                'extra.png', _png_bytes(), content_type='image/png'
            ),
            'imagenes-0-es_principal': 'on',
            'imagenes-0-orden': '1',
            'imagenes-0-id': '',
        })
        response = self.client.post(
            reverse('vehicles:update', kwargs={'pk': self.vehiculo.pk}), datos
        )
        self.assertEqual(response.status_code, 302)
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'EN_VENTA')
        self.assertEqual(
            ImagenVehiculo.objects.filter(vehiculo=self.vehiculo).count(), 1
        )

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_post_sin_en_venta_no_guarda_imagen(self):
        self.client.force_login(self.admin)
        datos = dict(self.datos, estado='ACONDICIONADO')
        datos['imagen_principal'] = SimpleUploadedFile(
            'foto.png', _png_bytes(), content_type='image/png'
        )
        response = self.client.post(
            reverse('vehicles:update', kwargs={'pk': self.vehiculo.pk}), datos
        )
        self.assertEqual(response.status_code, 302)
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'ACONDICIONADO')
        self.assertFalse(self.vehiculo.imagen_principal)
        self.assertFalse(ImagenVehiculo.objects.filter(vehiculo=self.vehiculo).exists())
