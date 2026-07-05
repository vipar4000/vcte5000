from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, DecimalField
from apps.vehicles.models import Vehiculo
from apps.workshop.models import Material, OrdenTrabajo


@login_required
def home_view(request):
    """Vista principal del dashboard."""
    
    # Estadísticas de vehículos
    stats_vehiculos = {
        'total': Vehiculo.objects.count(),
        'adquiridos': Vehiculo.objects.filter(estado='ADQUIRIDO').count(),
        'en_taller': Vehiculo.objects.filter(estado='TALLER').count(),
        'acondicionados': Vehiculo.objects.filter(estado='ACONDICIONADO').count(),
        'en_venta': Vehiculo.objects.filter(estado='EN_VENTA').count(),
        'vendidos': Vehiculo.objects.filter(estado='VENDIDO').count(),
    }
    
    # Estadísticas de taller
    stats_taller = {
        'ots_total': OrdenTrabajo.objects.count(),
        'ots_pendientes': OrdenTrabajo.objects.filter(estado='PENDIENTE').count(),
        'ots_en_progreso': OrdenTrabajo.objects.filter(estado='EN_PROGRESO').count(),
        'ots_completadas': OrdenTrabajo.objects.filter(estado='COMPLETADA').count(),
    }
    
    # Estadísticas de inventario
    valor_total_expr = ExpressionWrapper(
        F('stock_actual') * F('precio_unitario'),
        output_field=DecimalField()
    )
    stats_inventario = {
        'total_materiales': Material.objects.count(),
        'con_alerta': Material.objects.filter(alerta_stock=True).count(),
        'valor_total': Material.objects.aggregate(
            total=Sum(valor_total_expr)
        )['total'] or 0,
    }
    
    # Alertas de stock
    alertas_stock = Material.objects.filter(alerta_stock=True)[:5]
    
    # Últimos vehículos
    ultimos_vehiculos = Vehiculo.objects.all()[:5]
    
    # Últimas OTs
    ultimas_ots = OrdenTrabajo.objects.select_related(
        'vehiculo', 'operario'
    ).all()[:5]
    
    # Coste total de reparaciones activas
    coste_reparaciones_activas = OrdenTrabajo.objects.filter(
        estado__in=['PENDIENTE', 'EN_PROGRESO']
    ).aggregate(
        total=Sum('horas_reales')
    )['total'] or 0
    
    context = {
        'stats_vehiculos': stats_vehiculos,
        'stats_taller': stats_taller,
        'stats_inventario': stats_inventario,
        'alertas_stock': alertas_stock,
        'ultimos_vehiculos': ultimos_vehiculos,
        'ultimas_ots': ultimas_ots,
        'coste_reparaciones_activas': coste_reparaciones_activas,
    }
    return render(request, 'home.html', context)


@login_required
def operario_redirect(request):
    """Redirect /operario/ to kiosco de fichaje."""
    return redirect('attendance:kiosco')


@login_required
def vendedor_redirect(request):
    """Redirect /vendedor/ to catalogo de ventas."""
    return redirect('sales:list')


@login_required
def gestoria_redirect(request):
    """Redirect /gestoria/ to contabilidad."""
    return redirect('accounting:asientos')
