"""
Vistas de informes financieros - Pymes.
P&L, Balance, IVA, Modelo 303/390, Comparativa.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import date


@login_required
def pyg_view(request):
    """Informe de Pérdidas y Ganancias (PyG) Pymes."""
    anio = int(request.GET.get('anio', date.today().year))
    
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
    
    from .reports import calcular_balance
    balance = calcular_balance(fecha_corte)
    
    context = {
        'balance': balance,
        'fecha_corte': fecha_corte,
    }
    return render(request, 'accounting/reports/balance.html', context)


@login_required
def iva_view(request):
    """Libro de IVA por trimestre (Modelo 303/390)."""
    anio = int(request.GET.get('anio', date.today().year))
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
    anio_actual = int(request.GET.get('anio_actual', date.today().year))
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
    from datetime import date
    anio = date.today().year
    
    context = {
        'anio': anio,
    }
    return render(request, 'accounting/reports/list.html', context)


@login_required
def facturas_compra_view(request):
    """Reporte de Facturas de Compra: agrupa CompraMaterial por numero_factura."""
    from decimal import Decimal
    from django.db.models import Sum
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
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'proveedor': proveedor,
        'total_base': sum(f['base'] for f in facturas),
        'total_iva': sum(f['iva'] for f in facturas),
        'total_total': sum(f['total'] for f in facturas),
        'n_facturas': len(facturas),
    }
    return render(request, 'accounting/reports/facturas_compras.html', context)
