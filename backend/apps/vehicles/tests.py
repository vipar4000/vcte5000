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

    # ------------------------------------------------------------------
    # Optimización, carpetas por matrícula y conservación de las fotos
    # ------------------------------------------------------------------

    def _datos_sin_imagenes(self, **extra):
        datos = dict(self.datos, **extra)
        datos.update({
            'imagenes-TOTAL_FORMS': '0',
            'imagenes-INITIAL_FORMS': '0',
            'imagenes-MIN_NUM_FORMS': '0',
            'imagenes-MAX_NUM_FORMS': '1000',
        })
        return datos

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_imagen_principal_se_reduce_y_va_a_la_carpeta_de_la_matricula(self):
        from apps.accounting.models import PlanContableDefault
        PlanContableDefault.crear_plan_base()
        self.client.force_login(self.admin)
        datos = self._datos_sin_imagenes(estado='EN_VENTA', precio_venta='11900')
        datos['imagen_principal'] = SimpleUploadedFile(
            'foto-movil.png', _png_bytes_grande(3000, 2000), content_type='image/png'
        )
        response = self.client.post(
            reverse('vehicles:update', kwargs={'pk': self.vehiculo.pk}), datos
        )
        self.assertEqual(response.status_code, 302)
        self.vehiculo.refresh_from_db()

        nombre = self.vehiculo.imagen_principal.name
        self.assertTrue(
            nombre.startswith('vehiculos/1234abc/portada-'),
            f'Ruta inesperada: {nombre}',
        )
        self.assertTrue(nombre.endswith('.jpg'), nombre)
        with Image.open(self.vehiculo.imagen_principal.path) as img:
            self.assertEqual(img.format, 'JPEG')
            self.assertLessEqual(max(img.size), 2560)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_imagen_adicional_va_a_la_carpeta_de_la_matricula(self):
        from apps.accounting.models import PlanContableDefault
        PlanContableDefault.crear_plan_base()
        self.client.force_login(self.admin)
        datos = self._datos_sin_imagenes(estado='EN_VENTA', precio_venta='11900')
        datos.update({
            'imagenes-TOTAL_FORMS': '1',
            'imagenes-0-imagen': SimpleUploadedFile(
                'lateral.png', _png_bytes_grande(1200, 900), content_type='image/png'
            ),
            'imagenes-0-orden': '1',
            'imagenes-0-id': '',
        })
        response = self.client.post(
            reverse('vehicles:update', kwargs={'pk': self.vehiculo.pk}), datos
        )
        self.assertEqual(response.status_code, 302)
        extra = ImagenVehiculo.objects.get(vehiculo=self.vehiculo)
        self.assertTrue(
            extra.imagen.name.startswith('vehiculos/1234abc/lateral-'),
            extra.imagen.name,
        )

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_formset_avisa_al_superar_el_maximo_de_imagenes(self):
        self.client.force_login(self.admin)
        datos = self._datos_sin_imagenes(estado='EN_VENTA', precio_venta='11900')
        datos['imagenes-TOTAL_FORMS'] = '16'
        for i in range(16):
            datos[f'imagenes-{i}-imagen'] = ''
            datos[f'imagenes-{i}-orden'] = str(i + 1)
            datos[f'imagenes-{i}-id'] = ''

        response = self.client.post(
            reverse('vehicles:update', kwargs={'pk': self.vehiculo.pk}), datos
        )
        # No se guarda nada y el usuario ve el motivo, en lugar de perder fotos
        # en silencio porque el formset recorta en max_num.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'el máximo es 15')
        self.assertFalse(ImagenVehiculo.objects.filter(vehiculo=self.vehiculo).exists())

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_cambiar_de_estado_conserva_las_fotos(self):
        from apps.accounting.models import PlanContableDefault
        PlanContableDefault.crear_plan_base()
        self.client.force_login(self.admin)
        self.vehiculo.estado = 'EN_VENTA'
        self.vehiculo.precio_venta = 11900
        self.vehiculo.save()
        self.vehiculo.imagen_principal = SimpleUploadedFile(
            'foto.png', _png_bytes(), content_type='image/png'
        )
        self.vehiculo.save()
        self.assertTrue(self.vehiculo.imagen_principal)

        datos = self._datos_sin_imagenes(estado='VENDIDO', precio_venta='11900')
        response = self.client.post(
            reverse('vehicles:update', kwargs={'pk': self.vehiculo.pk}), datos
        )
        self.assertEqual(response.status_code, 302)
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'VENDIDO')
        self.assertTrue(
            self.vehiculo.imagen_principal,
            'Las fotos deben conservarse al salir de EN_VENTA',
        )


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
            'forma_pago': '', 'precio_venta': '11.900,00',
            'descripcion_dano': '',
        }
        datos.update(extra)
        return datos

    def test_el_formulario_muestra_importes_y_fecha_correctos(self):
        from apps.vehicles.forms import VehiculoForm

        form = VehiculoForm(instance=self.vehiculo)
        self.assertIn('value="7.500,00"', str(form['precio_subasta']))
        self.assertIn('value="11.900,00"', str(form['precio_venta']))
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

    def test_campos_financieros_bloqueados_con_asiento_posteado(self):
        from decimal import Decimal

        from apps.vehicles.forms import VehiculoForm

        asiento = self.vehiculo.crear_asiento_contable()
        asiento.estado = 'POSTEADO'
        asiento.save(update_fields=['estado'])

        form = VehiculoForm(instance=self.vehiculo)
        self.assertIn('precio_subasta', form.campos_bloqueados)
        self.assertIn('tasas_sala', form.campos_bloqueados)
        self.assertTrue(form.fields['precio_subasta'].disabled)

        # Aunque lleguen otros importes, el campo deshabilitado conserva el suyo
        form_post = VehiculoForm(
            self._datos_tecnicos(precio_subasta='99.999,00'), instance=self.vehiculo
        )
        self.assertTrue(form_post.is_valid(), form_post.errors)
        self.assertEqual(form_post.cleaned_data['precio_subasta'], Decimal('7500.00'))

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
