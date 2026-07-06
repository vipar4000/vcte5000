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
