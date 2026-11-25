import tempfile
from datetime import date
from decimal import Decimal
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


class VehiculoHojaTecnicaTests(TestCase):
    """Hoja 1: técnicos + compra + factura (sin precio ni fotos)."""

    def setUp(self):
        from datetime import date
        from decimal import Decimal

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
            'forma_pago': '',
        }
        datos.update(extra)
        return datos

    def _editar(self, **extra):
        return self.client.post(
            reverse('vehicles:update', args=[self.vehiculo.pk]),
            self._datos(**extra),
        )


    def _banco_con_deposito(self, fecha, importe='10000.00'):
        from apps.accounting.models import CuentaContable
        from apps.bank.models import BancoCuenta, BancoMovimiento

        banco = BancoCuenta.objects.create(
            nombre='Santander Vehiculos',
            iban='ES9121000418450200051777',
            cuenta_contable=CuentaContable.objects.get(codigo='572'),
        )
        BancoMovimiento.objects.create(
            banco_cuenta=banco, fecha=fecha, concepto='Deposito inicial',
            tipo='INGRESO', importe=Decimal(importe), conciliado=True,
        )
        return banco

    def test_no_se_puede_comprar_un_vehiculo_antes_del_deposito(self):
        """El banco no puede quedar en negativo: depósito 10/08, compra 01/07."""
        self._banco_con_deposito(fecha=date(2026, 8, 10), importe='10000.00')

        respuesta = self.client.post(reverse('vehicles:create'), self._datos(
            matricula='9999ZZZ', bastidor='WVWZZZ1KZAW999999',
            fecha_adquisicion='2026-07-01',
        ))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta, 'Saldo insuficiente en la cuenta bancaria en la fecha indicada'
        )
        self.assertFalse(Vehiculo.objects.filter(matricula='9999ZZZ').exists())

    def test_se_puede_comprar_si_el_deposito_es_anterior(self):
        self._banco_con_deposito(fecha=date(2026, 7, 1), importe='10000.00')

        respuesta = self.client.post(reverse('vehicles:create'), self._datos(
            matricula='9999ZZZ', bastidor='WVWZZZ1KZAW999999',
            fecha_adquisicion='2026-07-02',
        ))

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Vehiculo.objects.filter(matricula='9999ZZZ').exists())

    def test_el_formulario_muestra_importes_y_fecha(self):
        from apps.vehicles.forms import VehiculoForm

        form = VehiculoForm(instance=self.vehiculo)
        self.assertIn('value="7.500,00"', str(form['precio_subasta']))
        self.assertIn('value="2026-07-01"', str(form['fecha_adquisicion']))

    def test_la_hoja_tecnica_no_tiene_campos_comerciales(self):
        respuesta = self.client.get(
            reverse('vehicles:update', args=[self.vehiculo.pk])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'name="precio_subasta"')
        self.assertContains(respuesta, 'name="factura_compra_pdf"')
        self.assertNotContains(respuesta, 'name="precio_venta"')
        self.assertNotContains(respuesta, 'name="descripcion_dano"')
        self.assertNotContains(respuesta, 'name="imagen_principal"')
        self.assertNotContains(respuesta, 'imagenes-TOTAL_FORMS')

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
        from decimal import Decimal

        self._editar()
        self._editar()

        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.precio_subasta, Decimal('7500.00'))
        self.assertEqual(self.vehiculo.coste_inicial, Decimal('8150.00'))

    def test_parseo_de_importes_sin_ambiguedad(self):
        from decimal import Decimal

        from apps.vehicles.forms import parsear_importe

        self.assertEqual(parsear_importe('7500'), Decimal('7500'))
        self.assertEqual(parsear_importe('7500.00'), Decimal('7500.00'))
        self.assertEqual(parsear_importe('7.500'), Decimal('7500'))
        self.assertEqual(parsear_importe('7.500,00'), Decimal('7500.00'))
        self.assertEqual(parsear_importe('7.500,50'), Decimal('7500.50'))
        self.assertEqual(parsear_importe('1.234.567,89'), Decimal('1234567.89'))

    def test_editar_importe_regenera_el_asiento_con_contrapartida(self):
        from decimal import Decimal

        from apps.accounting.models import AsientoContable

        asiento_viejo = self.vehiculo.crear_asiento_contable()

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
        self.assertEqual(self.vehiculo.asiento_contable.estado, 'POSTEADO')
        self.assertNotEqual(self.vehiculo.asiento_contable_id, asiento_viejo.pk)

    def test_editar_siempre_regenera_el_asiento(self):
        asiento = self.vehiculo.crear_asiento_contable()

        respuesta = self._editar(kilometraje='150000')
        self.assertEqual(respuesta.status_code, 302)

        asiento.refresh_from_db()
        self.assertEqual(asiento.estado, 'ANULADO')
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.kilometraje, 150000)
        self.assertNotEqual(self.vehiculo.asiento_contable_id, asiento.pk)


class VehiculoHojaComercialTests(TestCase):
    """Hoja 2 (Publicar): estado, precio, descripción y galería."""

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
        self.vendedor = User.objects.create_user(
            username='vendedor1', email='v1@eurocar.local',
            password='vendedor123!', rol='VENDEDOR',
        )
        self.vehiculo = Vehiculo.objects.create(
            matricula='1234ABC', bastidor='WVWZZZ3CZWE123456',
            marca='Volkswagen', modelo='Golf', anio=2020,
            combustible='DIESEL', kilometraje=90000, tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='C', estado='ACONDICIONADO',
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
            'descripcion_dano': 'Buen estado, un solo dueño.',
            'imagenes-TOTAL_FORMS': '0',
            'imagenes-INITIAL_FORMS': '0',
            'imagenes-MIN_NUM_FORMS': '0',
            'imagenes-MAX_NUM_FORMS': '15',
        }
        datos.update(extra)
        return self.client.post(
            reverse('vehicles:publicar', args=[self.vehiculo.pk]), datos
        )

    def test_publicar_guarda_estado_precio_y_descripcion(self):
        from decimal import Decimal

        respuesta = self._publicar()
        self.assertEqual(respuesta.status_code, 302)

        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'EN_VENTA')
        self.assertEqual(self.vehiculo.precio_venta, Decimal('11900.00'))
        self.assertIn('un solo dueño', self.vehiculo.descripcion_dano)

    def test_publicar_no_toca_los_costes(self):
        from decimal import Decimal

        self._publicar()
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.precio_subasta, Decimal('7500.00'))
        self.assertEqual(self.vehiculo.coste_inicial, Decimal('8150.00'))

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

    def test_publicar_guarda_una_foto_adicional(self):
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

    def test_publicar_avisa_al_superar_el_maximo(self):
        respuesta = self._publicar(**{'imagenes-TOTAL_FORMS': '16'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'el máximo es 15')

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

    def test_cambiar_de_estado_conserva_las_fotos(self):
        self._foto()
        respuesta = self._publicar(estado='ACONDICIONADO')
        self.assertEqual(respuesta.status_code, 302)

        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'ACONDICIONADO')
        self.assertEqual(
            ImagenVehiculo.objects.filter(vehiculo=self.vehiculo).count(), 1
        )

    def test_eliminar_foto_cuyo_archivo_ya_no_existe(self):
        from django.core.files.storage import default_storage

        foto = self._foto()
        default_storage.delete(foto.imagen.name)

        respuesta = self._publicar(**{
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

        respuesta = self._publicar(**{
            'imagenes-TOTAL_FORMS': '1',
            'imagenes-INITIAL_FORMS': '1',
            'imagenes-0-id': str(foto.pk),
            'imagenes-0-orden': '1',
        })
        self.assertEqual(respuesta.status_code, 302)
        foto.refresh_from_db()
        self.assertEqual(foto.imagen.name, nombre_original)

    def test_publicar_fija_la_fecha_de_publicacion(self):
        """Al pasar a En Venta sin fecha, se registra el día de hoy."""
        from django.utils import timezone

        self.assertIsNone(self.vehiculo.fecha_publicacion)
        self._publicar()

        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.fecha_publicacion, timezone.localdate())
        self.assertEqual(self.vehiculo.dias_en_venta, 0)

    def test_la_fecha_de_publicacion_se_puede_corregir(self):
        from datetime import date

        self._publicar(fecha_publicacion='2026-07-15')
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.fecha_publicacion, date(2026, 7, 15))

    def test_publicar_no_pisa_una_fecha_ya_registrada(self):
        from datetime import date

        self.vehiculo.estado = 'EN_VENTA'
        self.vehiculo.fecha_publicacion = date(2026, 7, 1)
        self.vehiculo.save()

        self._publicar(precio_venta='12.500,00')
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.fecha_publicacion, date(2026, 7, 1))

    def test_la_ficha_muestra_la_fecha_y_el_boton_editar(self):
        from datetime import date

        self.vehiculo.fecha_publicacion = date(2026, 7, 1)
        self.vehiculo.save(update_fields=['fecha_publicacion'])

        respuesta = self.client.get(
            reverse('vehicles:detail', args=[self.vehiculo.pk])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '01/07/2026')
        self.assertContains(respuesta, 'Datos comerciales')
        self.assertContains(
            respuesta,
            reverse('vehicles:publicar', args=[self.vehiculo.pk]),
        )


    def test_el_comando_detecta_y_limpia_fotos_perdidas(self):
        from django.core.files.storage import default_storage
        from django.core.management import call_command

        foto = self._foto()
        default_storage.delete(foto.imagen.name)

        call_command('comprobar_imagenes_vehiculos', verbosity=0)
        self.assertTrue(ImagenVehiculo.objects.filter(pk=foto.pk).exists())

        call_command('comprobar_imagenes_vehiculos', '--borrar-huerfanas', verbosity=0)
        self.assertFalse(ImagenVehiculo.objects.filter(pk=foto.pk).exists())

    def test_la_hoja_comercial_no_tiene_campos_de_compra(self):
        respuesta = self.client.get(
            reverse('vehicles:publicar', args=[self.vehiculo.pk])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'name="precio_venta"')
        self.assertContains(respuesta, 'name="estado"')
        self.assertContains(respuesta, 'name="imagen_principal"')
        self.assertNotContains(respuesta, 'name="precio_subasta"')
        self.assertNotContains(respuesta, 'name="tasas_sala"')
        self.assertNotContains(respuesta, 'name="factura_compra_pdf"')


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


class CatalogoVendidosTests(TestCase):
    """El catálogo público muestra los vendidos 30 días con la etiqueta."""

    def setUp(self):
        from datetime import date
        from decimal import Decimal

        from apps.accounting.models import PlanContableDefault

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
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

    def _ids_catalogo(self):
        respuesta = self.client.get('/api/vehiculos/')
        self.assertEqual(respuesta.status_code, 200)
        return [v['id'] for v in respuesta.json()['vehiculos']]

    def test_en_venta_aparece_sin_etiqueta_de_vendido(self):
        respuesta = self.client.get('/api/vehiculos/')
        datos = {v['id']: v for v in respuesta.json()['vehiculos']}
        self.assertIn(self.vehiculo.pk, datos)
        self.assertFalse(datos[self.vehiculo.pk]['vendido'])

    def test_vendido_hoy_sigue_visible_con_etiqueta(self):
        self.vehiculo.estado = 'VENDIDO'
        self.vehiculo.save(update_fields=['estado'])

        self.vehiculo.refresh_from_db()
        self.assertIsNotNone(self.vehiculo.fecha_vendido)

        respuesta = self.client.get('/api/vehiculos/')
        datos = {v['id']: v for v in respuesta.json()['vehiculos']}
        self.assertIn(self.vehiculo.pk, datos)
        self.assertTrue(datos[self.vehiculo.pk]['vendido'])

    def test_vendido_hace_31_dias_ya_no_aparece(self):
        from datetime import timedelta

        from django.utils import timezone

        self.vehiculo.estado = 'VENDIDO'
        self.vehiculo.save(update_fields=['estado'])
        Vehiculo.objects.filter(pk=self.vehiculo.pk).update(
            fecha_vendido=timezone.localdate() - timedelta(days=31)
        )

        self.assertNotIn(self.vehiculo.pk, self._ids_catalogo())
        detalle = self.client.get(f'/api/vehiculos/{self.vehiculo.pk}/')
        self.assertEqual(detalle.status_code, 404)

    def test_el_detalle_de_un_vendido_reciente_responde_con_la_etiqueta(self):
        self.vehiculo.estado = 'VENDIDO'
        self.vehiculo.save(update_fields=['estado'])

        respuesta = self.client.get(f'/api/vehiculos/{self.vehiculo.pk}/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['vendido'])

    def test_volver_a_publicar_limpia_la_fecha_de_venta(self):
        from django.utils import timezone

        self.vehiculo.estado = 'VENDIDO'
        self.vehiculo.save(update_fields=['estado'])
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.fecha_vendido, timezone.localdate())

        self.vehiculo.estado = 'EN_VENTA'
        self.vehiculo.save(update_fields=['estado'])
        self.vehiculo.refresh_from_db()
        self.assertIsNone(self.vehiculo.fecha_vendido)


class BorradoVehiculoProtegidoTests(TestCase):
    """H5/H9: no se borra un vehículo con operaciones; mensaje claro."""

    def setUp(self):
        from datetime import date
        from decimal import Decimal

        from apps.accounting.models import PlanContableDefault

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.operario = User.objects.create_user(
            username='mecanico1', email='m@eurocar.local',
            password='mecanico123!', rol='OPERARIO',
        )
        self.client.force_login(self.admin)
        self.vehiculo = Vehiculo.objects.create(
            matricula='1234ABC', bastidor='WVWZZZ3CZWE123456',
            marca='Volkswagen', modelo='Golf', anio=2020,
            combustible='DIESEL', kilometraje=90000, tipo_dano='ACCIDENTAL',
            etiqueta_ambiental='C', estado='ADQUIRIDO',
            fecha_adquisicion=date(2026, 10, 1),
            precio_subasta=Decimal('1000.00'), tasas_sala=Decimal('0'),
            logistica_grua=Decimal('0'), created_by=self.admin,
        )

    def test_no_se_borra_un_vehiculo_con_ot(self):
        from apps.workshop.models import OrdenTrabajo

        OrdenTrabajo.objects.create(
            vehiculo=self.vehiculo, operario=self.operario,
            titulo='Reparación', descripcion='Prueba',
            estado='COMPLETADA', horas_reales=1, created_by=self.admin,
        )

        respuesta = self.client.post(
            reverse('vehicles:delete', args=[self.vehiculo.pk]),
            follow=True,
        )

        self.assertTrue(Vehiculo.objects.filter(pk=self.vehiculo.pk).exists())
        self.assertContains(respuesta, 'órdenes de trabajo')

    def test_no_se_borra_un_vehiculo_vendido(self):
        self.vehiculo.estado = 'VENDIDO'
        self.vehiculo.save(update_fields=['estado'])

        respuesta = self.client.post(
            reverse('vehicles:delete', args=[self.vehiculo.pk]),
            follow=True,
        )

        self.assertTrue(Vehiculo.objects.filter(pk=self.vehiculo.pk).exists())
        self.assertContains(respuesta, 'vendido')
