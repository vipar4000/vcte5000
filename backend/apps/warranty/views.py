from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum, Count
from datetime import date, timedelta
from .models import GarantiaVehiculo, HistorialReparacionGarantia
from .forms import HistorialReparacionGarantiaForm, FiltroGarantiasForm
from apps.sales.models import VentaVehiculo
from apps.expenses.services import transferir_coste_garantia


@login_required
def garantia_list(request):
    """Lista de garantías con filtros."""
    form = FiltroGarantiasForm(request.GET)
    garantias = GarantiaVehiculo.objects.select_related(
        'venta', 'venta__vehiculo'
    ).all()
    
    buscar = request.GET.get('buscar', '')
    estado = request.GET.get('estado', '')
    
    if buscar:
        garantias = garantias.filter(
            Q(venta__vehiculo__matricula__icontains=buscar) |
            Q(venta__cliente__first_name__icontains=buscar) |
            Q(venta__cliente__last_name__icontains=buscar) |
            Q(venta__cliente__nif__icontains=buscar)
        )
    
    if estado == 'vigente':
        garantias = garantias.filter(fecha_fin__gte=date.today())
    elif estado == 'caducada':
        garantias = garantias.filter(fecha_fin__lt=date.today())
    
    # Estadísticas
    total_vigentes = GarantiaVehiculo.objects.filter(fecha_fin__gte=date.today()).count()
    total_reparaciones = HistorialReparacionGarantia.objects.count()
    
    context = {
        'garantias': garantias,
        'form': form,
        'total_vigentes': total_vigentes,
        'total_reparaciones': total_reparaciones,
    }
    return render(request, 'warranty/list.html', context)


@login_required
def garantia_detail(request, pk):
    """Detalle de una garantía."""
    garantia = get_object_or_404(
        GarantiaVehiculo.objects.select_related(
            'venta', 'venta__vehiculo'
        ),
        pk=pk
    )
    
    reparaciones = garantia.reparaciones.all()
    total_reparaciones_coste = reparaciones.aggregate(
        total=Sum('total_costo_reparacion')
    )['total'] or 0
    
    context = {
        'garantia': garantia,
        'reparaciones': reparaciones,
        'total_reparaciones_coste': total_reparaciones_coste,
    }
    return render(request, 'warranty/detail.html', context)


@login_required
def reparacion_create(request, garantia_pk):
    """Crear una reparación en garantía."""
    garantia = get_object_or_404(GarantiaVehiculo, pk=garantia_pk)
    
    if request.method == 'POST':
        form = HistorialReparacionGarantiaForm(request.POST)
        if form.is_valid():
            reparacion = form.save()
            
            try:
                resultado = transferir_coste_garantia(
                    venta=reparacion.garantia.venta,
                    descripcion=reparacion.descripcion_averia,
                    costo_repuestos=reparacion.coste_repuestos,
                    costo_mano_obra=reparacion.coste_mano_obra,
                )
                if resultado and resultado.get('asiento'):
                    messages.success(
                        request,
                        f'Reparación registrada. Costes transferidos al gasto estructura #{resultado["gasto"].pk}.'
                    )
                else:
                    messages.success(
                        request,
                        f'Reparación registrada: {reparacion.descripcion_averia[:50]}...'
                    )
            except Exception as e:
                messages.warning(
                    request,
                    f'Reparación registrada, pero no se pudo transferir al gasto: {str(e)}'
                )
            
            return redirect('warranty:detail', pk=garantia.pk)
    else:
        form = HistorialReparacionGarantiaForm(initial={'garantia': garantia})
    
    context = {
        'form': form,
        'garantia': garantia,
    }
    return render(request, 'warranty/reparacion_form.html', context)


@login_required
def reparacion_update(request, pk):
    """Actualizar una reparación en garantía."""
    reparacion = get_object_or_404(HistorialReparacionGarantia, pk=pk)
    
    if request.method == 'POST':
        form = HistorialReparacionGarantiaForm(request.POST, instance=reparacion)
        if form.is_valid():
            form.save()
            messages.success(request, 'Reparación actualizada')
            return redirect('warranty:detail', pk=reparacion.garantia.pk)
    else:
        form = HistorialReparacionGarantiaForm(instance=reparacion)
    
    context = {
        'form': form,
        'reparacion': reparacion,
        'garantia': reparacion.garantia,
    }
    return render(request, 'warranty/reparacion_form.html', context)


@login_required
def garantia_stats(request):
    """Estadísticas de garantías para el dashboard."""
    hoy = date.today()
    
    stats = {
        'vigentes': GarantiaVehiculo.objects.filter(fecha_fin__gte=hoy).count(),
        'por_vencer_30d': GarantiaVehiculo.objects.filter(
            fecha_fin__gte=hoy,
            fecha_fin__lte=hoy + timedelta(days=30)
        ).count(),
        'reparaciones_pendientes': HistorialReparacionGarantia.objects.filter(
            estado__in=['ESTUDIO', 'PROCESO']
        ).count(),
        'coste_total_reparaciones': HistorialReparacionGarantia.objects.aggregate(
            total=Sum('total_costo_reparacion')
        )['total'] or 0,
    }
    
    return JsonResponse(stats)
