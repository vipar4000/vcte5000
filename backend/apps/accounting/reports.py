"""
Servicio de informes financieros - PGC español / Pymes.
Genera datos para P&L, Balance, IVA, Modelo 303/390.
"""
from django.db.models import Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
from datetime import date


def obtener_saldo_cuenta(codigo_inicio, fecha_desde=None, fecha_hasta=None):
    """
    Obtiene el saldo total de todas las cuentas que empiezan por un código.
    Para cuentas de gasto (6xx): saldo = DEBE - HABER
    Para cuentas de ingreso (7xx): saldo = HABER - DEBE
    Para cuentas de activo/pasivo: saldo = DEBE - HABER
    """
    from apps.accounting.models import MovimientoContable
    
    filtros = Q(cuenta__codigo__startswith=codigo_inicio)
    
    if fecha_desde:
        filtros &= Q(asiento__fecha__gte=fecha_desde)
    if fecha_hasta:
        filtros &= Q(asiento__fecha__lte=fecha_hasta)
    
    # Solo asientos posteados
    filtros &= Q(asiento__estado='POSTEADO')
    
    resultado = MovimientoContable.objects.filter(filtros).aggregate(
        total_debe=Coalesce(Sum('debe'), Decimal('0')),
        total_haber=Coalesce(Sum('haber'), Decimal('0')),
    )
    
    return resultado['total_debe'], resultado['total_haber']


def calcular_pyg(fecha_desde, fecha_hasta):
    """
    Calcula el PyG (Pérdidas y Ganancias) simplificado Pymes.
    
    Estructura:
    1. Ingresos por ventas (700)
    2. Compras y gastos (6xx)
    3. = Resultado Bruto
    4. Gastos de personal (640, 642)
    5. Otros gastos (620, 621, 623, 628, 629)
    6. = EBITDA
    7. Amortizaciones (2xx depreciación)
    8. = EBIT (Resultado operativo)
    9. Gastos financieros (630)
    10. = Beneficio antes de impuestos
    11. Impuesto sociedades (680)
    12. = Resultado neto
    """
    
    def saldo(codigo):
        debe, haber = obtener_saldo_cuenta(codigo, fecha_desde, fecha_hasta)
        return debe - haber
    
    def saldo_haber(codigo):
        """Para cuentas de ingreso (7xx): HABER - DEBE"""
        debe, haber = obtener_saldo_cuenta(codigo, fecha_desde, fecha_hasta)
        return haber - debe
    
    # 1. Ingresos
    ventas = saldo_haber('700')
    
    # 2. Coste de ventas
    compras = saldo('600')
    repuestos = saldo('600')
    
    # 3. Resultado bruto
    resultado_bruto = ventas - compras - repuestos
    
    # 4. Gastos de personal
    sueldos = saldo('640')
    seguridad_social = saldo('642')
    gastos_personal = sueldos + seguridad_social
    
    # 5. Otros gastos operativos
    servicios_exteriores = saldo('602')
    arrendamientos = saldo('621')
    reparaciones = saldo('623')
    suministros = saldo('628')
    otros_gastos = saldo('629')
    Otros_gastos_operativos = servicios_exteriores + arrendamientos + reparaciones + suministros + otros_gastos
    
    # 6. EBITDA
    ebitda = resultado_bruto - gastos_personal - Otros_gastos_operativos
    
    # 7. Gastos financieros
    gastos_financieros = saldo('630')
    
    # 8. Resultado antes de impuestos
    resultado_antes_impuestos = ebitda - gastos_financieros
    
    # 9. Impuesto sociedades
    impuesto_sociedades = saldo('680')
    
    # 10. Resultado neto
    resultado_neto = resultado_antes_impuestos - impuesto_sociedades
    
    return {
        'periodo': {'desde': fecha_desde, 'hasta': fecha_hasta},
        'ingresos': {
            'ventas': ventas,
        },
        'coste_ventas': {
            'compras': compras,
            'repuestos': repuestos,
            'total': compras + repuestos,
        },
        'resultado_bruto': resultado_bruto,
        'margen_bruto_pct': (resultado_bruto / ventas * 100) if ventas > 0 else Decimal('0'),
        'gastos_operativos': {
            'sueldos': sueldos,
            'seguridad_social': seguridad_social,
            'gastos_personal_total': gastos_personal,
            'servicios_exteriores': servicios_exteriores,
            'arrendamientos': arrendamientos,
            'reparaciones': reparaciones,
            'suministros': suministros,
            'otros_gastos': otros_gastos,
            'otros_gastos_operativos_total': Otros_gastos_operativos,
            'total': gastos_personal + Otros_gastos_operativos,
        },
        'ebitda': ebitda,
        'margen_ebitda_pct': (ebitda / ventas * 100) if ventas > 0 else Decimal('0'),
        'gastos_financieros': gastos_financieros,
        'resultado_antes_impuestos': resultado_antes_impuestos,
        'impuesto_sociedades': impuesto_sociedades,
        'resultado_neto': resultado_neto,
        'margen_neto_pct': (resultado_neto / ventas * 100) if ventas > 0 else Decimal('0'),
    }


def calcular_balance(fecha_corte):
    """
    Calcula el Balance de Situación simplificado Pymes.
    
    ACTIVO:
    - Activo corriente: 3xx (existencias), 430 (clientes), 440 (deudores), 5xx (tesorería)
    - Activo no corriente: 2xx (inmovilizado)
    
    PASIVO:
    - Pasivo corriente: 400 (proveedores), 410 (acreedores), 471 (IVA repercutido), 472 (IVA soportado)
    - Pasivo no corriente: 1xx (financiación)
    
    PATRIMONIO NETO:
    - 100 (capital), 102 (reservas), 110 (resultados acumulados), 129 (resultado ejercicio)
    """
    
    def saldo_grupo(codigo):
        debe, haber = obtener_saldo_cuenta(codigo, fecha_hasta=fecha_corte)
        return debe - haber
    
    def saldo_grupo_haber(codigo):
        """Para cuentas de pasivo/neto: HABER - DEBE"""
        debe, haber = obtener_saldo_cuenta(codigo, fecha_hasta=fecha_corte)
        return haber - debe
    
    # ACTIVO
    inmovilizado = saldo_grupo('2')
    existencias = saldo_grupo('3')
    clientes = saldo_grupo('430')
    deudores = saldo_grupo('440')
    tesoreria = saldo_grupo('5')
    
    activo_no_corriente = inmovilizado
    activo_corriente = existencias + clientes + deudores + tesoreria
    total_activo = activo_no_corriente + activo_corriente
    
    # PASIVO
    proveedores = saldo_grupo_haber('400')
    acreedores = saldo_grupo_haber('410')
    iva_repercutido = saldo_grupo_haber('471')
    iva_soportado = saldo_grupo('472')  # IVA soportado es deudor
    
    pasivo_corriente = proveedores + acreedores + iva_repercutido - iva_soportado
    financiacion = saldo_grupo_haber('1')
    pasivo_no_corriente = financiacion
    total_pasivo = pasivo_corriente + pasivo_no_corriente
    
    # PATRIMONIO NETO
    capital = saldo_grupo_haber('100')
    reservas = saldo_grupo_haber('102')
    resultados_acumulados = saldo_grupo_haber('110')
    resultado_ejercicio = saldo_grupo_haber('129')
    
    patrimonio_neto = capital + reservas + resultados_acumulados + resultado_ejercicio
    
    return {
        'fecha': fecha_corte,
        'activo': {
            'no_corriente': {
                'inmovilizado': inmovilizado,
                'total': activo_no_corriente,
            },
            'corriente': {
                'existencias': existencias,
                'clientes': clientes,
                'deudores': deudores,
                'tesoreria': tesoreria,
                'total': activo_corriente,
            },
            'total': total_activo,
        },
        'pasivo': {
            'corriente': {
                'proveedores': proveedores,
                'acreedores': acreedores,
                'iva_repercutido': iva_repercutido,
                'iva_soportado': iva_soportado,
                'total': pasivo_corriente,
            },
            'no_corriente': {
                'financiacion': financiacion,
                'total': pasivo_no_corriente,
            },
            'total': total_pasivo,
        },
        'patrimonio_neto': {
            'capital': capital,
            'reservas': reservas,
            'resultados_acumulados': resultados_acumulados,
            'resultado_ejercicio': resultado_ejercicio,
            'total': patrimonio_neto,
        },
        'total_pasivo_patrimonio': total_pasivo + patrimonio_neto,
    }


def calcular_libro_iva(fecha_desde, fecha_hasta):
    """
    Calcula el libro de IVA (Modelo 303/390) por trimestre.
    
    IVA Repercutido (cobrado al cliente):
    - 471: HABER - DEBE
    
    IVA Soportado (pagado a proveedores):
    - 472: DEBE - HABER
    
    Liquidación trimestral:
    - IVA repercutido - IVA soportado = Cuota a liquidar
    """
    from apps.accounting.models import MovimientoContable
    
    # IVA Repercutido (471)
    iva_repercutido = MovimientoContable.objects.filter(
        cuenta__codigo='471',
        asiento__fecha__gte=fecha_desde,
        asiento__fecha__lte=fecha_hasta,
        asiento__estado='POSTEADO',
    ).aggregate(
        debe=Coalesce(Sum('debe'), Decimal('0')),
        haber=Coalesce(Sum('haber'), Decimal('0')),
    )
    
    iva_repercido_total = iva_repercutido['haber'] - iva_repercutido['debe']
    
    # IVA Soportado (472)
    iva_soportado = MovimientoContable.objects.filter(
        cuenta__codigo='472',
        asiento__fecha__gte=fecha_desde,
        asiento__fecha__lte=fecha_hasta,
        asiento__estado='POSTEADO',
    ).aggregate(
        debe=Coalesce(Sum('debe'), Decimal('0')),
        haber=Coalesce(Sum('haber'), Decimal('0')),
    )
    
    iva_soportado_total = iva_soportado['debe'] - iva_soportado['haber']
    
    # Base imponible (ventas 700)
    ventas = MovimientoContable.objects.filter(
        cuenta__codigo__startswith='700',
        asiento__fecha__gte=fecha_desde,
        asiento__fecha__lte=fecha_hasta,
        asiento__estado='POSTEADO',
    ).aggregate(
        haber=Coalesce(Sum('haber'), Decimal('0')),
    )
    
    base_imponible_ventas = ventas['haber']
    
    # Base imponible (compras 600)
    compras = MovimientoContable.objects.filter(
        cuenta__codigo__startswith='600',
        asiento__fecha__gte=fecha_desde,
        asiento__fecha__lte=fecha_hasta,
        asiento__estado='POSTEADO',
    ).aggregate(
        debe=Coalesce(Sum('debe'), Decimal('0')),
    )
    
    base_imponible_compras = compras['debe']
    
    # Cuota a liquidar
    cuota_liquidar = iva_repercido_total - iva_soportado_total
    
    return {
        'periodo': {'desde': fecha_desde, 'hasta': fecha_hasta},
        'iva_repercutido': {
            'base_imponible': base_imponible_ventas,
            'debe': iva_repercutido['debe'],
            'haber': iva_repercutido['haber'],
            'total': iva_repercido_total,
        },
        'iva_soportado': {
            'base_imponible': base_imponible_compras,
            'debe': iva_soportado['debe'],
            'haber': iva_soportado['haber'],
            'total': iva_soportado_total,
        },
        'cuota_liquidar': cuota_liquidar,
        'a_favor_cliente': cuota_liquidar < 0,
    }


def calcular_trimestre(trimestre, anio):
    """Devuelve fechas de inicio/fin para un trimestre."""
    trimestres = {
        1: (date(anio, 1, 1), date(anio, 3, 31)),
        2: (date(anio, 4, 1), date(anio, 6, 30)),
        3: (date(anio, 7, 1), date(anio, 9, 30)),
        4: (date(anio, 10, 1), date(anio, 12, 31)),
    }
    return trimestres.get(trimestre)


def calcular_comparativa(anio_actual, anio_anterior):
    """Compara PyG de dos años consecutivos."""
    pyg_actual = calcular_pyg(
        date(anio_actual, 1, 1), date(anio_actual, 12, 31)
    )
    pyg_anterior = calcular_pyg(
        date(anio_anterior, 1, 1), date(anio_anterior, 12, 31)
    )
    
    def variacion(actual, anterior):
        if anterior == 0:
            return Decimal('0') if actual == 0 else Decimal('100')
        return ((actual - anterior) / abs(anterior) * 100).quantize(Decimal('0.1'))
    
    return {
        'anio_actual': anio_actual,
        'anio_anterior': anio_anterior,
        'ventas': {
            'actual': pyg_actual['ingresos']['ventas'],
            'anterior': pyg_anterior['ingresos']['ventas'],
            'variacion': variacion(pyg_actual['ingresos']['ventas'], pyg_anterior['ingresos']['ventas']),
        },
        'coste_ventas': {
            'actual': pyg_actual['coste_ventas']['total'],
            'anterior': pyg_anterior['coste_ventas']['total'],
            'variacion': variacion(pyg_actual['coste_ventas']['total'], pyg_anterior['coste_ventas']['total']),
        },
        'resultado_bruto': {
            'actual': pyg_actual['resultado_bruto'],
            'anterior': pyg_anterior['resultado_bruto'],
            'variacion': variacion(pyg_actual['resultado_bruto'], pyg_anterior['resultado_bruto']),
        },
        'ebitda': {
            'actual': pyg_actual['ebitda'],
            'anterior': pyg_anterior['ebitda'],
            'variacion': variacion(pyg_actual['ebitda'], pyg_anterior['ebitda']),
        },
        'resultado_neto': {
            'actual': pyg_actual['resultado_neto'],
            'anterior': pyg_anterior['resultado_neto'],
            'variacion': variacion(pyg_actual['resultado_neto'], pyg_anterior['resultado_neto']),
        },
    }
