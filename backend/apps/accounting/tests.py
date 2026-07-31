from datetime import date
from decimal import Decimal

from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from apps.accounting.models import (
    CuentaContable, AsientoContable, MovimientoContable, PlanContableDefault,
)
from apps.accounting import reports
from apps.workshop.models import Material


User = get_user_model()


class BaseReportesTestCase(TestCase):
    """Seed compartido: plan contable, materiales y asientos posteados."""

    @classmethod
    def setUpTestData(cls):
        PlanContableDefault.crear_plan_base()
        cls.user = User.objects.create_user(
            username='testadmin',
            password='testpass123!',
            rol='ADMIN',
        )

        cls.material_aceite = Material.objects.create(
            nombre='Aceite motor', unidad='litros', stock_actual=50, stock_minimo=20,
            precio_unitario=Decimal('4.00'),
        )
        cls.material_filtro = Material.objects.create(
            nombre='Filtro de aceite', unidad='unidades', stock_actual=10, stock_minimo=5,
            precio_unitario=Decimal('15.00'),
        )
        Material.objects.create(
            nombre='Pastillas de freno', unidad='unidades', stock_actual=0, stock_minimo=2,
            precio_unitario=Decimal('100.00'),
        )

        cls.crear_asiento('1', date(2026, 1, 15), 'Venta coche 2026', [
            ('430', Decimal('12100.00'), Decimal('0')),
            ('700', Decimal('0'), Decimal('10000.00')),
            ('471', Decimal('0'), Decimal('2100.00')),
        ])
        cls.crear_asiento('2', date(2026, 2, 10), 'Compra coche 2026', [
            ('600', Decimal('6000.00'), Decimal('0')),
            ('472', Decimal('1260.00'), Decimal('0')),
            ('400', Decimal('0'), Decimal('7260.00')),
        ])
        cls.crear_asiento('3', date(2026, 3, 5), 'Nomina marzo 2026', [
            ('640', Decimal('2000.00'), Decimal('0')),
            ('570', Decimal('0'), Decimal('2000.00')),
        ])
        cls.crear_asiento('4', date(2026, 3, 20), 'Cierre trimestre 2026', [
            ('621', Decimal('1000.00'), Decimal('0')),
            ('630', Decimal('500.00'), Decimal('0')),
            ('680', Decimal('300.00'), Decimal('0')),
            ('570', Decimal('0'), Decimal('1800.00')),
        ])
        cls.crear_asiento('5', date(2026, 4, 1), 'Borrador no posteado', [
            ('430', Decimal('100.00'), Decimal('0')),
            ('700', Decimal('0'), Decimal('100.00')),
        ], estado='BORRADOR')
        cls.crear_asiento('6', date(2026, 5, 1), 'Entrada inventario 2026', [
            ('310', Decimal('3000.00'), Decimal('0')),
            ('570', Decimal('0'), Decimal('3000.00')),
        ])
        cls.crear_asiento('7', date(2025, 12, 1), 'Venta coche 2025', [
            ('430', Decimal('6050.00'), Decimal('0')),
            ('700', Decimal('0'), Decimal('5000.00')),
            ('471', Decimal('0'), Decimal('1050.00')),
        ])
        cls.crear_asiento('8', date(2026, 6, 1), 'Compra materias primas', [
            ('320', Decimal('500.00'), Decimal('0')),
            ('400', Decimal('0'), Decimal('500.00')),
        ])

    @classmethod
    def crear_asiento(cls, numero, fecha, concepto, lineas, estado='POSTEADO'):
        asiento = AsientoContable.objects.create(
            numero=numero,
            fecha=fecha,
            concepto=concepto,
            estado=estado,
            created_by=cls.user,
        )
        for codigo, debe, haber in lineas:
            MovimientoContable.objects.create(
                asiento=asiento,
                cuenta=CuentaContable.objects.get(codigo=codigo),
                debe=debe,
                haber=haber,
            )
        return asiento


class DiarioTests(BaseReportesTestCase):

    def test_orden_cronologico_y_contaje(self):
        diario = reports.obtener_asientos_diario(date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(diario['n_asientos'], 6)
        self.assertEqual([a['numero'] for a in diario['asientos']], ['1', '2', '3', '4', '6', '8'])

    def test_solo_asientos_posteados(self):
        diario = reports.obtener_asientos_diario(date(2026, 1, 1), date(2026, 12, 31))
        numeros = [a['numero'] for a in diario['asientos']]
        self.assertNotIn('5', numeros)

    def test_asientos_cuadrados(self):
        diario = reports.obtener_asientos_diario(date(2026, 1, 1), date(2026, 12, 31))
        for a in diario['asientos']:
            self.assertEqual(a['total_debe'], a['total_haber'])

    def test_totales_generales(self):
        diario = reports.obtener_asientos_diario(date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(diario['total_debe'], Decimal('26660.00'))
        self.assertEqual(diario['total_haber'], Decimal('26660.00'))

    def test_filtro_por_fechas(self):
        diario = reports.obtener_asientos_diario(date(2026, 1, 1), date(2026, 2, 28))
        self.assertEqual([a['numero'] for a in diario['asientos']], ['1', '2'])

    def test_excluye_ejercicio_anterior(self):
        diario = reports.obtener_asientos_diario(date(2027, 1, 1), date(2027, 12, 31))
        self.assertEqual(diario['n_asientos'], 0)


class MayorTests(BaseReportesTestCase):

    def test_saldo_corrido(self):
        resultado = reports.obtener_movimientos_cuenta('570', date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual([m['saldo'] for m in resultado['movimientos']],
                         [Decimal('-2000'), Decimal('-3800'), Decimal('-6800')])
        self.assertEqual(resultado['total_debe'], Decimal('0'))
        self.assertEqual(resultado['total_haber'], Decimal('6800'))
        self.assertEqual(resultado['saldo_final'], Decimal('-6800'))

    def test_filtro_por_fechas(self):
        resultado = reports.obtener_movimientos_cuenta('570', date(2026, 3, 1), date(2026, 3, 31))
        self.assertEqual(len(resultado['movimientos']), 2)
        self.assertEqual(resultado['saldo_final'], Decimal('-3800'))

    def test_cuenta_inexistente(self):
        self.assertIsNone(reports.obtener_movimientos_cuenta('999', date(2026, 1, 1), date(2026, 12, 31)))

    def test_excluye_borradores(self):
        resultado = reports.obtener_movimientos_cuenta('430', date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(len(resultado['movimientos']), 1)
        self.assertEqual(resultado['total_debe'], Decimal('12100'))
        self.assertEqual(resultado['saldo_final'], Decimal('12100'))

    def test_cuenta_de_ingresos_saldo_negativo(self):
        resultado = reports.obtener_movimientos_cuenta('700', date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(resultado['saldo_final'], Decimal('-10000'))


class ExistenciasTests(BaseReportesTestCase):

    def test_valoracion_materiales(self):
        data = reports.obtener_valor_existencias()
        self.assertEqual(data['total_valor'], Decimal('350'))
        items = {i['nombre']: i for i in data['materiales']}
        self.assertEqual(items['Aceite motor']['valor'], Decimal('200'))
        self.assertEqual(items['Filtro de aceite']['valor'], Decimal('150'))
        self.assertEqual(items['Pastillas de freno']['valor'], Decimal('0'))

    def test_saldo_contable_por_cuentas_300_330(self):
        data = reports.obtener_valor_existencias()
        self.assertEqual(data['saldo_contable'], Decimal('3500'))

    def test_diferencia(self):
        data = reports.obtener_valor_existencias()
        self.assertEqual(data['diferencia'], Decimal('-3150'))

    def test_items_contienen_campos(self):
        data = reports.obtener_valor_existencias()
        for item in data['materiales']:
            self.assertIn('nombre', item)
            self.assertIn('unidad', item)
            self.assertIn('stock', item)
            self.assertIn('precio', item)
            self.assertIn('valor', item)


class BalanceTests(BaseReportesTestCase):

    def test_cuadre_activo_pasivo_patrimonio(self):
        balance = reports.calcular_balance(date(2026, 12, 31))
        self.assertEqual(balance['activo']['total'], balance['total_pasivo_patrimonio'])

    def test_activo(self):
        balance = reports.calcular_balance(date(2026, 12, 31))
        self.assertEqual(balance['activo']['no_corriente']['inmovilizado'], Decimal('0'))
        self.assertEqual(balance['activo']['corriente']['existencias'], Decimal('3500'))
        self.assertEqual(balance['activo']['corriente']['clientes'], Decimal('18150'))
        self.assertEqual(balance['activo']['corriente']['tesoreria'], Decimal('-6800'))
        self.assertEqual(balance['activo']['total'], Decimal('14850'))

    def test_pasivo(self):
        balance = reports.calcular_balance(date(2026, 12, 31))
        self.assertEqual(balance['pasivo']['corriente']['proveedores'], Decimal('7760'))
        self.assertEqual(balance['pasivo']['corriente']['iva_repercutido'], Decimal('3150'))
        self.assertEqual(balance['pasivo']['corriente']['iva_soportado'], Decimal('1260'))
        self.assertEqual(balance['pasivo']['corriente']['total'], Decimal('9650'))

    def test_patrimonio_neto(self):
        balance = reports.calcular_balance(date(2026, 12, 31))
        self.assertEqual(balance['patrimonio_neto']['resultado_ejercicio'], Decimal('5200'))
        self.assertEqual(balance['patrimonio_neto']['total'], Decimal('5200'))

    def test_fecha_de_corte_excluye_anio_siguiente(self):
        balance = reports.calcular_balance(date(2025, 12, 31))
        self.assertEqual(balance['activo']['total'], Decimal('6050'))
        self.assertEqual(balance['activo']['total'], balance['total_pasivo_patrimonio'])


class PyGTests(BaseReportesTestCase):

    def test_cascada_resultados(self):
        pyg = reports.calcular_pyg(date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(pyg['ingresos']['ventas'], Decimal('10000'))
        self.assertEqual(pyg['coste_ventas']['compras'], Decimal('6000'))
        self.assertEqual(pyg['resultado_bruto'], Decimal('4000'))
        self.assertEqual(pyg['gastos_operativos']['gastos_personal_total'], Decimal('2000'))
        self.assertEqual(pyg['gastos_operativos']['arrendamientos'], Decimal('1000'))
        self.assertEqual(pyg['ebitda'], Decimal('1000'))
        self.assertEqual(pyg['gastos_financieros'], Decimal('500'))
        self.assertEqual(pyg['resultado_antes_impuestos'], Decimal('500'))
        self.assertEqual(pyg['impuesto_sociedades'], Decimal('300'))
        self.assertEqual(pyg['resultado_neto'], Decimal('200'))

    def test_margenes(self):
        pyg = reports.calcular_pyg(date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(float(pyg['margen_bruto_pct']), 40.0)
        self.assertEqual(float(pyg['margen_ebitda_pct']), 10.0)
        self.assertEqual(float(pyg['margen_neto_pct']), 2.0)

    def test_anio_sin_movimientos(self):
        pyg = reports.calcular_pyg(date(2024, 1, 1), date(2024, 12, 31))
        self.assertEqual(pyg['ingresos']['ventas'], Decimal('0'))
        self.assertEqual(pyg['resultado_neto'], Decimal('0'))
        self.assertEqual(pyg['margen_neto_pct'], Decimal('0'))


class IvaTests(BaseReportesTestCase):

    def test_primer_trimestre_2026(self):
        libro = reports.calcular_libro_iva(date(2026, 1, 1), date(2026, 3, 31))
        self.assertEqual(libro['iva_repercutido']['total'], Decimal('2100'))
        self.assertEqual(libro['iva_soportado']['total'], Decimal('1260'))
        self.assertEqual(libro['iva_repercutido']['base_imponible'], Decimal('10000'))
        self.assertEqual(libro['iva_soportado']['base_imponible'], Decimal('6000'))
        self.assertEqual(libro['cuota_liquidar'], Decimal('840'))
        self.assertFalse(libro['a_favor_cliente'])

    def test_cuarto_trimestre_2025(self):
        libro = reports.calcular_libro_iva(date(2025, 10, 1), date(2025, 12, 31))
        self.assertEqual(libro['iva_repercutido']['total'], Decimal('1050'))
        self.assertEqual(libro['iva_soportado']['total'], Decimal('0'))
        self.assertEqual(libro['cuota_liquidar'], Decimal('1050'))

    def test_trimestre_sin_movimientos(self):
        libro = reports.calcular_libro_iva(date(2026, 4, 1), date(2026, 6, 30))
        self.assertEqual(libro['cuota_liquidar'], Decimal('0'))
        self.assertFalse(libro['a_favor_cliente'])


class ComparativaTests(BaseReportesTestCase):

    def test_variacion_ventas(self):
        comparativa = reports.calcular_comparativa(2026, 2025)
        self.assertEqual(float(comparativa['ventas']['variacion']), 100.0)

    def test_variacion_negativa(self):
        comparativa = reports.calcular_comparativa(2026, 2025)
        self.assertEqual(float(comparativa['resultado_bruto']['variacion']), -20.0)
        self.assertEqual(float(comparativa['ebitda']['variacion']), -80.0)
        self.assertEqual(float(comparativa['resultado_neto']['variacion']), -96.0)

    def test_coste_ventas_sin_anterior(self):
        comparativa = reports.calcular_comparativa(2026, 2025)
        self.assertEqual(float(comparativa['coste_ventas']['variacion']), 100.0)

    def test_estructura(self):
        comparativa = reports.calcular_comparativa(2026, 2025)
        self.assertEqual(comparativa['anio_actual'], 2026)
        self.assertEqual(comparativa['anio_anterior'], 2025)


class ReportViewsTests(BaseReportesTestCase):

    def setUp(self):
        self.client.force_login(self.user)

    def test_login_requerido(self):
        anon = Client()
        resp = anon.get('/erp/contabilidad/informes/')
        self.assertEqual(resp.status_code, 302)

    def test_informes_list_9_tarjetas(self):
        resp = self.client.get('/erp/contabilidad/informes/')
        self.assertEqual(resp.status_code, 200)
        for titulo in [
            'Pérdidas y Ganancias',
            'Balance de Situación',
            'Libro IVA / Modelo 303',
            'Comparativa Año a Año',
            'Facturas de Compra',
            'Libro Diario',
            'Libro Mayor',
            'Valoración Existencias',
            'Tareas Programadas',
        ]:
            self.assertContains(resp, titulo)

    def test_pyg_view(self):
        resp = self.client.get('/erp/contabilidad/informes/pyg/', {'anio': 2026})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['pyg']['resultado_neto'], Decimal('200'))

    def test_balance_view_con_desglose(self):
        resp = self.client.get('/erp/contabilidad/informes/balance/', {'fecha': '2026-12-31'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['balance']['activo']['total'], Decimal('14850'))
        cuentas = resp.context['cuentas_balance']
        existencias = list(cuentas['existencias'])
        self.assertEqual([c['cuenta__codigo'] for c in existencias], ['310', '320'])
        self.assertEqual(sum(c['saldo'] for c in existencias), Decimal('3500'))
        clientes = list(cuentas['clientes'])
        self.assertEqual(clientes[0]['cuenta__codigo'], '430')
        self.assertEqual(clientes[0]['saldo'], Decimal('18150'))
        self.assertEqual(list(cuentas['activo_no_corriente']), [])

    def test_iva_view(self):
        resp = self.client.get('/erp/contabilidad/informes/iva/', {'anio': 2026, 'trimestre': 1})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['libro_iva']['cuota_liquidar'], Decimal('840'))

    def test_comparativa_view(self):
        resp = self.client.get('/erp/contabilidad/informes/comparativa/', {'anio_actual': 2026})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(float(resp.context['comparativa']['ventas']['variacion']), 100.0)

    def test_libro_diario_view(self):
        resp = self.client.get(
            '/erp/contabilidad/informes/libro-diario/',
            {'desde': '2026-01-01', 'hasta': '2026-12-31'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['diario']['n_asientos'], 6)

    def test_libro_mayor_view(self):
        resp = self.client.get(
            '/erp/contabilidad/informes/libro-mayor/',
            {'cuenta': '570', 'desde': '2026-01-01', 'hasta': '2026-12-31'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['saldo_final'], Decimal('-6800'))
        self.assertContains(resp, 'Caja')

    def test_libro_mayor_cuenta_inexistente(self):
        resp = self.client.get(
            '/erp/contabilidad/informes/libro-mayor/',
            {'cuenta': '999', 'desde': '2026-01-01', 'hasta': '2026-12-31'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['error'], 'Cuenta 999 no encontrada')

    def test_existencias_view(self):
        resp = self.client.get('/erp/contabilidad/informes/existencias/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['data']['total_valor'], Decimal('350'))

    def test_facturas_compra_view(self):
        resp = self.client.get('/erp/contabilidad/informes/facturas-compras/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['n_facturas'], 0)
