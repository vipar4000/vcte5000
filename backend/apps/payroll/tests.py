"""Personal sin acceso al ERP y nóminas proporcionales a la periodicidad.

Casos reales de Madrid:
  - Obreros, limpieza y auxiliares cobran y fichan, pero no entran al ERP.
  - Hay pagos mensuales, quincenales y semanales: el importe debe repartirse
    según la ficha del trabajador, sin hacerlo a mano.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounting.models import PlanContableDefault
from apps.attendance.models import ConfiguracionNomina, Marcaje
from apps.payroll.models import NominaEstructura
from apps.payroll.services import generar_nominas_del_periodo, importes_para_periodo


class FichaSinAccesoTests(TestCase):
    def setUp(self):
        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.client.force_login(self.admin)

    def _datos(self, **extra):
        datos = {
            'first_name': 'Manuel',
            'last_name': 'García',
            'rol': 'OPERARIO',
            'sin_acceso': 'on',
            'pin_kiosco': '4321',
            'is_active': 'on',
            'puede_eliminar': 'on',
            'salario_base_mensual': '1500',
            'porcentaje_ss_patronal': '31.50',
            'periodicidad_pago': 'QUINCENAL',
            'porcentaje_irpf': '6',
            'porcentaje_ss_obrera': '6.35',
        }
        datos.update(extra)
        return datos

    def test_alta_de_trabajador_sin_usuario_ni_contrasena(self):
        respuesta = self.client.post(reverse('usuarios:create'), self._datos())
        self.assertEqual(respuesta.status_code, 302)

        trabajador = User.objects.get(first_name='Manuel', last_name='García')
        self.assertTrue(trabajador.sin_acceso)
        self.assertFalse(trabajador.has_usable_password())
        self.assertTrue(trabajador.username)
        self.assertTrue(trabajador.email.endswith('@sin-acceso.local'))
        self.assertEqual(trabajador.pin_kiosco, '4321')
        self.assertEqual(trabajador.periodicidad_pago, 'QUINCENAL')

    def test_el_trabajador_sin_acceso_no_puede_entrar_al_erp(self):
        self.client.post(reverse('usuarios:create'), self._datos())
        trabajador = User.objects.get(first_name='Manuel')

        anonimo = self.client_class()
        respuesta = anonimo.post(reverse('accounts:login'), {
            'username': trabajador.username,
            'password': 'loquesea',
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('_auth_user_id', anonimo.session)

    def test_ficha_sin_nombre_da_error_claro(self):
        respuesta = self.client.post(
            reverse('usuarios:create'),
            self._datos(first_name='', last_name=''),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Indique al menos el nombre')

    def test_operario_sin_acceso_necesita_pin(self):
        respuesta = self.client.post(
            reverse('usuarios:create'), self._datos(pin_kiosco='')
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Para fichar en taller hace falta el PIN')

    def test_el_pin_no_se_puede_repetir(self):
        self.client.post(reverse('usuarios:create'), self._datos())
        respuesta = self.client.post(
            reverse('usuarios:create'),
            self._datos(first_name='Otro', last_name='Trabajador'),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ese PIN ya lo usa otro trabajador')

    def test_el_formulario_no_bloquea_el_envio_por_campos_ocultos(self):
        """Regresión: con la casilla marcada, el navegador bloqueaba el botón.

        Los campos de usuario/correo/contraseña conservaban el atributo `required`
        aunque estuvieran ocultos, y el formulario no se podía enviar.
        """
        respuesta = self.client.get(reverse('usuarios:create'))
        html = respuesta.content.decode()

        self.assertIn('novalidate', html)
        self.assertIn("removeAttribute('required')", html)

    def test_al_reintentar_el_alta_el_campo_usuario_no_es_obligatorio(self):
        import re

        respuesta = self.client.post(
            reverse('usuarios:create'), self._datos(pin_kiosco='')
        )
        html = respuesta.content.decode()

        campo = re.search(r'<input[^>]*id="id_username"[^>]*>', html)
        self.assertIsNotNone(campo)
        self.assertNotIn('required', campo.group(0))

        correo = re.search(r'<input[^>]*id="id_email"[^>]*>', html)
        self.assertNotIn('required', correo.group(0))

    def test_puede_fichar_en_el_kiosco_con_su_pin(self):
        self.client.post(reverse('usuarios:create'), self._datos())

        tablet = self.client_class()
        respuesta = tablet.post(reverse('attendance:kiosco'), {'pin': '4321'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Marcaje.objects.count(), 1)
        self.assertContains(respuesta, 'Manuel')


class NominaProporcionalTests(TestCase):
    def setUp(self):
        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.trabajador = User.objects.create_user(
            username='limpieza-1', email='limpieza@sin-acceso.local',
            password=None, rol='OPERARIO',
            first_name='María', last_name='López',
            sin_acceso=True,
            salario_base_mensual=Decimal('1500.00'),
            porcentaje_ss_patronal=Decimal('31.50'),
            porcentaje_irpf=Decimal('6.00'),
            porcentaje_ss_obrera=Decimal('6.35'),
            periodicidad_pago='QUINCENAL',
            pin_kiosco='1111',
        )
        self.trabajador.set_unusable_password()
        self.trabajador.save()
        self.client.force_login(self.admin)

    def test_importes_por_periodicidad(self):
        mensual = importes_para_periodo(self.trabajador, 'MENSUAL')
        self.assertEqual(mensual['salario_bruto'], Decimal('1500.00'))
        self.assertEqual(mensual['ss_obrera'], Decimal('95.25'))
        self.assertEqual(mensual['retencion_irpf'], Decimal('90.00'))

        quincenal = importes_para_periodo(self.trabajador, 'QUINCENAL')
        self.assertEqual(quincenal['salario_bruto'], Decimal('750.00'))
        self.assertEqual(quincenal['ss_obrera'], Decimal('47.62'))
        self.assertEqual(quincenal['retencion_irpf'], Decimal('45.00'))

        semanal = importes_para_periodo(self.trabajador, 'SEMANAL')
        self.assertEqual(semanal['salario_bruto'], Decimal('350.00'))
        self.assertEqual(semanal['liquido'], Decimal('306.78'))

    def test_nueva_nomina_calcula_sola_al_elegir_trabajador(self):
        respuesta = self.client.post(reverse('payroll:create'), {
            'empleado': self.trabajador.pk,
            'periodo': 'QUINCENAL',
            'fecha_nomina': '2026-11-20',
            'calcular_automaticamente': 'on',
        })
        self.assertEqual(respuesta.status_code, 302)

        nomina = NominaEstructura.objects.get()
        self.assertEqual(nomina.empleado, self.trabajador)
        self.assertEqual(nomina.periodo, 'QUINCENAL')
        self.assertEqual(nomina.salario_bruto, Decimal('750.00'))
        self.assertEqual(nomina.ss_obrera, Decimal('47.62'))
        self.assertEqual(nomina.retencion_irpf, Decimal('45.00'))
        self.assertEqual(nomina.liquido_percibir, Decimal('657.38'))
        self.assertTrue(nomina.asiento_contable.esta_cuadrado)

    def test_sin_calculo_automatico_hacen_falta_los_importes(self):
        respuesta = self.client.post(reverse('payroll:create'), {
            'empleado': self.trabajador.pk,
            'periodo': 'MENSUAL',
            'fecha_nomina': '2026-11-20',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Indique el salario bruto')

    def test_el_endpoint_devuelve_los_importes_del_periodo(self):
        url = reverse('payroll:importes', args=[self.trabajador.pk])
        respuesta = self.client.get(url, {'periodo': 'SEMANAL'})

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos['salario_bruto'], '350.00')
        self.assertEqual(datos['periodo'], 'SEMANAL')
        self.assertEqual(datos['nombre'], 'María López')

    def test_generador_usa_la_periodicidad_de_cada_ficha(self):
        semanal = User.objects.create_user(
            username='obrero-1', email='obrero@sin-acceso.local',
            password=None, rol='OPERARIO', first_name='Juan', last_name='Pérez',
            sin_acceso=True, salario_base_mensual=Decimal('1200.00'),
            porcentaje_ss_patronal=Decimal('31.50'),
            porcentaje_irpf=Decimal('6.00'), porcentaje_ss_obrera=Decimal('6.35'),
            periodicidad_pago='SEMANAL', pin_kiosco='2222',
        )
        semanal.set_unusable_password()
        semanal.save()

        resultado = generar_nominas_del_periodo(fecha=date(2026, 11, 20))
        self.assertEqual(resultado['status'], 'ok')
        self.assertEqual(resultado['generadas'], 2)

        quincena = NominaEstructura.objects.get(empleado=self.trabajador)
        self.assertEqual(quincena.periodo, 'QUINCENAL')
        self.assertEqual(quincena.salario_bruto, Decimal('750.00'))

        semana = NominaEstructura.objects.get(empleado=semanal)
        self.assertEqual(semana.periodo, 'SEMANAL')
        self.assertEqual(semana.salario_bruto, Decimal('280.00'))

    def test_el_generador_no_duplica_la_nomina_del_periodo(self):
        generar_nominas_del_periodo(fecha=date(2026, 11, 20))
        segundo = generar_nominas_del_periodo(fecha=date(2026, 11, 21))

        self.assertEqual(segundo['generadas'], 0)
        self.assertEqual(segundo['saltadas'], 1)
        self.assertEqual(NominaEstructura.objects.count(), 1)

    def test_la_configuracion_de_taller_guarda_en_la_ficha(self):
        ConfiguracionNomina.objects.filter(operario=self.trabajador).delete()

        respuesta = self.client.post(reverse('attendance:nomina_create'), {
            'operario': self.trabajador.pk,
            'salario_base_mensual': '1600',
            'porcentaje_ss_patronal': '32.00',
            'periodicidad_pago': 'SEMANAL',
            'porcentaje_irpf': '8.00',
            'porcentaje_ss_obrera': '6.40',
        })
        self.assertEqual(respuesta.status_code, 302)

        self.trabajador.refresh_from_db()
        self.assertEqual(self.trabajador.salario_base_mensual, Decimal('1600.00'))
        self.assertEqual(self.trabajador.periodicidad_pago, 'SEMANAL')
        self.assertEqual(self.trabajador.porcentaje_irpf, Decimal('8.00'))
        self.assertEqual(self.trabajador.porcentaje_ss_obrera, Decimal('6.40'))


class ReciboNominaTests(TestCase):
    """Recibo imprimible de la nómina (botón + hoja formal)."""

    def setUp(self):
        from datetime import date
        from decimal import Decimal

        from apps.accounting.models import PlanContableDefault

        PlanContableDefault.crear_plan_base()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.client.force_login(self.admin)
        self.trabajador = User.objects.create_user(
            username='mecanico1', email='mecanico1@eurocar.local',
            password='mecanico123!', rol='OPERARIO',
            first_name='Manuel', last_name='García',
            puesto_trabajo='Mecánico',
            salario_base_mensual=Decimal('1500.00'),
            porcentaje_ss_patronal=Decimal('31.50'),
            porcentaje_irpf=Decimal('6.00'),
            porcentaje_ss_obrera=Decimal('6.35'),
        )
        self.nomina = NominaEstructura.objects.create(
            empleado=self.trabajador,
            fecha_nomina=date(2026, 11, 30),
            periodo='MENSUAL',
            salario_bruto=Decimal('1500.00'),
            ss_patronal=Decimal('472.50'),
            retencion_irpf=Decimal('90.00'),
            ss_obrera=Decimal('95.25'),
            liquido_percibir=Decimal('1314.75'),
            created_by=self.admin,
        )

    def test_la_ficha_muestra_el_boton_de_imprimir(self):
        respuesta = self.client.get(
            reverse('payroll:detail', args=[self.nomina.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'btn-imprimir-recibo')
        self.assertContains(respuesta, 'Imprimir Recibo')
        self.assertContains(respuesta, 'js/recibo-nomina.js')
        self.assertContains(respuesta, 'css/recibo-nomina.css')

    def test_el_recibo_tiene_los_datos_formales(self):
        respuesta = self.client.get(
            reverse('payroll:detail', args=[self.nomina.pk])
        )
        html = respuesta.content.decode()

        self.assertIn('id="recibo-nomina"', html)
        self.assertIn('Recibo de Salario', html)
        # Empresa
        self.assertIn('R Car Rogil', html)
        self.assertIn('B26729731', html)
        # Trabajador, puesto y periodo
        self.assertIn('Manuel García', html)
        self.assertIn('Mecánico', html)
        self.assertIn('Mensual', html)
        self.assertIn('30/11/2026', html)
        # Devengos, deducciones y líquido
        self.assertIn('Total devengos (A)', html)
        self.assertIn('Total deducciones (B)', html)
        self.assertIn('1.314,75', html)
        # Firmas
        self.assertIn('Firma de la Empresa', html)
        self.assertIn('Recibí del Trabajador', html)

    def test_el_css_de_impresion_oculta_la_interfaz_y_muestra_el_recibo(self):
        from django.contrib.staticfiles import finders

        ruta_css = finders.find('css/recibo-nomina.css')
        self.assertIsNotNone(ruta_css)

        with open(ruta_css, encoding='utf-8') as archivo:
            css = archivo.read()

        self.assertIn('@media print', css)
        self.assertIn('#recibo-nomina', css)
        self.assertIn('visibility: hidden', css)
        self.assertIn('visibility: visible', css)

    def test_sin_puesto_configurado_se_muestra_el_rol(self):
        User.objects.filter(pk=self.trabajador.pk).update(puesto_trabajo='')

        respuesta = self.client.get(
            reverse('payroll:detail', args=[self.nomina.pk])
        )

        self.assertContains(respuesta, 'Operario de Taller')


class TotalDeduccionesTests(TestCase):
    """El total de deducciones es solo del trabajador (IRPF + SS obrera)."""

    def test_no_incluye_la_ss_patronal(self):
        from datetime import date
        from decimal import Decimal

        from apps.accounting.models import PlanContableDefault
        from apps.accounts.models import User
        from apps.payroll.models import NominaEstructura

        PlanContableDefault.crear_plan_base()
        admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        empleado = User.objects.create_user(
            username='mecanico1', email='m@eurocar.local',
            password='mecanico123!', rol='OPERARIO',
        )
        nomina = NominaEstructura.objects.create(
            empleado=empleado, fecha_nomina=date(2026, 11, 27),
            salario_bruto=Decimal('750.00'),
            ss_obrera=Decimal('47.62'),
            ss_patronal=Decimal('236.25'),
            retencion_irpf=Decimal('45.00'),
            created_by=admin,
        )

        self.assertEqual(nomina.total_deducciones, Decimal('92.62'))
        self.assertEqual(nomina.liquido_percibir, Decimal('657.38'))
