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


def _png_bytes_grande(ancho, alto):
    buf = BytesIO()
    Image.new('RGB', (ancho, alto), color='blue').save(buf, 'PNG')
    return buf.getvalue()


class VehiculoFormEdicionTests(TestCase):
    """Formulario único de edición: importes, fotos y contabilidad."""

    def setUp(self):
        import shutil
        import tempfile
        from datetime import date
        from decimal import Decimal

        from django.test import override_settings

        from apps.accounting.models import PlanContableDefault

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.vehiculo = Vehiculo.objects.create(
            matricula='1234ABC', bastidor='WVWZZZ3CZWE123456',
            marca='Volkswagen', modelo='Golf', anio=2020,
            combustible='DIESEL', kilometraje=90000, tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='C', estado='EN_VENTA',
            fecha_adquisicion=date(2026, 7, 1),
            precio_subasta=Decimal('7500.00'), tasas_sala=Decimal('400.00'),
            logistica_grua=Decimal('250.00'), tipo_iva=Decimal('136.50'),
            precio_venta=Decimal('11900.00'),
            created_by=self.admin,
        )
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        self._media = override_settings(MEDIA_ROOT=media)
        self._media.enable()
        self.addCleanup(self._media.disable)
        self.client.force_login(self.admin)

    def _datos(self, **extra):
        datos = {
            'matricula': '1234ABC', 'bastidor': 'WVWZZZ3CZWE123456',
            'marca': 'Volkswagen', 'modelo': 'Golf', 'anio': '2020',
            'combustible': 'DIESEL', 'kilometraje': '90000',
            'tipo_dano': 'ACCIDENTAL', 'etiqueta_ambiental': 'C',
            'estado': 'EN_VENTA', 'fecha_adquisicion': '2026-07-01',
            'plataforma_subasta': '', 'precio_subasta': '7.500,00',
            'tasas_sala': '400,00', 'logistica_grua': '250,00',
            'proveedor': 'Subastas Online', 'cif_nif': 'B12345678',
            'numero_factura': 'FC-1', 'tipo_iva': '136,50',
            'forma_pago': '', 'precio_venta': '11.900,00',
            'descripcion_dano': 'Buen estado',
            'imagenes-TOTAL_FORMS': '0', 'imagenes-INITIAL_FORMS': '0',
            'imagenes-MIN_NUM_FORMS': '0', 'imagenes-MAX_NUM_FORMS': '15',
        }
        datos.update(extra)
        return datos

    def _editar(self, **extra):
        return self.client.post(
            reverse('vehicles:update', args=[self.vehiculo.pk]),
            self._datos(**extra),
        )

    # ------------------------------------------------------- formato
    def test_el_formulario_muestra_importes_y_fecha_correctos(self):
        from apps.vehicles.forms import VehiculoForm

        form = VehiculoForm(instance=self.vehiculo)
        self.assertIn('value="7.500,00"', str(form['precio_subasta']))
        self.assertIn('value="11.900,00"', str(form['precio_venta']))
        self.assertIn('value="2026-07-01"', str(form['fecha_adquisicion']))

    def test_editar_muestra_el_formulario_completo(self):
        respuesta = self.client.get(
            reverse('vehicles:update', args=[self.vehiculo.pk])
        )
        self.assertEqual(respuesta.status_code, 200)
        for campo in ('precio_subasta', 'precio_venta', 'descripcion_dano',
                      'imagen_principal'):
            self.assertContains(respuesta, f'name="{campo}"')
        self.assertContains(respuesta, 'imagenes-TOTAL_FORMS')

    def test_acepta_formato_espanol_y_estandar(self):
        from decimal import Decimal

        from apps.vehicles.forms import VehiculoForm

        espanol = VehiculoForm(self._datos(), instance=self.vehiculo)
        self.assertTrue(espanol.is_valid(), espanol.errors)
        self.assertEqual(espanol.cleaned_data['precio_subasta'], Decimal('7500.00'))

        estandar = VehiculoForm(
            self._datos(precio_subasta='7500.00', tasas_sala='400.00',
                        logistica_grua='250.00'),
            instance=self.vehiculo,
        )
        self.assertTrue(estandar.is_valid(), estandar.errors)
        self.assertEqual(estandar.cleaned_data['precio_subasta'], Decimal('7500.00'))

    def test_guardar_dos_veces_no_multiplica_el_importe(self):
        """Regresión del ×10.000: repetir el guardado no altera los costes."""
        from decimal import Decimal

        self._editar()
        self._editar()

        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.precio_subasta, Decimal('7500.00'))
        self.assertEqual(self.vehiculo.tasas_sala, Decimal('400.00'))
        self.assertEqual(self.vehiculo.coste_inicial, Decimal('8150.00'))

    def test_la_ruta_publicar_ya_no_existe(self):
        respuesta = self.client.get(
            f'/erp/vehiculos/{self.vehiculo.pk}/publicar/'
        )
        self.assertEqual(respuesta.status_code, 404)

    # ------------------------------------------------------- imágenes
    def test_guarda_la_imagen_principal(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        respuesta = self._editar(imagen_principal=SimpleUploadedFile(
            'portada.png', _png_bytes(), content_type='image/png'
        ))
        self.assertEqual(respuesta.status_code, 302)

        self.vehiculo.refresh_from_db()
        self.assertTrue(self.vehiculo.imagen_principal)
        self.assertTrue(
            self.vehiculo.imagen_principal.name.startswith('vehiculos/1234abc/'),
            f'Ruta inesperada: {self.vehiculo.imagen_principal.name}',
        )

    def test_guarda_una_imagen_adicional(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        respuesta = self._editar(**{
            'imagenes-TOTAL_FORMS': '1',
            'imagenes-0-orden': '1',
            'imagenes-0-imagen': SimpleUploadedFile(
                'foto.png', _png_bytes(), content_type='image/png'
            ),
        })
        self.assertEqual(respuesta.status_code, 302)

        imagenes = list(ImagenVehiculo.objects.filter(vehiculo=self.vehiculo))
        self.assertEqual(len(imagenes), 1)
        self.assertTrue(imagenes[0].imagen.name.startswith('vehiculos/1234abc/'))

    def test_avisa_al_superar_el_maximo_de_imagenes(self):
        respuesta = self._editar(**{'imagenes-TOTAL_FORMS': '16'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'el máximo es 15')

    def test_cambiar_de_estado_conserva_las_fotos(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        ImagenVehiculo.objects.create(
            vehiculo=self.vehiculo, orden=1,
            imagen=SimpleUploadedFile('f.png', _png_bytes(), content_type='image/png'),
        )
        respuesta = self._editar(estado='ACONDICIONADO')
        self.assertEqual(respuesta.status_code, 302)

        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'ACONDICIONADO')
        self.assertEqual(
            ImagenVehiculo.objects.filter(vehiculo=self.vehiculo).count(), 1
        )

    def _foto(self, nombre='vieja.png'):
        from io import BytesIO

        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        buf = BytesIO()
        Image.new('RGB', (400, 300), color='blue').save(buf, 'PNG')
        return ImagenVehiculo.objects.create(
            vehiculo=self.vehiculo, orden=1,
            imagen=SimpleUploadedFile(nombre, buf.getvalue(), content_type='image/png'),
        )

    def test_eliminar_foto_cuyo_archivo_ya_no_existe(self):
        """Marcar Eliminar en una foto perdida no debe fallar."""
        from django.core.files.storage import default_storage

        foto = self._foto()
        default_storage.delete(foto.imagen.name)
        self.assertFalse(default_storage.exists(foto.imagen.name))

        respuesta = self._editar(**{
            'imagenes-TOTAL_FORMS': '1',
            'imagenes-INITIAL_FORMS': '1',
            'imagenes-0-id': str(foto.pk),
            'imagenes-0-orden': '1',
            'imagenes-0-DELETE': 'on',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(ImagenVehiculo.objects.filter(pk=foto.pk).exists())

    def test_guardar_sin_tocar_fotos_no_lee_el_archivo(self):
        from django.core.files.storage import default_storage

        foto = self._foto()
        nombre_original = foto.imagen.name
        default_storage.delete(nombre_original)

        respuesta = self._editar(**{
            'imagenes-TOTAL_FORMS': '1',
            'imagenes-INITIAL_FORMS': '1',
            'imagenes-0-id': str(foto.pk),
            'imagenes-0-orden': '1',
        })
        self.assertEqual(respuesta.status_code, 302)

        foto.refresh_from_db()
        self.assertEqual(foto.imagen.name, nombre_original)

    # --------------------------------------------------- contabilidad
    def test_editar_importe_regenera_el_asiento_con_contrapartida(self):
        from decimal import Decimal

        from apps.accounting.models import AsientoContable

        asiento_viejo = self.vehiculo.crear_asiento_contable()
        self.assertEqual(asiento_viejo.estado, 'POSTEADO')

        respuesta = self._editar(precio_subasta='8.500,00')
        self.assertEqual(respuesta.status_code, 302)

        asiento_viejo.refresh_from_db()
        self.assertEqual(asiento_viejo.estado, 'ANULADO')
        self.assertTrue(
            AsientoContable.objects.filter(tipo_documento='AnulacionVehiculo').exists()
        )

        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.precio_subasta, Decimal('8500.00'))
        self.assertEqual(self.vehiculo.coste_inicial, Decimal('9150.00'))
        nuevo = self.vehiculo.asiento_contable
        self.assertIsNotNone(nuevo)
        self.assertNotEqual(nuevo.pk, asiento_viejo.pk)
        self.assertEqual(nuevo.estado, 'POSTEADO')

    def test_editar_siempre_regenera_el_asiento(self):
        """Guardar el vehículo rehace la contabilidad (sin mensajes de "no cambió")."""
        from apps.accounting.models import AsientoContable

        asiento = self.vehiculo.crear_asiento_contable()

        respuesta = self._editar(kilometraje='150000')
        self.assertEqual(respuesta.status_code, 302)

        asiento.refresh_from_db()
        self.assertEqual(asiento.estado, 'ANULADO')
        self.assertTrue(
            AsientoContable.objects.filter(tipo_documento='AnulacionVehiculo').exists()
        )
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.kilometraje, 150000)
        self.assertNotEqual(self.vehiculo.asiento_contable_id, asiento.pk)
        self.assertEqual(self.vehiculo.asiento_contable.estado, 'POSTEADO')

    def test_parseo_de_importes_sin_ambiguedad(self):
        """7.500 son siete mil quinientos; 7.500,50 son 7500,50."""
        from decimal import Decimal

        from apps.vehicles.forms import parsear_importe

        self.assertEqual(parsear_importe('7500'), Decimal('7500'))
        self.assertEqual(parsear_importe('7500.00'), Decimal('7500.00'))
        self.assertEqual(parsear_importe('7500,00'), Decimal('7500.00'))
        self.assertEqual(parsear_importe('7.500'), Decimal('7500'))
        self.assertEqual(parsear_importe('7.500,00'), Decimal('7500.00'))
        self.assertEqual(parsear_importe('7.500,50'), Decimal('7500.50'))
        self.assertEqual(parsear_importe('1.234.567,89'), Decimal('1234567.89'))


class CorregirCosteVehiculoCommandTests(TestCase):
    """El comando de reparación corrige importes y regenera el asiento."""

    def setUp(self):
        from datetime import date
        from decimal import Decimal

        from apps.accounting.models import PlanContableDefault

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        # Importes corrompidos por el antiguo bug (×10.000)
        self.vehiculo = Vehiculo.objects.create(
            matricula='1234ABC', bastidor='WVWZZZ3CZWE123456',
            marca='Volkswagen', modelo='Golf', anio=2020,
            combustible='DIESEL', kilometraje=90000, tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='C', estado='EN_VENTA',
            fecha_adquisicion=date(2026, 7, 1),
            precio_subasta=Decimal('75000000.00'),
            tasas_sala=Decimal('4000000.00'),
            logistica_grua=Decimal('2500000.00'),
            tipo_iva=Decimal('1365000.00'),
            created_by=self.admin,
        )
        self.asiento_viejo = self.vehiculo.crear_asiento_contable()

    def test_corrige_importes_y_regenera_el_asiento(self):
        from decimal import Decimal

        from django.core.management import call_command

        from apps.accounting.models import AsientoContable

        call_command(
            'corregir_coste_vehiculo', '1234ABC',
            '--precio-subasta', '7.500,00',
            '--tasas', '400',
            '--grua', '250',
            '--tipo-iva', '136,50',
            verbosity=0,
        )

        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.precio_subasta, Decimal('7500.00'))
        self.assertEqual(self.vehiculo.tasas_sala, Decimal('400.00'))
        self.assertEqual(self.vehiculo.logistica_grua, Decimal('250.00'))
        self.assertEqual(self.vehiculo.coste_inicial, Decimal('8150.00'))
        self.assertEqual(self.vehiculo.cuota_iva, Decimal('136.50'))

        self.asiento_viejo.refresh_from_db()
        self.assertEqual(self.asiento_viejo.estado, 'ANULADO')
        self.assertTrue(
            AsientoContable.objects.filter(
                tipo_documento='AnulacionVehiculo'
            ).exists()
        )

        nuevo = self.vehiculo.asiento_contable
        self.assertIsNotNone(nuevo)
        self.assertEqual(nuevo.estado, 'POSTEADO')
        self.assertEqual(nuevo.total_debe, Decimal('8286.50'))

    def test_matricula_inexistente_da_error(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                'corregir_coste_vehiculo', '9999ZZZ',
                '--precio-subasta', '1', '--tasas', '1', '--grua', '1',
                verbosity=0,
            )
