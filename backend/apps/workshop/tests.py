import unittest
from datetime import date
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.db import connections
from apps.accounts.models import User
from apps.vehicles.models import Vehiculo
from apps.accounting.models import PlanContableDefault, CuentaContable, AsientoContable
from apps.bank.models import BancoCuenta, BancoMovimiento
from apps.workshop.models import Material, CompraMaterial


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


    def test_los_dos_accesos_apuntan_a_la_misma_vista(self):
        """Taller y ficha del coche comparten vista y plantilla (sin duplicar)."""
        self.client.force_login(self.admin)
        url_formulario = reverse('workshop:create_ot')

        ficha = self.client.get(
            reverse('vehicles:detail', args=[self.vehiculo.pk])
        ).content.decode()
        self.assertIn(url_formulario, ficha)
        self.assertIn(f'{url_formulario}?vehiculo={self.vehiculo.pk}', ficha)

        listado = self.client.get(reverse('workshop:list')).content.decode()
        self.assertIn(url_formulario, listado)

        # Las dos entradas devuelven el mismo formulario
        desde_taller = self.client.get(url_formulario)
        desde_ficha = self.client.get(
            url_formulario, {'vehiculo': self.vehiculo.pk}
        )
        self.assertEqual(desde_taller.status_code, 200)
        self.assertEqual(desde_ficha.status_code, 200)
        self.assertIn('id="id_vehiculo"', desde_taller.content.decode())
        self.assertIn('id="id_vehiculo"', desde_ficha.content.decode())

    def test_el_vehiculo_llega_preseleccionado_desde_la_ficha(self):
        self.client.force_login(self.admin)

        html = self.client.get(
            reverse('workshop:create_ot'), {'vehiculo': self.vehiculo.pk}
        ).content.decode()

        self.assertIn(
            f'<option value="{self.vehiculo.pk}" selected>', html
        )

    def test_un_vehiculo_vendido_no_se_ofrece_ni_se_precarga(self):
        self.client.force_login(self.admin)
        self.vehiculo.estado = 'VENDIDO'
        self.vehiculo.save(update_fields=['estado'])

        respuesta = self.client.get(
            reverse('workshop:create_ot'), {'vehiculo': self.vehiculo.pk}
        )
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'está vendido')
        self.assertNotIn(f'<option value="{self.vehiculo.pk}" selected>', html)


    def test_crear_ot_no_despublica_un_vehiculo_en_venta(self):
        """Regla de negocio: solo se pasa a TALLER desde ADQUIRIDO.

        Un coche ya publicado (EN_VENTA) no debe desaparecer del catálogo por
        abrirle una orden de trabajo.
        """
        self.client.force_login(self.admin)
        self.vehiculo.estado = 'EN_VENTA'
        self.vehiculo.save(update_fields=['estado'])

        response = self.client.post(reverse('workshop:create_ot'), {
            'vehiculo': self.vehiculo.pk,
            'operario': self.operario.pk,
            'titulo': 'Repaso antes de entregar',
            'descripcion': 'Revisión',
            'horas_estimadas': 1,
            'horas_reales': 0,
            'estado': 'PENDIENTE',
        })

        self.assertEqual(response.status_code, 302)
        self.vehiculo.refresh_from_db()
        self.assertEqual(self.vehiculo.estado, 'EN_VENTA')

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


class OrdenTrabajoListaFiltroTests(TestCase):
    """El filtro de búsqueda del listado de OTs incluye título y descripción."""

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
            estado='TALLER',
            fecha_adquisicion='2026-07-01',
            precio_subasta=7500,
            tasas_sala=400,
            logistica_grua=250,
            created_by=self.admin,
        )
        from apps.workshop.models import OrdenTrabajo
        self.ot = OrdenTrabajo.objects.create(
            vehiculo=self.vehiculo,
            operario=self.operario,
            titulo='Diagnostico general y reparacion',
            descripcion='Revision general: cambio aceite, filtros, frenos',
            horas_estimadas=4,
            estado='PENDIENTE',
            created_by=self.admin,
        )

    def test_busqueda_por_descripcion(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('workshop:list'), {'busqueda': 'cambio aceite'}
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Diagnostico general y reparacion', html)

    def test_busqueda_sin_resultados_excluye_ot(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('workshop:list'), {'busqueda': 'texto inexistente'}
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('Diagnostico general y reparacion', html)


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

        # La mano de obra debe ir a 611 (Variación de existencias), no a 610
        codigos = [m.cuenta.codigo for m in movimientos]
        self.assertIn('611', codigos)
        self.assertNotIn('610', codigos)
        mov_611 = [m for m in movimientos if m.cuenta.codigo == '611'][0]
        self.assertEqual(mov_611.haber, ot.coste_mano_obra)

    def test_capitalizacion_ot_como_variacion_existencias(self):
        """La mano de obra capitalizada aparece como variación de existencias (611).

        Mientras el vehículo sigue en inventario, la mano de obra de la OT
        incrementa el activo (DEBE 310); el HABER a 611 debe formar parte del
        resultado del ejercicio o el Balance no cuadraría (el gasto de
        personal del operario no se asienta como tal en este sistema).
        """
        from apps.workshop.models import OrdenTrabajo
        from apps.accounting.reports import calcular_balance, calcular_pyg
        from apps.vehicles.models import Vehiculo

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
        ot.crear_asiento_contable()
        self.vehiculo.estado = 'ACONDICIONADO'
        self.vehiculo.save()

        balance = calcular_balance('2026-12-31')
        pyg = calcular_pyg('2026-01-01', '2026-12-31')

        self.assertEqual(
            balance['patrimonio_neto']['resultado_ejercicio'],
            ot.coste_mano_obra,
        )
        self.assertEqual(pyg['variacion_existencias'], ot.coste_mano_obra)
        self.assertEqual(pyg['resultado_neto'], ot.coste_mano_obra)
        self.assertEqual(balance['activo']['total'], balance['total_pasivo_patrimonio'])


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
            'fecha_vencimiento': '2026-08-15',
            'numero_factura': 'FC-AUTO-2026-001',
            'tipo_inventario': '300',
            'tipo_iva': '21.00',
            'lineas-TOTAL_FORMS': '2',
            'lineas-INITIAL_FORMS': '0',
            'lineas-MIN_NUM_FORMS': '0',
            'lineas-MAX_NUM_FORMS': '1000',
            'lineas-0-material': self.aceite.nombre,
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

    def _post_compra(self, forma_pago='', cantidad='20', precio='8.50',
                     tipo_iva='21.00', pagado='', fecha_pago='', cuenta_pago='',
                     fecha_compra='2026-07-01'):
        """POST de una compra de una línea (aceite) con la forma de pago dada."""
        self.client.force_login(self.admin)
        data = {
            'proveedor': 'Distribuciones Auto S.L.',
            'cif_nif': 'B12345678',
            'fecha_compra': fecha_compra,
            'fecha_vencimiento': '2026-08-15',
            'numero_factura': 'FC-AUTO-2026-001',
            'tipo_inventario': '300',
            'tipo_iva': tipo_iva,
            'forma_pago': forma_pago,
            'pagado': pagado,
            'fecha_pago': fecha_pago,
            'cuenta_pago': cuenta_pago,
            'lineas-TOTAL_FORMS': '1',
            'lineas-INITIAL_FORMS': '0',
            'lineas-MIN_NUM_FORMS': '0',
            'lineas-MAX_NUM_FORMS': '1000',
            'lineas-0-material': self.aceite.nombre,
            'lineas-0-cantidad': cantidad,
            'lineas-0-precio_unitario': precio,
            'lineas-0-DELETE': '',
        }
        return self.client.post(reverse('workshop:compra_material_create'), data)

    def _banco_con_saldo(self, saldo='1000.00', nombre='Santander Prueba'):
        """Crea la cuenta banco 572 con un INGRESO inicial (para poder pagar)."""
        cuenta_572 = CuentaContable.objects.get(codigo='572')
        banco = BancoCuenta.objects.create(
            nombre=nombre,
            iban='ES9121000418450200051332',
            cuenta_contable=cuenta_572,
        )
        BancoMovimiento.objects.create(
            banco_cuenta=banco,
            fecha='2026-06-30',
            concepto='Deposito inicial',
            tipo='INGRESO',
            importe=Decimal(saldo),
            conciliado=True,
        )
        return banco

    def _crear_compra_credito(self):
        """Crea una compra a crédito (aceite 20 x 8,50, IVA 21% → 205,70)."""
        self.client.force_login(self.admin)
        response = self._post_compra()
        self.assertEqual(response.status_code, 302)
        return CompraMaterial.objects.get(material=self.aceite)

    def _cuentas_haber(self, compra):
        return {
            m.cuenta.codigo: m.haber
            for m in compra.asiento_contable.movimientos.all()
        }

    def test_compra_credito_default_hace_410_sin_movimiento_banco(self):
        """Sin forma de pago: HABER 410 (crédito), sin movimiento bancario."""
        response = self._post_compra()
        self.assertEqual(response.status_code, 302)
        compra = CompraMaterial.objects.get(material=self.aceite)
        self.assertIsNone(compra.forma_pago)
        self.assertIsNotNone(compra.asiento_contable)
        self.assertEqual(compra.asiento_contable.estado, 'POSTEADO')
        cuentas = self._cuentas_haber(compra)
        self.assertEqual(cuentas.get('410'), Decimal('205.70'))
        self.assertNotIn('572', cuentas)
        self.assertNotIn('570', cuentas)
        self.assertEqual(BancoMovimiento.objects.count(), 0)

    def test_compra_contado_banco_genera_egreso(self):
        """Forma de pago 572: HABER 572 + EGRESO bancario vinculado al asiento."""
        cuenta_572 = CuentaContable.objects.get(codigo='572')
        banco = BancoCuenta.objects.create(
            nombre='Santander Prueba',
            iban='ES9121000418450200051332',
            cuenta_contable=cuenta_572,
        )
        BancoMovimiento.objects.create(
            banco_cuenta=banco,
            fecha='2026-06-30',
            concepto='Deposito inicial',
            tipo='INGRESO',
            importe=Decimal('1000.00'),
            conciliado=True,
        )

        response = self._post_compra(forma_pago='572')
        self.assertEqual(response.status_code, 302)
        compra = CompraMaterial.objects.get(material=self.aceite)
        self.assertEqual(compra.forma_pago.codigo, '572')
        cuentas = self._cuentas_haber(compra)
        self.assertEqual(cuentas.get('572'), Decimal('205.70'))
        self.assertNotIn('410', cuentas)

        egreso = BancoMovimiento.objects.get(tipo='EGRESO')
        self.assertEqual(egreso.importe, Decimal('205.70'))
        self.assertEqual(egreso.asiento_asociado, compra.asiento_contable)
        self.assertEqual(egreso.banco_cuenta, banco)

    def test_compra_contado_caja_sin_movimiento_banco(self):
        """Forma de pago 570: HABER 570 (caja), sin movimiento bancario."""
        response = self._post_compra(forma_pago='570')
        self.assertEqual(response.status_code, 302)
        compra = CompraMaterial.objects.get(material=self.aceite)
        self.assertEqual(compra.forma_pago.codigo, '570')
        cuentas = self._cuentas_haber(compra)
        self.assertEqual(cuentas.get('570'), Decimal('205.70'))
        self.assertNotIn('410', cuentas)
        self.assertNotIn('572', cuentas)
        self.assertEqual(BancoMovimiento.objects.count(), 0)

    def test_compra_contado_banco_sin_saldo_no_se_guarda(self):
        """Saldo insuficiente: la factura entera se rechaza (sin stock ni asiento)."""
        cuenta_572 = CuentaContable.objects.get(codigo='572')
        BancoCuenta.objects.create(
            nombre='Santander Vacio',
            iban='ES9121000418450200051444',
            cuenta_contable=cuenta_572,
        )

        response = self._post_compra(forma_pago='572')
        self.assertEqual(response.status_code, 200)
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.stock_actual, 0)
        self.assertEqual(CompraMaterial.objects.count(), 0)
        self.assertEqual(BancoMovimiento.objects.filter(tipo='EGRESO').count(), 0)


    def test_compra_por_banco_con_fecha_anterior_al_deposito_se_bloquea(self):
        """Caso Madrid: el dinero entra el 10/08 y la compra es del 01/07.

        El saldo de hoy cubre el pago, pero a la fecha de la compra la cuenta
        estaba a cero: el sistema debe bloquearlo y avisar en rojo.
        """
        cuenta_572 = CuentaContable.objects.get(codigo='572')
        banco = BancoCuenta.objects.create(
            nombre='Santander Deposito Tardio',
            iban='ES9121000418450200051555',
            cuenta_contable=cuenta_572,
        )
        BancoMovimiento.objects.create(
            banco_cuenta=banco,
            fecha='2026-08-10',
            concepto='Deposito inicial',
            tipo='INGRESO',
            importe=Decimal('1000.00'),
            conciliado=True,
        )

        response = self._post_compra(forma_pago='572', fecha_compra='2026-07-01')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Saldo insuficiente en la cuenta bancaria en la fecha indicada')
        self.assertContains(response, 'Registre primero el ingreso/depósito')
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.stock_actual, 0)
        self.assertEqual(CompraMaterial.objects.count(), 0)
        self.assertEqual(BancoMovimiento.objects.filter(tipo='EGRESO').count(), 0)

    def test_compra_por_banco_despues_del_deposito_se_permite(self):
        cuenta_572 = CuentaContable.objects.get(codigo='572')
        banco = BancoCuenta.objects.create(
            nombre='Santander Con Fondos',
            iban='ES9121000418450200051666',
            cuenta_contable=cuenta_572,
        )
        BancoMovimiento.objects.create(
            banco_cuenta=banco,
            fecha='2026-08-10',
            concepto='Deposito inicial',
            tipo='INGRESO',
            importe=Decimal('1000.00'),
            conciliado=True,
        )

        response = self._post_compra(forma_pago='572', fecha_compra='2026-08-11')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(CompraMaterial.objects.count(), 1)
        self.assertEqual(BancoMovimiento.objects.filter(tipo='EGRESO').count(), 1)

    def test_compra_credito_pagada_al_crear_genera_asiento_pago_y_egreso(self):
        """Checkbox 'Pagar ahora' al crear a crédito: asiento PagoCompraMaterial + EGRESO."""
        banco = self._banco_con_saldo()

        response = self._post_compra(pagado='on', fecha_pago='2026-07-31', cuenta_pago='572')
        self.assertEqual(response.status_code, 302)
        compra = CompraMaterial.objects.get(material=self.aceite)
        self.assertTrue(compra.pagado)
        self.assertEqual(compra.fecha_pago.strftime('%Y-%m-%d'), '2026-07-31')
        self.assertEqual(compra.cuenta_pago.codigo, '572')

        pago = AsientoContable.objects.get(
            tipo_documento='PagoCompraMaterial', documento_id=compra.pk
        )
        self.assertEqual(pago.estado, 'POSTEADO')
        self.assertTrue(pago.esta_cuadrado)
        cuentas = {
            m.cuenta.codigo: (m.debe, m.haber)
            for m in pago.movimientos.all()
        }
        self.assertEqual(cuentas['410'][0], Decimal('205.70'))
        self.assertEqual(cuentas['572'][1], Decimal('205.70'))

        egreso = BancoMovimiento.objects.get(tipo='EGRESO')
        self.assertEqual(egreso.importe, Decimal('205.70'))
        self.assertEqual(egreso.asiento_asociado, pago)
        self.assertEqual(egreso.banco_cuenta, banco)

    def test_compra_credito_pagada_al_crear_sin_saldo_no_se_guarda(self):
        """'Pagar ahora' sin saldo en banco: la factura entera se rechaza."""
        cuenta_572 = CuentaContable.objects.get(codigo='572')
        BancoCuenta.objects.create(
            nombre='Santander Vacio',
            iban='ES9121000418450200051444',
            cuenta_contable=cuenta_572,
        )

        response = self._post_compra(pagado='on', cuenta_pago='572')
        self.assertEqual(response.status_code, 200)
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.stock_actual, 0)
        self.assertEqual(CompraMaterial.objects.count(), 0)

    def test_pagar_compra_posterior_genera_asiento_y_egreso(self):
        """Acción 'Marcar pagado' sobre una compra a crédito ya registrada."""
        compra = self._crear_compra_credito()
        banco = self._banco_con_saldo()
        self.assertFalse(compra.pagado)

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('workshop:compra_pagar', args=[compra.pk]),
            {'fecha_pago': '2026-07-31', 'cuenta_pago': '572'},
        )
        self.assertEqual(response.status_code, 302)
        compra.refresh_from_db()
        self.assertTrue(compra.pagado)

        pago = AsientoContable.objects.get(
            tipo_documento='PagoCompraMaterial', documento_id=compra.pk
        )
        self.assertEqual(pago.estado, 'POSTEADO')
        self.assertEqual(pago.fecha.strftime('%Y-%m-%d'), '2026-07-31')
        egreso = BancoMovimiento.objects.get(tipo='EGRESO')
        self.assertEqual(egreso.importe, Decimal('205.70'))
        self.assertEqual(egreso.banco_cuenta, banco)

    def test_crear_asiento_pago_es_idempotente(self):
        """Pagar dos veces no duplica el asiento de pago."""
        compra = self._crear_compra_credito()
        self._banco_con_saldo()
        compra.pagado = True
        compra.fecha_pago = date(2026, 7, 31)
        compra.save(update_fields=['pagado', 'fecha_pago'])

        primero = compra.crear_asiento_pago()
        segundo = compra.crear_asiento_pago()
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(
            AsientoContable.objects.filter(
                tipo_documento='PagoCompraMaterial', documento_id=compra.pk
            ).count(),
            1,
        )
        self.assertEqual(BancoMovimiento.objects.filter(tipo='EGRESO').count(), 1)

    def test_pago_por_caja_no_genera_movimiento_banco(self):
        """Pagar con cuenta_pago 570: asiento HABER 570, sin movimiento bancario."""
        compra = self._crear_compra_credito()

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('workshop:compra_pagar', args=[compra.pk]),
            {'fecha_pago': '2026-07-31', 'cuenta_pago': '570'},
        )
        self.assertEqual(response.status_code, 302)
        compra.refresh_from_db()
        self.assertTrue(compra.pagado)
        self.assertEqual(compra.cuenta_pago.codigo, '570')

        pago = AsientoContable.objects.get(
            tipo_documento='PagoCompraMaterial', documento_id=compra.pk
        )
        cuentas = {m.cuenta.codigo: m.haber for m in pago.movimientos.all()}
        self.assertEqual(cuentas.get('570'), Decimal('205.70'))
        self.assertNotIn('572', cuentas)
        self.assertEqual(BancoMovimiento.objects.count(), 0)

    def test_deshacer_pago_anula_y_elimina_egreso(self):
        """'Deshacer pago': asiento anulado + contrapartida + EGRESO eliminado."""
        compra = self._crear_compra_credito()
        self._banco_con_saldo()

        self.client.force_login(self.admin)
        self.client.post(
            reverse('workshop:compra_pagar', args=[compra.pk]),
            {'fecha_pago': '2026-07-31', 'cuenta_pago': '572'},
        )
        self.assertEqual(BancoMovimiento.objects.filter(tipo='EGRESO').count(), 1)

        response = self.client.post(
            reverse('workshop:compra_deshacer_pago', args=[compra.pk])
        )
        self.assertEqual(response.status_code, 302)
        compra.refresh_from_db()
        self.assertFalse(compra.pagado)
        self.assertIsNone(compra.fecha_pago)
        self.assertIsNone(compra.cuenta_pago)

        pago = AsientoContable.objects.get(
            tipo_documento='PagoCompraMaterial', documento_id=compra.pk
        )
        self.assertEqual(pago.estado, 'ANULADO')
        reverso = AsientoContable.objects.get(
            tipo_documento='AnulacionPagoCompra', documento_id=compra.pk
        )
        self.assertTrue(reverso.esta_cuadrado)
        self.assertEqual(BancoMovimiento.objects.filter(tipo='EGRESO').count(), 0)

    def test_crear_asiento_pago_en_contado_lanza_error(self):
        """Una compra al contado no admite asiento de pago (ya pagó al crear)."""
        self._banco_con_saldo()
        response = self._post_compra(forma_pago='572')
        self.assertEqual(response.status_code, 302)
        compra = CompraMaterial.objects.get(material=self.aceite)
        self.assertFalse(compra.es_credito)

        with self.assertRaises(ValueError):
            compra.crear_asiento_pago()

    def test_checkbox_pagado_ignorado_en_contado(self):
        """Checkbox 'Pagar ahora' con forma de pago contado: no genera pago duplicado."""
        self._banco_con_saldo()
        response = self._post_compra(forma_pago='572', pagado='on',
                                     fecha_pago='2026-07-31', cuenta_pago='572')
        self.assertEqual(response.status_code, 302)
        compra = CompraMaterial.objects.get(material=self.aceite)
        self.assertFalse(compra.pagado)
        self.assertFalse(
            AsientoContable.objects.filter(
                tipo_documento='PagoCompraMaterial', documento_id=compra.pk
            ).exists()
        )
        # Solo el EGRESO del contado, no un segundo por el checkbox.
        self.assertEqual(BancoMovimiento.objects.filter(tipo='EGRESO').count(), 1)

    # ------------------------------------------ alta de material en 1 paso
    def _datos_linea(self, material, unidad='', cantidad='4', precio='9.75'):
        return {
            'proveedor': 'Recambios Nuevos S.L.',
            'cif_nif': 'B99887766',
            'fecha_compra': '2026-07-01',
            'fecha_vencimiento': '2026-08-15',
            'numero_factura': 'FC-NUEVO-1',
            'tipo_inventario': '300',
            'tipo_iva': '21.00',
            'lineas-TOTAL_FORMS': '1',
            'lineas-INITIAL_FORMS': '0',
            'lineas-MIN_NUM_FORMS': '0',
            'lineas-MAX_NUM_FORMS': '1000',
            'lineas-0-material': material,
            'lineas-0-unidad': unidad,
            'lineas-0-cantidad': cantidad,
            'lineas-0-precio_unitario': precio,
            'lineas-0-DELETE': '',
        }

    def test_material_nuevo_se_crea_al_registrar_la_compra(self):
        """Un nombre desconocido crea el material en la misma pantalla."""
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse('workshop:compra_material_create'),
            self._datos_linea('Filtro de habitáculo', unidad='unidades'),
        )
        self.assertEqual(respuesta.status_code, 302)

        material = Material.objects.get(nombre='Filtro de habitáculo')
        self.assertEqual(material.unidad, 'unidades')
        self.assertEqual(material.stock_actual, 4)
        # El precio de referencia del catálogo se toma de la propia compra
        self.assertEqual(material.precio_unitario, Decimal('9.75'))

    def test_material_nuevo_sin_unidad_no_se_crea(self):
        """Si el material no existe y no se indica unidad, se rechaza la línea."""
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse('workshop:compra_material_create'),
            self._datos_linea('Material sin unidad', unidad=''),
        )
        self.assertEqual(respuesta.status_code, 200)  # vuelve al formulario
        self.assertFalse(Material.objects.filter(nombre='Material sin unidad').exists())

    def test_material_existente_por_nombre_no_duplica(self):
        """El mismo material escrito con otras mayúsculas suma stock, no duplica."""
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse('workshop:compra_material_create'),
            self._datos_linea('aceite MOTOR 5w30', cantidad='5', precio='8.50'),
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            Material.objects.filter(nombre__iexact='Aceite motor 5W30').count(), 1
        )
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.stock_actual, 5)

    def test_inventario_ya_no_ofrece_dar_de_alta(self):
        """Inventario es consulta: sin botones de alta ni de compra."""
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('workshop:material_list'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'Registrar Compra')
        self.assertNotContains(respuesta, 'Nuevo Material')
        self.assertContains(respuesta, 'se crea solo')


class MaterialCreateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@eurocar.local',
            password='admin123!',
            rol='ADMIN',
        )
        self.client.force_login(self.admin)
        self.url = reverse('workshop:material_create')
        self.data = {
            'nombre': 'Filtro de aceite',
            'descripcion': 'Filtro estándar',
            'unidad': 'unidades',
            'stock_actual': '10',
            'stock_minimo': '2',
            'precio_unitario': '12.50',
        }

    def test_crear_material_y_anadir_otro(self):
        """'Crear y añadir otro' vuelve al formulario vacío permitiendo crear varios."""
        response = self.client.post(self.url, {**self.data, 'guardar_otro': '1'})
        self.assertRedirects(response, self.url)
        self.assertTrue(Material.objects.filter(nombre='Filtro de aceite').exists())

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="Filtro de aceite"')

        response = self.client.post(self.url, {**self.data, 'nombre': 'Bujía'})
        self.assertEqual(Material.objects.count(), 2)
        bujia = Material.objects.get(nombre='Bujía')
        self.assertRedirects(response, reverse('workshop:material_detail', args=[bujia.pk]))

class CompraFacturaFlujoTest(TestCase):
    """Historial, hoja resumen, «guardar y otra» y corrección de una factura."""

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
            stock_minimo=0,
            precio_unitario=Decimal('8.50'),
        )
        self.client.force_login(self.admin)

    def _datos(self, **extra):
        datos = {
            'proveedor': 'Distribuciones Auto S.L.',
            'cif_nif': 'C12345678',
            'fecha_compra': '2026-07-02',
            'fecha_vencimiento': '2026-12-31',
            'numero_factura': 'CM-001',
            'tipo_inventario': '300',
            'tipo_iva': '21.00',
            'forma_pago': '',
            'lineas-TOTAL_FORMS': '1',
            'lineas-INITIAL_FORMS': '0',
            'lineas-MIN_NUM_FORMS': '0',
            'lineas-MAX_NUM_FORMS': '1000',
            'lineas-0-material': 'Aceite motor 5W30',
            'lineas-0-unidad': 'litros',
            'lineas-0-cantidad': '20',
            'lineas-0-precio_unitario': '8.50',
            'lineas-0-DELETE': '',
        }
        datos.update(extra)
        return datos

    def _banco_con_saldo(self, saldo='1000.00'):
        banco = BancoCuenta.objects.create(
            nombre='Santander Prueba',
            iban='ES9121000418450200051332',
            cuenta_contable=CuentaContable.objects.get(codigo='572'),
        )
        BancoMovimiento.objects.create(
            banco_cuenta=banco,
            tipo='INGRESO',
            importe=Decimal(saldo),
            concepto='Aportación inicial',
            fecha=date(2026, 7, 1),
        )
        return banco

    # ------------------------------------------------- guardar y otra
    def test_guardar_y_otra_vuelve_al_formulario(self):
        respuesta = self.client.post(
            reverse('workshop:compra_material_create'),
            self._datos(guardar_y_otra='1'),
        )
        self.assertRedirects(respuesta, reverse('workshop:compra_material_create'))
        self.assertEqual(CompraMaterial.objects.count(), 1)

    # ------------------------------------------------- hoja resumen
    def test_tras_guardar_se_abre_el_resumen(self):
        respuesta = self.client.post(
            reverse('workshop:compra_material_create'), self._datos()
        )
        compra = CompraMaterial.objects.get()
        self.assertRedirects(
            respuesta,
            reverse('workshop:compra_detail', args=[compra.factura_grupo]),
        )

        detalle = self.client.get(respuesta.url)
        self.assertEqual(detalle.status_code, 200)
        self.assertContains(detalle, 'CM-001')
        self.assertContains(detalle, 'Aceite motor 5W30')
        self.assertContains(detalle, compra.asiento_contable.numero)

    def test_historial_agrupa_por_factura(self):
        self.client.post(reverse('workshop:compra_material_create'), self._datos())

        historial = self.client.get(reverse('workshop:compra_list'))
        self.assertEqual(historial.status_code, 200)
        self.assertContains(historial, 'CM-001')
        self.assertContains(historial, 'Distribuciones Auto S.L.')

    # ------------------------------------------------- corrección
    def test_editar_forma_de_pago_anula_y_crea_el_contado(self):
        self._banco_con_saldo()
        self.client.post(reverse('workshop:compra_material_create'), self._datos())
        compra = CompraMaterial.objects.get()
        asiento_viejo = compra.asiento_contable

        respuesta = self.client.post(
            reverse('workshop:compra_edit', args=[compra.factura_grupo]),
            self._datos(forma_pago='572'),
        )
        self.assertEqual(respuesta.status_code, 302)

        asiento_viejo.refresh_from_db()
        self.assertEqual(asiento_viejo.estado, 'ANULADO')
        self.assertTrue(
            AsientoContable.objects.filter(
                tipo_documento='AnulacionCompraMaterial'
            ).exists()
        )

        nueva = CompraMaterial.objects.get()
        self.assertEqual(nueva.forma_pago.codigo, '572')
        self.assertEqual(nueva.asiento_contable.estado, 'POSTEADO')
        cuentas = nueva.asiento_contable.movimientos.values_list(
            'cuenta__codigo', flat=True
        )
        self.assertIn('572', cuentas)
        self.assertEqual(BancoMovimiento.objects.filter(tipo='EGRESO').count(), 1)

        # La cantidad no cambió: el stock sigue igual
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.stock_actual, 20)

    def test_editar_cantidad_ajusta_el_stock(self):
        self.client.post(reverse('workshop:compra_material_create'), self._datos())
        compra = CompraMaterial.objects.get()

        respuesta = self.client.post(
            reverse('workshop:compra_edit', args=[compra.factura_grupo]),
            self._datos(**{'lineas-0-cantidad': '30'}),
        )
        self.assertEqual(respuesta.status_code, 302)

        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.stock_actual, Decimal('30'))
        self.assertEqual(CompraMaterial.objects.get().cantidad, Decimal('30'))

    # ------------------------------------------- fecha de vencimiento
    def test_compra_a_credito_exige_fecha_de_vencimiento(self):
        datos = self._datos()
        datos.pop('fecha_vencimiento')
        respuesta = self.client.post(
            reverse('workshop:compra_material_create'), datos
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(CompraMaterial.objects.count(), 0)
        self.assertContains(respuesta, 'Indique la fecha de vencimiento')

    def test_vencimiento_anterior_a_la_compra_es_error(self):
        respuesta = self.client.post(
            reverse('workshop:compra_material_create'),
            self._datos(**{'fecha_vencimiento': '2026-06-01'}),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(CompraMaterial.objects.count(), 0)
        self.assertContains(respuesta, 'no puede ser anterior')

    def test_historial_y_resumen_marcan_la_factura_vencida(self):
        from datetime import timedelta

        compra_fecha = date.today() - timedelta(days=40)
        vencimiento = date.today() - timedelta(days=5)
        self.client.post(
            reverse('workshop:compra_material_create'),
            self._datos(**{
                'fecha_compra': compra_fecha.isoformat(),
                'fecha_vencimiento': vencimiento.isoformat(),
            }),
        )
        compra = CompraMaterial.objects.get()
        self.assertEqual(compra.fecha_vencimiento, vencimiento)

        historial = self.client.get(reverse('workshop:compra_list'))
        self.assertContains(historial, 'Vencida')

        resumen = self.client.get(
            reverse('workshop:compra_detail', args=[compra.factura_grupo])
        )
        self.assertContains(resumen, 'Factura vencida')

    # --------------------------------- PDF perdido tras un despliegue
    def test_editar_con_el_pdf_perdido_no_falla(self):
        import shutil
        import tempfile

        from django.core.files.storage import default_storage
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings

        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)

        with override_settings(MEDIA_ROOT=media):
            datos = self._datos()
            datos['documento_pdf'] = SimpleUploadedFile(
                'factura_cm003.pdf', b'%PDF-1.4\n',
                content_type='application/pdf',
            )
            self.client.post(reverse('workshop:compra_material_create'), datos)

            compra = CompraMaterial.objects.get()
            self.assertTrue(compra.documento_pdf)
            nombre = compra.documento_pdf.name

            # El servidor perdió el archivo (disco efímero de Render)
            default_storage.delete(nombre)
            self.assertFalse(default_storage.exists(nombre))

            # El resumen avisa en vez de ofrecer un enlace roto
            resumen = self.client.get(
                reverse('workshop:compra_detail', args=[compra.factura_grupo])
            )
            self.assertContains(resumen, 'PDF no disponible')

            # Y la corrección se guarda igual, sin adjunto
            respuesta = self.client.post(
                reverse('workshop:compra_edit', args=[compra.factura_grupo]),
                self._datos(),
            )
            self.assertEqual(respuesta.status_code, 302)
            self.assertEqual(CompraMaterial.objects.count(), 1)
            self.assertFalse(CompraMaterial.objects.get().documento_pdf)

    # ------------------- PDF nuevo al corregir (incluye mismo nombre)
    def _media_temporal(self):
        import shutil
        import tempfile

        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        return media

    def _crear_con_pdf(self, nombre='05_CM-003.pdf'):
        from django.core.files.uploadedfile import SimpleUploadedFile

        datos = self._datos()
        datos['documento_pdf'] = SimpleUploadedFile(
            nombre, b'%PDF-1.4 viejo\n', content_type='application/pdf'
        )
        self.client.post(reverse('workshop:compra_material_create'), datos)
        return CompraMaterial.objects.get()

    def test_editar_con_pdf_nuevo_lo_guarda(self):
        """Al subir un PDF nuevo en la corrección, se guarda ese archivo."""
        from django.core.files.storage import default_storage
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings

        media = self._media_temporal()
        with override_settings(MEDIA_ROOT=media):
            compra = self._crear_con_pdf('viejo.pdf')
            default_storage.delete(compra.documento_pdf.name)

            datos = self._datos()
            datos['documento_pdf'] = SimpleUploadedFile(
                'nuevo.pdf', b'%PDF-1.4 nuevo\n', content_type='application/pdf'
            )
            respuesta = self.client.post(
                reverse('workshop:compra_edit', args=[compra.factura_grupo]),
                datos, follow=True,
            )

            nueva = CompraMaterial.objects.get()
            self.assertIn('nuevo', nueva.documento_pdf.name)
            self.assertTrue(default_storage.exists(nueva.documento_pdf.name))
            self.assertNotContains(respuesta, 'PDF no disponible')
            # No debe avisar de PDF perdido: se subió uno nuevo
            self.assertNotContains(respuesta, 'ya no estaba en el servidor')

    def test_editar_reutilizando_el_mismo_nombre_de_pdf(self):
        """Regresión: django-cleanup no debe borrar el PDF recién subido.

        Antes, al reutilizar el nombre del archivo antiguo, la limpieza
        diferida de la línea borrada eliminaba también el PDF nuevo y la
        factura quedaba con «PDF no disponible».
        """
        from django.core.files.storage import default_storage
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings

        media = self._media_temporal()
        with override_settings(MEDIA_ROOT=media):
            compra = self._crear_con_pdf('05_CM-003.pdf')
            default_storage.delete(compra.documento_pdf.name)

            datos = self._datos()
            datos['documento_pdf'] = SimpleUploadedFile(
                '05_CM-003.pdf', b'%PDF-1.4 nuevo\n',
                content_type='application/pdf',
            )
            respuesta = self.client.post(
                reverse('workshop:compra_edit', args=[compra.factura_grupo]),
                datos, follow=True,
            )

            nueva = CompraMaterial.objects.get()
            self.assertTrue(nueva.documento_pdf)
            self.assertTrue(
                default_storage.exists(nueva.documento_pdf.name),
                'El PDF recién subido no debe borrarse con la limpieza del antiguo',
            )
            self.assertIn('corregida', nueva.documento_pdf.name)
            self.assertNotContains(respuesta, 'PDF no disponible')
