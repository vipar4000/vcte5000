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


class VehiculoImagenesPublicacionTests(TestCase):
    """Fotos del vehículo desde la pantalla Publicar (la única que las edita)."""

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
            etiqueta_ambiental='EC', estado='ACONDICIONADO',
            fecha_adquisicion=date(2026, 7, 1),
            precio_subasta=Decimal('7500.00'), tasas_sala=Decimal('400.00'),
            logistica_grua=Decimal('250.00'), tipo_iva=Decimal('136.50'),
            created_by=self.admin,
        )
        self.client.force_login(self.admin)

        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        self._media = override_settings(MEDIA_ROOT=media)
        self._media.enable()
        self.addCleanup(self._media.disable)

    def _publicar(self, **extra):
        datos = {
            'estado': 'EN_VENTA',
            'precio_venta': '11.900,00',
            'descripcion_dano': 'Buen estado',
            'imagenes-TOTAL_FORMS': '0',
            'imagenes-INITIAL_FORMS': '0',
            'imagenes-MIN_NUM_FORMS': '0',
            'imagenes-MAX_NUM_FORMS': '15',
        }
        datos.update(extra)
        return self.client.post(
            reverse('vehicles:publicar', args=[self.vehiculo.pk]), datos
        )

    def test_publicar_guarda_la_imagen_principal(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        respuesta = self._publicar(imagen_principal=SimpleUploadedFile(
            'portada.png', _png_bytes(), content_type='image/png'
        ))
        self.assertEqual(respuesta.status_code, 302)

        self.vehiculo.refresh_from_db()
        self.assertTrue(self.vehiculo.imagen_principal)
        self.assertTrue(
            self.vehiculo.imagen_principal.name.startswith('vehiculos/1234abc/'),
            f'Ruta inesperada: {self.vehiculo.imagen_principal.name}',
        )

    def test_publicar_guarda_una_imagen_adicional(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        respuesta = self._publicar(**{
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

    def test_publicar_avisa_al_superar_el_maximo_de_imagenes(self):
        respuesta = self._publicar(**{'imagenes-TOTAL_FORMS': '16'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'el máximo es 15')

    def test_cambiar_de_estado_conserva_las_fotos(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        ImagenVehiculo.objects.create(
            vehiculo=self.vehiculo, orden=1,
            imagen=SimpleUploadedFile('f.png', _png_bytes(), content_type='image/png'),
        )
        respuesta = self._publicar(estado='ACONDICIONADO')
        self.assertEqual(respuesta.status_code, 302)

        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'ACONDICIONADO')
        self.assertEqual(
            ImagenVehiculo.objects.filter(vehiculo=self.vehiculo).count(), 1
        )

    def test_editar_muestra_el_formulario_completo(self):
        """Un solo formulario: técnicos, compra, precio de venta y fotos."""
        respuesta = self.client.get(
            reverse('vehicles:update', args=[self.vehiculo.pk])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'name="precio_subasta"')
        self.assertContains(respuesta, 'name="precio_venta"')
        self.assertContains(respuesta, 'name="descripcion_dano"')
        self.assertContains(respuesta, 'name="imagen_principal"')
        self.assertContains(respuesta, 'imagenes-TOTAL_FORMS')


class VehiculoFormatoYPublicacionTest(TestCase):
    """Formato de importes/fecha, publicación comercial y bloqueo contable."""

    def setUp(self):
        from datetime import date
        from decimal import Decimal

        from apps.accounting.models import PlanContableDefault

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.vendedor = User.objects.create_user(
            username='vendedor1', email='v1@eurocar.local',
            password='vendedor123!', rol='VENDEDOR',
        )
        self.vehiculo = Vehiculo.objects.create(
            matricula='1234ABC', bastidor='WVWZZZ3CZWE123456',
            marca='Volkswagen', modelo='Golf', anio=2020,
            combustible='DIESEL', kilometraje=100000, tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='C', estado='ACONDICIONADO',
            fecha_adquisicion=date(2026, 7, 1),
            precio_subasta=Decimal('7500.00'), tasas_sala=Decimal('400.00'),
            logistica_grua=Decimal('250.00'), tipo_iva=Decimal('136.50'),
            precio_venta=Decimal('11900.00'),
            created_by=self.admin,
        )

    def _datos_tecnicos(self, **extra):
        datos = {
            'matricula': '1234ABC', 'bastidor': 'WVWZZZ3CZWE123456',
            'marca': 'Volkswagen', 'modelo': 'Golf', 'anio': '2020',
            'combustible': 'DIESEL', 'kilometraje': '100000',
            'tipo_dano': 'ACCIDENTAL', 'etiqueta_ambiental': 'C',
            'estado': 'ACONDICIONADO', 'fecha_adquisicion': '2026-07-01',
            'plataforma_subasta': '', 'precio_subasta': '7.500,00',
            'tasas_sala': '400,00', 'logistica_grua': '250,00',
            'proveedor': 'Subastas Online', 'cif_nif': 'B12345678',
            'numero_factura': 'FC-1', 'tipo_iva': '136,50',
            'forma_pago': '',
            'descripcion_dano': '',
        }
        datos.update(extra)
        return datos

    def test_el_formulario_muestra_importes_y_fecha_correctos(self):
        from apps.vehicles.forms import VehiculoForm

        form = VehiculoForm(instance=self.vehiculo)
        self.assertIn('value="7.500,00"', str(form['precio_subasta']))
        self.assertIn('value="2026-07-01"', str(form['fecha_adquisicion']))

    def test_acepta_formato_espanol_y_estandar(self):
        from decimal import Decimal

        from apps.vehicles.forms import VehiculoForm

        espanol = VehiculoForm(self._datos_tecnicos(), instance=self.vehiculo)
        self.assertTrue(espanol.is_valid(), espanol.errors)
        self.assertEqual(espanol.cleaned_data['precio_subasta'], Decimal('7500.00'))
        self.assertEqual(espanol.cleaned_data['logistica_grua'], Decimal('250.00'))

        estandar = VehiculoForm(self._datos_tecnicos(
            precio_subasta='7500.00', tasas_sala='400.00',
            logistica_grua='250.00', precio_venta='11900.00',
        ), instance=self.vehiculo)
        self.assertTrue(estandar.is_valid(), estandar.errors)
        self.assertEqual(estandar.cleaned_data['precio_subasta'], Decimal('7500.00'))

    def test_guardar_dos_veces_no_multiplica_el_importe(self):
        """Regresión del ×10.000: repetir el guardado no altera los costes."""
        from decimal import Decimal

        self.client.force_login(self.admin)
        url = reverse('vehicles:update', args=[self.vehiculo.pk])

        for _ in range(2):
            respuesta = self.client.post(url, self._datos_tecnicos())
            self.assertEqual(respuesta.status_code, 302)

        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.precio_subasta, Decimal('7500.00'))
        self.assertEqual(self.vehiculo.coste_inicial, Decimal('8150.00'))

    def test_publicar_solo_cambia_datos_comerciales(self):
        from decimal import Decimal

        self.client.force_login(self.vendedor)
        datos = {
            'estado': 'EN_VENTA',
            'precio_venta': '11.900,00',
            'descripcion_dano': 'Buen estado, un solo dueño.',
            'imagenes-TOTAL_FORMS': '0',
            'imagenes-INITIAL_FORMS': '0',
            'imagenes-MIN_NUM_FORMS': '0',
            'imagenes-MAX_NUM_FORMS': '15',
        }
        respuesta = self.client.post(
            reverse('vehicles:publicar', args=[self.vehiculo.pk]), datos
        )
        self.assertEqual(respuesta.status_code, 302)

        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'EN_VENTA')
        self.assertEqual(self.vehiculo.precio_venta, Decimal('11900.00'))
        # Los costes de compra no se tocan desde la pantalla comercial
        self.assertEqual(self.vehiculo.precio_subasta, Decimal('7500.00'))
        self.assertEqual(self.vehiculo.coste_inicial, Decimal('8150.00'))

    def test_operario_no_puede_publicar(self):
        operario = User.objects.create_user(
            username='mecanico1', email='m1@eurocar.local',
            password='mecanico123!', rol='OPERARIO',
        )
        self.client.force_login(operario)
        respuesta = self.client.get(
            reverse('vehicles:publicar', args=[self.vehiculo.pk])
        )
        self.assertEqual(respuesta.status_code, 302)

    def test_editar_importe_regenera_el_asiento_con_contrapartida(self):
        """Al cambiar un importe se anula el asiento y se crea el nuevo."""
        from decimal import Decimal

        from apps.accounting.models import AsientoContable

        self.client.force_login(self.admin)
        asiento_viejo = self.vehiculo.crear_asiento_contable()
        self.assertEqual(asiento_viejo.estado, 'POSTEADO')

        respuesta = self.client.post(
            reverse('vehicles:update', args=[self.vehiculo.pk]),
            self._datos_tecnicos(precio_subasta='8.500,00'),
        )
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
        self.assertEqual(nuevo.total_debe, Decimal('9286.50'))

    def test_editar_sin_cambiar_importes_conserva_el_asiento(self):
        """Guardar un dato técnico no rehace la contabilidad."""
        self.client.force_login(self.admin)
        asiento = self.vehiculo.crear_asiento_contable()

        datos = self._datos_tecnicos()
        datos['kilometraje'] = '150000'
        respuesta = self.client.post(
            reverse('vehicles:update', args=[self.vehiculo.pk]), datos
        )
        self.assertEqual(respuesta.status_code, 302)

        asiento.refresh_from_db()
        self.assertEqual(asiento.estado, 'POSTEADO')
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.kilometraje, 150000)
        self.assertEqual(self.vehiculo.asiento_contable_id, asiento.pk)

    def test_publicar_no_devuelve_500_si_falla_el_guardado(self):
        """La vista informa del error en vez de romper con un 500."""
        from unittest.mock import patch

        from apps.vehicles.forms import VehiculoComercialForm

        self.client.force_login(self.admin)
        datos = {
            'estado': 'EN_VENTA', 'precio_venta': '11.900,00',
            'descripcion_dano': 'x',
            'imagenes-TOTAL_FORMS': '0', 'imagenes-INITIAL_FORMS': '0',
            'imagenes-MIN_NUM_FORMS': '0', 'imagenes-MAX_NUM_FORMS': '15',
        }
        with patch.object(
            VehiculoComercialForm, 'save', side_effect=RuntimeError('fallo simulado')
        ):
            respuesta = self.client.post(
                reverse('vehicles:publicar', args=[self.vehiculo.pk]), datos
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'No se pudieron guardar los datos comerciales')
        self.assertContains(respuesta, 'fallo simulado')
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'ACONDICIONADO')

    def test_publicar_con_foto_reemplazada_y_error_no_rompe(self):
        """Regresión: re-renderizar con una foto nueva sin guardar no debe fallar."""
        from io import BytesIO

        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.vehicles.forms import ImagenVehiculoForm
        from django.test import override_settings
        import tempfile
        import shutil

        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)

        def png(color):
            buf = BytesIO()
            Image.new('RGB', (400, 300), color=color).save(buf, 'PNG')
            return buf.getvalue()

        with override_settings(MEDIA_ROOT=media):
            from apps.vehicles.models import ImagenVehiculo

            foto = ImagenVehiculo.objects.create(
                vehiculo=self.vehiculo, orden=1,
                imagen=SimpleUploadedFile('v.png', png('blue'), content_type='image/png'),
            )
            self.client.force_login(self.admin)
            datos = {
                'estado': 'ESTADO_QUE_NO_EXISTE',  # fuerza re-render con errores
                'precio_venta': '11.900,00', 'descripcion_dano': 'x',
                'imagenes-TOTAL_FORMS': '2', 'imagenes-INITIAL_FORMS': '1',
                'imagenes-MIN_NUM_FORMS': '0', 'imagenes-MAX_NUM_FORMS': '15',
                'imagenes-0-id': str(foto.pk), 'imagenes-0-orden': '1',
                'imagenes-1-orden': '',
                'imagenes-0-imagen': SimpleUploadedFile(
                    'nueva.png', png('green'), content_type='image/png'
                ),
            }
            respuesta = self.client.post(
                reverse('vehicles:publicar', args=[self.vehiculo.pk]), datos
            )
            self.assertEqual(respuesta.status_code, 200)

            # El formulario vuelve a mostrar la miniatura de la foto guardada
            form = respuesta.context['imagenes_formset'].forms[0]
            self.assertIsInstance(form, ImagenVehiculoForm)
            self.assertTrue(form.url_actual().startswith('/media/'))

    # ---------------------- borrado de fotos con archivo perdido
    def _media_temporal(self):
        import shutil
        import tempfile

        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        return media

    def _foto(self, nombre='vieja.png'):
        from io import BytesIO

        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.vehicles.models import ImagenVehiculo

        buf = BytesIO()
        Image.new('RGB', (400, 300), color='blue').save(buf, 'PNG')
        return ImagenVehiculo.objects.create(
            vehiculo=self.vehiculo, orden=1,
            imagen=SimpleUploadedFile(nombre, buf.getvalue(), content_type='image/png'),
        )

    def test_eliminar_foto_cuyo_archivo_ya_no_existe(self):
        """Regresión: marcar Eliminar en una foto perdida daba 500.

        La validación re-procesaba la imagen guardada e intentaba leer un
        archivo que el despliegue ya se había llevado.
        """
        from django.core.files.storage import default_storage
        from django.test import override_settings

        from apps.vehicles.models import ImagenVehiculo

        media = self._media_temporal()
        with override_settings(MEDIA_ROOT=media):
            foto = self._foto()
            default_storage.delete(foto.imagen.name)
            self.assertFalse(default_storage.exists(foto.imagen.name))

            self.client.force_login(self.admin)
            datos = {
                'estado': 'EN_VENTA', 'precio_venta': '11.900,00',
                'descripcion_dano': 'x',
                'imagenes-TOTAL_FORMS': '1', 'imagenes-INITIAL_FORMS': '1',
                'imagenes-MIN_NUM_FORMS': '0', 'imagenes-MAX_NUM_FORMS': '15',
                'imagenes-0-id': str(foto.pk),
                'imagenes-0-orden': '1',
                'imagenes-0-DELETE': 'on',
            }
            respuesta = self.client.post(
                reverse('vehicles:publicar', args=[self.vehiculo.pk]), datos
            )
            self.assertEqual(respuesta.status_code, 302)
            self.assertFalse(ImagenVehiculo.objects.filter(pk=foto.pk).exists())

    def test_guardar_sin_tocar_fotos_no_lee_el_archivo(self):
        """Guardar los datos comerciales no re-procesa las fotos existentes."""
        from django.core.files.storage import default_storage
        from django.test import override_settings

        media = self._media_temporal()
        with override_settings(MEDIA_ROOT=media):
            foto = self._foto()
            nombre_original = foto.imagen.name
            default_storage.delete(nombre_original)

            self.client.force_login(self.admin)
            datos = {
                'estado': 'EN_VENTA', 'precio_venta': '11.900,00',
                'descripcion_dano': 'x',
                'imagenes-TOTAL_FORMS': '1', 'imagenes-INITIAL_FORMS': '1',
                'imagenes-MIN_NUM_FORMS': '0', 'imagenes-MAX_NUM_FORMS': '15',
                'imagenes-0-id': str(foto.pk),
                'imagenes-0-orden': '1',
            }
            respuesta = self.client.post(
                reverse('vehicles:publicar', args=[self.vehiculo.pk]), datos
            )
            self.assertEqual(respuesta.status_code, 302)

            foto.refresh_from_db()
            self.assertEqual(foto.imagen.name, nombre_original)


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
