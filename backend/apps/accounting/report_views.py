"""
Vistas de informes financieros - Pymes.
P&L, Balance, IVA, Modelo 303/390, Comparativa.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import date


def parse_int_query(request, key, default):
    """Parsea un parametro entero tolerando el separador de miles espanol (2.026)."""
    raw = request.GET.get(key)
    if raw is None:
        return default
    try:
        return int(raw.replace('.', '').replace(',', ''))
    except (ValueError, TypeError):
        return default


@login_required
def pyg_view(request):
    """Informe de Pérdidas y Ganancias (PyG) Pymes."""
    anio = parse_int_query(request, 'anio', date.today().year)
    
    from .reports import calcular_pyg
    pyg = calcular_pyg(date(anio, 1, 1), date(anio, 12, 31))
    
    context = {
        'pyg': pyg,
        'anio': anio,
        'anios_disponibles': range(date.today().year, date.today().year - 5, -1),
    }
    return render(request, 'accounting/reports/pyg.html', context)


@login_required
def balance_view(request):
    """Informe de Balance de Situación."""
    fecha_str = request.GET.get('fecha', date.today().isoformat())
    try:
        fecha_corte = date.fromisoformat(fecha_str)
    except ValueError:
        fecha_corte = date.today()
    
    from .reports import calcular_balance, obtener_saldo_cuenta
    balance = calcular_balance(fecha_corte)
    
    # Desglose de cuentas individuales por grupo
    from decimal import Decimal
    from django.db.models import Sum
    from django.db.models.functions import Coalesce
    from apps.accounting.models import MovimientoContable

    cuentas_balance = {
        'activo_no_corriente': MovimientoContable.objects.filter(
            cuenta__codigo__startswith='2', asiento__fecha__lte=fecha_corte, asiento__estado='POSTEADO',
        ).values('cuenta__codigo', 'cuenta__nombre').annotate(
            total_debe=Coalesce(Sum('debe'), Decimal('0')), total_haber=Coalesce(Sum('haber'), Decimal('0')),
        ).order_by('cuenta__codigo'),
        'existencias': MovimientoContable.objects.filter(
            cuenta__codigo__in=['300','310','320','330'], asiento__fecha__lte=fecha_corte, asiento__estado='POSTEADO',
        ).values('cuenta__codigo', 'cuenta__nombre').annotate(
            total_debe=Coalesce(Sum('debe'), Decimal('0')), total_haber=Coalesce(Sum('haber'), Decimal('0')),
        ).order_by('cuenta__codigo'),
        'clientes': MovimientoContable.objects.filter(
            cuenta__codigo__startswith='430', asiento__fecha__lte=fecha_corte, asiento__estado='POSTEADO',
        ).values('cuenta__codigo', 'cuenta__nombre').annotate(
            total_debe=Coalesce(Sum('debe'), Decimal('0')), total_haber=Coalesce(Sum('haber'), Decimal('0')),
        ).order_by('cuenta__codigo'),
        'proveedores': MovimientoContable.objects.filter(
            cuenta__codigo__startswith='400', asiento__fecha__lte=fecha_corte, asiento__estado='POSTEADO',
        ).values('cuenta__codigo', 'cuenta__nombre').annotate(
            total_debe=Coalesce(Sum('debe'), Decimal('0')), total_haber=Coalesce(Sum('haber'), Decimal('0')),
        ).order_by('cuenta__codigo'),
    }

    for key in cuentas_balance:
        for c in cuentas_balance[key]:
            c['saldo'] = c['total_debe'] - c['total_haber']

    context = {
        'balance': balance,
        'fecha_corte': fecha_corte,
        'cuentas_balance': cuentas_balance,
    }
    return render(request, 'accounting/reports/balance.html', context)


@login_required
def iva_view(request):
    """Libro de IVA por trimestre (Modelo 303/390)."""
    anio = parse_int_query(request, 'anio', date.today().year)
    trimestre = int(request.GET.get('trimestre', (date.today().month - 1) // 3 + 1))
    
    from .reports import calcular_libro_iva, calcular_trimestre
    desde, hasta = calcular_trimestre(trimestre, anio)
    libro_iva = calcular_libro_iva(desde, hasta)
    
    # Acumulado anual para Modelo 390
    libro_iva_anual = calcular_libro_iva(date(anio, 1, 1), date(anio, 12, 31))
    
    context = {
        'libro_iva': libro_iva,
        'libro_iva_anual': libro_iva_anual,
        'anio': anio,
        'trimestre': trimestre,
        'anios_disponibles': range(date.today().year, date.today().year - 5, -1),
    }
    return render(request, 'accounting/reports/iva.html', context)


@login_required
def comparativa_view(request):
    """Comparativa año a año."""
    anio_actual = parse_int_query(request, 'anio_actual', date.today().year)
    anio_anterior = anio_actual - 1
    
    from .reports import calcular_comparativa
    comparativa = calcular_comparativa(anio_actual, anio_anterior)
    
    context = {
        'comparativa': comparativa,
        'anio_actual': anio_actual,
        'anios_disponibles': range(date.today().year, date.today().year - 5, -1),
    }
    return render(request, 'accounting/reports/comparativa.html', context)


@login_required
def informes_list(request):
    """Panel principal de informes financieros."""
    anio = date.today().year
    
    context = {
        'anio': anio,
    }
    return render(request, 'accounting/reports/list.html', context)


@login_required
def facturas_compra_view(request):
    """Reporte de Facturas de Compra: agrupa CompraMaterial por numero_factura."""
    from decimal import Decimal
    from apps.workshop.models import CompraMaterial

    compras = _filtrar_compras(request)
    compras = compras.select_related('material', 'asiento_contable').order_by(
        'fecha_compra', 'proveedor', 'numero_factura'
    )

    grupos = {}
    for c in compras:
        # Las lineas sin numero de factura se agrupan de forma unica por compra
        key = c.numero_factura or f'__sin__{c.pk}'
        grupos.setdefault(key, []).append(c)

    facturas = []
    for lineas in grupos.values():
        base = sum((l.base_imponible for l in lineas), Decimal('0'))
        iva = sum((l.cuota_iva for l in lineas), Decimal('0'))
        primera = lineas[0]
        facturas.append({
            'numero': primera.numero_factura or '(sin nº de factura)',
            'proveedor': primera.proveedor,
            'cif_nif': primera.cif_nif,
            'fecha': primera.fecha_compra,
            'lineas': lineas,
            'base': base,
            'iva': iva,
            'total': base + iva,
            'pdf': primera.documento_pdf,
        })

    context = {
        'facturas': facturas,
        'fecha_desde': request.GET.get('fecha_desde', '').strip(),
        'fecha_hasta': request.GET.get('fecha_hasta', '').strip(),
        'proveedor': request.GET.get('proveedor', '').strip(),
        'total_base': sum(f['base'] for f in facturas),
        'total_iva': sum(f['iva'] for f in facturas),
        'total_total': sum(f['total'] for f in facturas),
        'n_facturas': len(facturas),
    }
    return render(request, 'accounting/reports/facturas_compras.html', context)


@login_required
def libro_diario_view(request):
    """Libro Diario: asientos en orden cronológico con filtro de fechas."""
    desde = request.GET.get('desde', date.today().replace(month=1, day=1).isoformat())
    hasta = request.GET.get('hasta', date.today().isoformat())
    try:
        fecha_desde = date.fromisoformat(desde)
        fecha_hasta = date.fromisoformat(hasta)
    except ValueError:
        fecha_desde = date.today().replace(month=1, day=1)
        fecha_hasta = date.today()

    from .reports import obtener_asientos_diario
    diario = obtener_asientos_diario(fecha_desde, fecha_hasta)

    context = {
        'diario': diario,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    }
    return render(request, 'accounting/reports/libro_diario.html', context)


@login_required
def libro_mayor_view(request):
    """Libro Mayor: movimientos de una cuenta con saldo corrido."""
    codigo = request.GET.get('cuenta', '')
    desde = request.GET.get('desde', date.today().replace(month=1, day=1).isoformat())
    hasta = request.GET.get('hasta', date.today().isoformat())

    cuenta_obj = None
    movimientos = None
    total_debe = 0
    total_haber = 0
    saldo_final = 0
    error = None

    if codigo:
        try:
            fecha_desde = date.fromisoformat(desde)
            fecha_hasta = date.fromisoformat(hasta)
        except ValueError:
            fecha_desde = date.today().replace(month=1, day=1)
            fecha_hasta = date.today()

        from .reports import obtener_movimientos_cuenta
        resultado = obtener_movimientos_cuenta(codigo, fecha_desde, fecha_hasta)
        if resultado is None:
            error = f"Cuenta {codigo} no encontrada"
        else:
            cuenta_obj = resultado['cuenta']
            movimientos = resultado['movimientos']
            total_debe = resultado['total_debe']
            total_haber = resultado['total_haber']
            saldo_final = resultado['saldo_final']
    else:
        fecha_desde = date.today().replace(month=1, day=1)
        fecha_hasta = date.today()

    from apps.accounting.models import CuentaContable
    cuentas = CuentaContable.objects.all().order_by('codigo')

    context = {
        'codigo': codigo,
        'cuenta': cuenta_obj,
        'movimientos': movimientos,
        'total_debe': total_debe,
        'total_haber': total_haber,
        'saldo_final': saldo_final,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'cuentas': cuentas,
        'error': error,
    }
    return render(request, 'accounting/reports/libro_mayor.html', context)


@login_required
def existencias_view(request):
    """Informe de valoración de existencias."""
    from .reports import obtener_valor_existencias
    data = obtener_valor_existencias()

    context = {
        'data': data,
    }
    return render(request, 'accounting/reports/existencias.html', context)


def _filtrar_compras(request):
    """Aplica los filtros de fecha/proveedor a CompraMaterial (reutilizable)."""
    from apps.workshop.models import CompraMaterial

    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    proveedor = request.GET.get('proveedor', '').strip()

    compras = CompraMaterial.objects.all()
    if fecha_desde:
        compras = compras.filter(fecha_compra__gte=fecha_desde)
    if fecha_hasta:
        compras = compras.filter(fecha_compra__lte=fecha_hasta)
    if proveedor:
        compras = compras.filter(proveedor__icontains=proveedor)
    return compras
