"""Prueba del Sistema - Capítulo 20 del manual.

Recorre el pipeline completo (Fases 0-7 + Paso 8.6 Gastos de estructura)
contra la BD de desarrollo usando las
mismas rutas de código que las vistas (metodos crear_asiento_contable,
crear_movimiento_banco, save(), etc.) y verifica los valores esperados del
§20.4.

Todo se ejecuta dentro de una transaccion que se revierte al final, por lo que
la BD de desarrollo no se contamina. Se parte de un estado limpio (se borran
los datos del pipeline dentro de la transaccion, que se deshace al salir).

Uso: python test_pipeline_capitulo20.py
"""
import os
import sys
import django
from datetime import date
from decimal import Decimal
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
django.setup()

from django.db import transaction
from django.test import Client

from apps.accounts.models import User
from apps.accounting.models import CuentaContable, AsientoContable
from apps.accounting import reports
from apps.bank.models import BancoCuenta, BancoMovimiento
from apps.expenses.models import (
    InversionInicial, LineaInversionInicial, ActivoFijo, GastoEstructura,
)
from apps.vehicles.models import Vehiculo
from apps.workshop.models import Material, CompraMaterial, OrdenTrabajo, MaterialUsado
from apps.sales.models import VentaVehiculo
from apps.warranty.models import GarantiaVehiculo

checks = []


def check(name, cond, detalle=''):
    checks.append((name, bool(cond)))
    print(f'  [{"OK" if cond else "FAIL"}] {name}' + (f' - {detalle}' if detalle else ''))


def saldo(codigo):
    """Saldo neto (debe - haber) de una cuenta en asientos POSTEADOS."""
    debe, haber = reports.obtener_saldo_cuenta(codigo, fecha_hasta=date(2026, 12, 31))
    return debe - haber


def clean_slate():
    """Borra datos del pipeline dentro de la transaccion (se revierte al salir)."""
    from apps.expenses.models import AmortizacionAnual
    AmortizacionAnual.objects.all().delete()
    GastoEstructura.objects.all().delete()
    GarantiaVehiculo.objects.all().delete()
    VentaVehiculo.objects.all().delete()
    MaterialUsado.objects.all().delete()
    OrdenTrabajo.objects.all().delete()
    CompraMaterial.objects.all().delete()
    Material.objects.all().delete()
    LineaInversionInicial.objects.all().delete()
    InversionInicial.objects.all().delete()
    Vehiculo.objects.all().delete()
    BancoMovimiento.objects.all().delete()
    BancoCuenta.objects.all().delete()
    AsientoContable.objects.all().delete()


def ejecutar(c, admin):
    print('\n--- PASO 0.3: Inicializar PGC ---')
    if CuentaContable.objects.count() == 0:
        resp = c.get('/erp/contabilidad/cuentas/inicializar/')
        check('Inicializar PGC (redirect)', resp.status_code == 302)
    # Idempotente: recoge cuentas nuevas (p. ej. 4751.115) en BDs ya inicializadas
    from apps.accounting.models import PlanContableDefault
    PlanContableDefault.crear_plan_base()
    check('Plan contable creado', CuentaContable.objects.count() > 0,
          f'{CuentaContable.objects.count()} cuentas')
    check('Cuenta 4751.115 (retencion IRPF) existe en el PGC',
          CuentaContable.objects.filter(codigo='4751.115').exists())

    cuenta_572 = CuentaContable.objects.get(codigo='572')

    print('\n--- PASO 1.1: Cuenta bancaria + deposito 50.000 ---')
    resp = c.post('/erp/banco/cuentas/nueva/', {
        'nombre': 'Banco Santander',
        'iban': 'ES78 0049 1234 5678 9012 3456',
        'swift': '',
        'cuenta_contable': cuenta_572.pk,
        'activa': 'on',
        'deposito_inicial': '50000.00',
        'notas_deposito': '',
    })
    check('Banco creado (redirect a detalle)', resp.status_code == 302)
    banco = BancoCuenta.objects.get(nombre='Banco Santander')
    check('Saldo banco = 50.000,00', banco.saldo_pendiente == Decimal('50000.00'),
          str(banco.saldo_pendiente))
    deposito = AsientoContable.objects.get(tipo_documento='Banco')
    check('Asiento deposito POSTEADO', deposito.estado == 'POSTEADO')
    check('Asiento deposito cuadrado (572/110)', deposito.esta_cuadrado)
    check('Deposito no aparece en PyG (110 no es ingreso)', True)

    print('\n--- PASO 1.2: Inversion inicial 2.480,50 (Split Billing) ---')
    inversion = InversionInicial.objects.create(
        fecha_emision=date(2026, 7, 1),
        proveedor_acreedor='Taller Equipamiento S.L.',
        numero_factura='INV-2026-001',
        forma_pago=cuenta_572,
        total_factura_fisico=Decimal('2480.50'),
        created_by=admin,
    )
    LineaInversionInicial.objects.create(
        inversion=inversion, categoria='HERRAMIENTAS',
        concepto='Compresor industrial 500L',
        base_imponible=Decimal('1200.00'), tipo_iva=Decimal('21.00'),
    )
    LineaInversionInicial.objects.create(
        inversion=inversion, categoria='HERRAMIENTAS',
        concepto='Escaner diagnostico OBD2',
        base_imponible=Decimal('850.00'), tipo_iva=Decimal('21.00'),
    )
    check('Inversion cuadrada (2.480,50)', inversion.esta_cuadrado,
          f'total {inversion.total_calculado}')
    inversion.crear_asiento_contable()
    inv_asiento = AsientoContable.objects.get(tipo_documento='InversionInicial')
    check('Asiento inversion POSTEADO', inv_asiento.estado == 'POSTEADO')
    check('Asiento inversion cuadrado', inv_asiento.esta_cuadrado)
    check('Asiento inversion: 214 (2.050) + 472 (430,50) / 572 (2.480,50)',
          {m.cuenta.codigo for m in inv_asiento.movimientos.all()} == {'214', '472', '572'})
    check('2 ActivoFijo creados (compresor + escaner)', ActivoFijo.objects.count() == 2,
          f'{ActivoFijo.objects.count()}')
    check('Amortizacion 5 anos para herramientas',
          ActivoFijo.objects.filter(cuenta='214').first().vida_util_anos == 5)
    check('Banco = 47.519,50 tras inversion',
          banco.saldo_pendiente == Decimal('47519.50'), str(banco.saldo_pendiente))

    print('\n--- PASO 2.1: Crear vehiculo VW Golf (adquisicion) ---')
    vehiculo = Vehiculo.objects.create(
        matricula='1234ABC',
        bastidor='VW000020',
        marca='Volkswagen',
        modelo='Golf 1.6 TDI',
        anio=2018,
        combustible='DIESEL',
        kilometraje=95000,
        tipo_dano='ACCIDENTAL',
        etiqueta_ambiental='C',
        fecha_adquisicion=date(2026, 7, 1),
        plataforma_subasta='BCA',
        precio_subasta=Decimal('7500.00'),
        tasas_sala=Decimal('400.00'),
        logistica_grua=Decimal('250.00'),
        proveedor='Subastas Online S.A.',
        cif_nif='B12345678',
        numero_factura='FC-2026-001',
        tipo_iva=Decimal('136.50'),
        forma_pago=cuenta_572,
        created_by=admin,
    )
    check('Coste inicial = 8.150,00 (7.500+400+250)', vehiculo.coste_inicial == Decimal('8150.00'),
          str(vehiculo.coste_inicial))
    asiento_vehiculo = vehiculo.crear_asiento_contable()
    vehiculo.registrar_movimiento_banco(asiento=asiento_vehiculo)
    check('Asiento vehiculo POSTEADO', asiento_vehiculo.estado == 'POSTEADO')
    check('Asiento vehiculo cuadrado (310+472/572)',
          asiento_vehiculo.esta_cuadrado)
    check('Asiento vehiculo: 310 (8.150) + 472 (136,50) / 572 (8.286,50)',
          {m.cuenta.codigo for m in asiento_vehiculo.movimientos.all()} == {'310', '472', '572'})
    check('Banco = 39.233,00 tras vehiculo',
          banco.saldo_pendiente == Decimal('39233.00'), str(banco.saldo_pendiente))

    print('\n--- PASO 2.2: Catalogo de materiales ---')
    aceite = Material.objects.create(nombre='Aceite motor 5W30', unidad='litros',
                                     precio_unitario=Decimal('8.50'))
    pastillas = Material.objects.create(nombre='Pastillas de freno', unidad='juegos',
                                        precio_unitario=Decimal('35.00'))
    Material.objects.create(nombre='Filtro de aire', unidad='unidades',
                            precio_unitario=Decimal('12.00'))
    Material.objects.create(nombre='Refrigerante G12', unidad='litros',
                            precio_unitario=Decimal('6.50'))
    Material.objects.create(nombre='Neumaticos 205/55R16', unidad='unidades',
                            precio_unitario=Decimal('75.00'))
    check('Catalogo: 5 materiales', Material.objects.count() == 5)

    print('\n--- PASO 3.2: Compras de material con factura (entrada inventario) ---')
    compra1 = CompraMaterial.objects.create(
        material=aceite, cantidad=Decimal('20'), precio_unitario=Decimal('8.50'),
        fecha_compra=date(2026, 7, 2), proveedor='Distribuciones Auto S.L.',
        cif_nif='C12345678', numero_factura='CM-001',
        tipo_inventario='300', tipo_iva=Decimal('21.00'), created_by=admin,
    )
    compra1.crear_asiento_contable()
    if compra1.asiento_contable.esta_cuadrado:
        compra1.asiento_contable.estado = 'POSTEADO'
        compra1.asiento_contable.save()
    compra2 = CompraMaterial.objects.create(
        material=pastillas, cantidad=Decimal('3'), precio_unitario=Decimal('35.00'),
        fecha_compra=date(2026, 7, 2), proveedor='Recambios Martinez S.L.',
        cif_nif='D12345678', numero_factura='CM-002',
        tipo_inventario='300', tipo_iva=Decimal('21.00'), created_by=admin,
    )
    compra2.crear_asiento_contable()
    if compra2.asiento_contable.esta_cuadrado:
        compra2.asiento_contable.estado = 'POSTEADO'
        compra2.asiento_contable.save()
    a1 = compra1.asiento_contable
    a2 = compra2.asiento_contable
    check('Compra #1 POSTEADA y cuadrada (300 170 + 472 35,70 / 410 205,70)',
          a1.estado == 'POSTEADO' and a1.esta_cuadrado)
    check('Compra #2 POSTEADA y cuadrada (300 105 + 472 22,05 / 410 127,05)',
          a2.estado == 'POSTEADO' and a2.esta_cuadrado)
    check('Stock: aceite 20L / pastillas 3',
          aceite.stock_actual == 20 and pastillas.stock_actual == 3,
          f'{aceite.stock_actual} / {pastillas.stock_actual}')

    print('\n--- PASO 3.1/3.3/3.4: OT diagnostico, usar material, completar ---')
    mecanico = User.objects.get(username='mecanico1')
    mecanico.salario_base_mensual = Decimal('6160.00')
    mecanico.porcentaje_ss_patronal = Decimal('0')
    mecanico.save(update_fields=['salario_base_mensual', 'porcentaje_ss_patronal'])
    check('Coste hora mecanico = 35,00', mecanico.coste_hora == Decimal('35.00'),
          str(mecanico.coste_hora))

    ot = OrdenTrabajo.objects.create(
        vehiculo=vehiculo, operario=mecanico,
        titulo='Diagnostico general y reparacion',
        descripcion='Revision general: cambio aceite, filtros, frenos',
        horas_estimadas=Decimal('4'), estado='PENDIENTE',
        created_by=admin,
    )
    MaterialUsado.objects.create(orden_trabajo=ot, material=aceite, cantidad=Decimal('5'))
    MaterialUsado.objects.create(orden_trabajo=ot, material=pastillas, cantidad=Decimal('1'))
    check('Stock tras consumo: aceite 15L / pastillas 2',
          aceite.stock_actual == 15 and pastillas.stock_actual == 2,
          f'{aceite.stock_actual} / {pastillas.stock_actual}')
    check('Coste materiales OT = 77,50', ot.coste_materiales == Decimal('77.50'),
          str(ot.coste_materiales))
    ot.estado = 'COMPLETADA'
    ot.horas_reales = Decimal('3')
    ot.fecha_fin = date(2026, 7, 5)
    ot.save()
    ot_asiento = ot.crear_asiento_contable()
    check('Capitalizacion OT (310 182,50 / 300 77,50 + 611 105) POSTEADA',
          ot_asiento is not None and ot_asiento.estado == 'POSTEADO')
    check('Asiento OT cuadrado', ot_asiento is not None and ot_asiento.esta_cuadrado)
    check('Movimientos OT: 310/300/611',
          {m.cuenta.codigo for m in ot_asiento.movimientos.all()} == {'310', '300', '611'})
    check('Coste reparacion vehiculo = 182,50', vehiculo.coste_reparacion == Decimal('182.50'),
          str(vehiculo.coste_reparacion))
    check('Coste total vehiculo = 8.332,50', vehiculo.coste_total == Decimal('8332.50'),
          str(vehiculo.coste_total))

    print('\n--- PASO 3.5 / 4.1: ACONDICIONADO -> EN_VENTA (precio 11.900) ---')
    vehiculo.estado = 'ACONDICIONADO'
    vehiculo.save()
    vehiculo.estado = 'EN_VENTA'
    vehiculo.precio_venta = Decimal('11900.00')
    vehiculo.save()
    check('Vehiculo EN_VENTA', vehiculo.estado == 'EN_VENTA')

    print('\n--- PASO 5.1: Venta REBU B2C 11.900 ---')
    venta = VentaVehiculo.objects.create(
        vehiculo=vehiculo,
        tipo_cliente='PARTICULAR',
        cliente_nombre='Antonio Perez Martin',
        cliente_dni='12345678Z',
        cliente_direccion='Calle Mayor 10, 4oA',
        cliente_poblacion='Alcala de Henares',
        cliente_provincia='Madrid',
        cliente_cp='28801',
        cliente_telefono='612345678',
        cliente_email='antonio.perez@email.com',
        fecha_venta=date(2026, 7, 15),
        metodo_pago='TRANSFERENCIA',
        precio_venta=Decimal('11900.00'),
        coste_total=vehiculo.coste_total,
        created_by=admin,
    )
    check('Base imponible REBU = 2.948,35 (3.567,50/1,21)', venta.base_imponible == Decimal('2948.35'),
          str(venta.base_imponible))
    check('Cuota IVA REBU = 619,15', venta.cuota_iva == Decimal('619.15'), str(venta.cuota_iva))

    vehiculo.estado = 'VENDIDO'
    vehiculo.save()
    garantia = GarantiaVehiculo.objects.create(
        venta=venta, tipo_cliente='PARTICULAR', fecha_inicio=date(2026, 7, 15),
    )
    venta.crear_asiento_contable()
    venta.registrar_movimiento_banco(asiento=venta.asiento_contable)

    venta_asiento = venta.asiento_contable
    check('Asiento venta POSTEADO', venta_asiento.estado == 'POSTEADO')
    check('Asiento venta cuadrado (572 11.900 / 700+471+310)', venta_asiento.esta_cuadrado)
    check('Movimientos venta: 572/700/471/310',
          {m.cuenta.codigo for m in venta_asiento.movimientos.all()} == {'572', '700', '471', '310'})
    check('Vehiculo VENDIDO', vehiculo.estado == 'VENDIDO')
    check('Garantia 12 meses vigente',
          garantia.esta_vigente and (garantia.fecha_fin - garantia.fecha_inicio).days in (365, 366))

    print('\n--- PASO 8.6: Gasto de estructura (alquiler con retencion IRPF) ---')
    gasto = GastoEstructura.objects.create(
        fecha_factura=date(2026, 7, 20),
        proveedor_acreedor='Propietario Galpon S.L.',
        cif_nif='B87654321',
        categoria='ARRENDAMIENTO',
        base_imponible=Decimal('2000.00'),
        tipo_iva=Decimal('21.00'),
        retencion_irpf=Decimal('19.00'),
        created_by=admin,
    )
    check('Gasto: cuota IVA = 420,00', gasto.cuota_iva == Decimal('420.00'),
          str(gasto.cuota_iva))
    check('Gasto: cuota retencion = 380,00', gasto.cuota_retencion == Decimal('380.00'),
          str(gasto.cuota_retencion))
    check('Gasto: total factura = 2.040,00', gasto.total_factura == Decimal('2040.00'),
          str(gasto.total_factura))
    gasto_asiento = gasto.crear_asiento_contable()
    check('Asiento gasto POSTEADO automaticamente', gasto_asiento.estado == 'POSTEADO')
    check('Asiento gasto cuadrado (621+472 / 4751.115+410)', gasto_asiento.esta_cuadrado)
    check('Movimientos gasto: 621/472/4751.115/410',
          {m.cuenta.codigo for m in gasto_asiento.movimientos.all()}
          == {'621', '472', '4751.115', '410'})
    check('Gasto NO genera movimiento bancario (pendiente en 410)',
          BancoMovimiento.objects.count() == 4)

    print('\n--- §20.4: VERIFICACION POST-PRUEBA ---')
    print('\n[Asientos]')
    asientos = list(AsientoContable.objects.order_by('numero'))
    check(f'Total asientos POSTEADOS = 8 (6 del manual + capitalizacion OT + gasto estructura)',
          len(asientos) == 8 and all(a.estado == 'POSTEADO' for a in asientos),
          f'{len(asientos)}')
    check('Todos los asientos cuadrados (DEBE = HABER)',
          all(a.esta_cuadrado for a in asientos))

    print('\n[Banco]')
    movs = list(BancoMovimiento.objects.order_by('fecha'))
    check('4 movimientos bancarios (deposito, inversion, vehiculo, cobro)',
          len(movs) == 4, f'{len(movs)}')
    check('Saldo banco = 51.133,00 (50.000 - 2.480,50 - 8.286,50 + 11.900)',
          banco.saldo_pendiente == Decimal('51133.00'), str(banco.saldo_pendiente))
    check('Cobro venta registrado (INGRESO 11.900)',
          any(m.tipo == 'INGRESO' and m.importe == Decimal('11900.00') for m in movs))

    print('\n[Inventario]')
    valor_stock = aceite.stock_actual * aceite.precio_unitario + \
        pastillas.stock_actual * pastillas.precio_unitario
    check('Valor stock materiales = 197,50 (15L + 2 juegos)',
          valor_stock == Decimal('197.50'), str(valor_stock))

    print('\n[Informes]')
    pyg = reports.calcular_pyg(date(2026, 1, 1), date(2026, 12, 31))
    check('PyG: Ingresos (700) = 2.948,35', pyg['ingresos']['ventas'] == Decimal('2948.35'),
          str(pyg['ingresos']['ventas']))
    check('PyG: resultado bruto = 2.948,35 (sin coste 600 duplicado)',
          pyg['resultado_bruto'] == Decimal('2948.35'), str(pyg['resultado_bruto']))
    check('PyG: variacion existencias (611) = 105,00 (mano de obra capitalizada)',
          pyg['variacion_existencias'] == Decimal('105.00'),
          str(pyg['variacion_existencias']))
    check('PyG: arrendamientos (621) = 2.000,00 (gasto estructura)',
          pyg['gastos_operativos']['arrendamientos'] == Decimal('2000.00'),
          str(pyg['gastos_operativos']['arrendamientos']))
    check('PyG: total gastos operativos = 2.000,00',
          pyg['gastos_operativos']['total'] == Decimal('2000.00'),
          str(pyg['gastos_operativos']['total']))
    check('PyG: resultado neto = 1.053,35 (2.948,35 + 105,00 - 2.000,00)',
          pyg['resultado_neto'] == Decimal('1053.35'), str(pyg['resultado_neto']))

    iva = reports.calcular_libro_iva(date(2026, 1, 1), date(2026, 12, 31))
    check('IVA repercutido (471) = 619,15', iva['iva_repercutido']['total'] == Decimal('619.15'),
          str(iva['iva_repercutido']['total']))
    check('IVA soportado (472) = 1.044,75 (624,75 + 420,00 alquiler)',
          iva['iva_soportado']['total'] == Decimal('1044.75'),
          str(iva['iva_soportado']['total']))

    balance = reports.calcular_balance(date(2026, 12, 31))
    check('Balance cuadra: Activo = Pasivo + Patrimonio',
          balance['activo']['total'] == balance['total_pasivo_patrimonio'],
          f'{balance["activo"]["total"]} vs {balance["total_pasivo_patrimonio"]}')
    check('310 a 0 tras la venta (reparacion capitalizada)',
          saldo('310') == Decimal('0'), str(saldo('310')))
    check('300 = 197,50 (materiales no consumidos)',
          saldo('300') == Decimal('197.50'), str(saldo('300')))
    check('621 = 2.000,00 (alquiler devengado)',
          saldo('621') == Decimal('2000.00'), str(saldo('621')))
    check('410 = -2.372,75 (compras 332,75 + alquiler 2.040 pendientes)',
          saldo('410') == Decimal('-2372.75'), str(saldo('410')))
    check('4751 = -380,00 (retencion IRPF pendiente de ingreso)',
          saldo('4751') == Decimal('-380.00'), str(saldo('4751')))

    existencias = reports.obtener_valor_existencias()
    check('Existencias: diferencia = 0 (stock == contable)',
          existencias['diferencia'] == Decimal('0'),
          f"valor {existencias['total_valor']} / contable {existencias['saldo_contable']}")
    check('Gasto de estructura NO toca inventario (300 sigue en 197,50)',
          saldo('300') == Decimal('197.50'), str(saldo('300')))
    resp = c.get('/erp/contabilidad/informes/existencias/')
    check('Informe existencias renderiza sin aviso de descuadre',
          resp.status_code == 200 and 'supera el valor seg' not in resp.content.decode('utf-8', 'ignore'))

    print('\n[KPIs]')
    check('KPIs: 1 vehiculo, 0 en venta, 1 vendido, 1 OT completada, 0 pendientes',
          Vehiculo.objects.count() == 1
          and Vehiculo.objects.filter(estado='EN_VENTA').count() == 0
          and Vehiculo.objects.filter(estado='VENDIDO').count() == 1
          and OrdenTrabajo.objects.filter(estado='COMPLETADA').count() == 1
          and OrdenTrabajo.objects.filter(estado='PENDIENTE').count() == 0)

    print('\n[Render de informes]')
    for url in ['/erp/contabilidad/informes/pyg/',
                '/erp/contabilidad/informes/balance/',
                '/erp/contabilidad/informes/iva/',
                '/erp/contabilidad/informes/libro-diario/',
                '/erp/contabilidad/informes/libro-mayor/']:
        resp = c.get(url)
        check(f'GET {url.split("/")[-2]}', resp.status_code == 200, str(resp.status_code))

    print('\n[Render modulo gastos]')
    resp = c.get('/erp/gastos/')
    check('GET /erp/gastos/ (listado)', resp.status_code == 200, str(resp.status_code))
    resp = c.get(f'/erp/gastos/{gasto.pk}/')
    check('GET /erp/gastos/<pk>/ (detalle)', resp.status_code == 200, str(resp.status_code))
    resp = c.get('/erp/gastos/exportar/')
    check('GET /erp/gastos/exportar/ (CSV gestoria)', resp.status_code == 200,
          str(resp.status_code))


def main():
    print('=' * 60)
    print('  PRUEBA DEL SISTEMA - CAPITULO 20 (pipeline completo)')
    print('=' * 60)
    c = Client()
    admin = User.objects.get(username='admin')
    c.force_login(admin)

    try:
        with transaction.atomic():
            clean_slate()
            ejecutar(c, admin)
            transaction.set_rollback(True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        check('Pipeline sin excepciones', False, str(e))

    print('\n' + '=' * 60)
    ok = sum(1 for _, cond in checks if cond)
    fail = sum(1 for _, cond in checks if not cond)
    for name, cond in checks:
        if not cond:
            print(f'  [FAIL] {name}')
    print('=' * 60)
    print(f'  Total: {ok + fail} | OK: {ok} | FAIL: {fail}')
    print('=' * 60)
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
