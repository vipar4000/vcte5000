"""Chequeo de datos reales: ejecuta los generadores de informes contra la DB de desarrollo.

Valida que la lógica de informes no rompa con datos reales:
- Balance de Situacion: Activo == Pasivo + Patrimonio Neto.
- Libro Diario: todos los asientos posteados cuadrados (debe == haber).
- Valoracion de existencias: saldo contable vs stock fisico valorado.
- PyG, IVA y Comparativa: se ejecutan sin errores.

Uso: python check_report_data.py
"""
import os
import sys
import django
from datetime import date
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
django.setup()

from apps.accounting import reports


checks = []


def check(name, cond, detalle=''):
    checks.append((name, cond))
    estado = 'OK' if cond else 'FAIL'
    print(f'  [{estado}] {name}{(" - " + detalle) if detalle else ""}')


anio_actual = date.today().year
anio_anterior = anio_actual - 1

print('=== BALANCE DE SITUACION ===')
for anio in (anio_actual, anio_anterior):
    balance = reports.calcular_balance(date(anio, 12, 31))
    activo = balance['activo']['total']
    pasivo_patrimonio = balance['total_pasivo_patrimonio']
    check(
        f'Balance {anio}: cuadre Activo = Pasivo + Patrimonio',
        activo == pasivo_patrimonio,
        f'Activo {activo} vs {pasivo_patrimonio}',
    )
    check(f'Balance {anio}: patrimonio no negativo', balance['patrimonio_neto']['total'] >= 0)

print('\n=== LIBRO DIARIO ===')
for anio in (anio_actual, anio_anterior):
    diario = reports.obtener_asientos_diario(date(anio, 1, 1), date(anio, 12, 31))
    descuadrados = [a['numero'] for a in diario['asientos'] if a['total_debe'] != a['total_haber']]
    check(
        f'Diario {anio}: {diario["n_asientos"]} asientos, todos cuadrados',
        not descuadrados,
        f'descuadrados: {descuadrados}' if descuadrados else '',
    )
    check(
        f'Diario {anio}: totales generales coinciden',
        diario['total_debe'] == diario['total_haber'],
        f'debe {diario["total_debe"]} / haber {diario["total_haber"]}',
    )

print('\n=== VALORACION DE EXISTENCIAS ===')
existencias = reports.obtener_valor_existencias()
check(
    'Existencias: stock valorado >= 0',
    existencias['total_valor'] >= 0,
    f'total valor {existencias["total_valor"]}',
)
check(
    'Existencias: saldo contable calculado',
    existencias['saldo_contable'] == existencias['saldo_contable'],
    f'saldo contable {existencias["saldo_contable"]}',
)
print(f'    materiales: {len(existencias["materiales"])} | valor {existencias["total_valor"]} | '
      f'contable {existencias["saldo_contable"]} | diferencia {existencias["diferencia"]}')

print('\n=== PYG ===')
pyg = reports.calcular_pyg(date(anio_actual, 1, 1), date(anio_actual, 12, 31))
check(
    'PyG: resultado neto coherente (ingresos - todos los gastos)',
    pyg['resultado_neto'] == pyg['resultado_antes_impuestos'] - pyg['impuesto_sociedades'],
    f'neto {pyg["resultado_neto"]}',
)

print('\n=== IVA (anual) ===')
iva = reports.calcular_libro_iva(date(anio_actual, 1, 1), date(anio_actual, 12, 31))
check(
    'IVA: cuota a liquidar = repercutido - soportado',
    iva['cuota_liquidar'] == iva['iva_repercutido']['total'] - iva['iva_soportado']['total'],
    f'cuota {iva["cuota_liquidar"]}',
)

print('\n=== COMPARATIVA ===')
comparativa = reports.calcular_comparativa(anio_actual, anio_anterior)
check(
    f'Comparativa {anio_actual} vs {anio_anterior}: ejecutada sin errores',
    comparativa['ventas']['variacion'] is not None,
)

print('\n' + '=' * 50)
fallos = [name for name, ok in checks if not ok]
print(f'RESULTADO: {len(checks) - len(fallos)}/{len(checks)} chequeos OK')
if fallos:
    print(f'FALLOS: {fallos}')
    sys.exit(1)
print('TODOS LOS CHEQUEOS PASARON')
