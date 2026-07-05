from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Sum
from decimal import Decimal
from .models import VentaVehiculo
from .forms import VentaVehiculoForm
from apps.vehicles.models import Vehiculo
from apps.warranty.models import GarantiaVehiculo


@login_required
def venta_list(request):
    """Lista de ventas con filtros."""
    ventas = VentaVehiculo.objects.select_related('vehiculo', 'created_by').all()
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    metodo_pago = request.GET.get('metodo_pago', '')
    
    if busqueda:
        ventas = ventas.filter(
            Q(cliente_nombre__icontains=busqueda) |
            Q(cliente_dni__icontains=busqueda) |
            Q(vehiculo__matricula__icontains=busqueda) |
            Q(vehiculo__marca__icontains=busqueda)
        )
    
    if metodo_pago:
        ventas = ventas.filter(metodo_pago=metodo_pago)
    
    # Estadísticas
    stats = {
        'total': VentaVehiculo.objects.count(),
        'total_ventas': VentaVehiculo.objects.aggregate(
            total=Sum('precio_venta')
        )['total'] or 0,
        'beneficio_total': sum(v.beneficio for v in VentaVehiculo.objects.all()),
    }
    
    context = {
        'ventas': ventas[:50],
        'stats': stats,
        'busqueda': busqueda,
    }
    return render(request, 'sales/list.html', context)


@login_required
def venta_detail(request, pk):
    """Detalle de una venta."""
    venta = get_object_or_404(
        VentaVehiculo.objects.select_related('vehiculo', 'created_by'),
        pk=pk
    )
    
    context = {
        'venta': venta,
        'beneficio': venta.beneficio,
        'precio_final': venta.precio_final_cliente,
    }
    return render(request, 'sales/detail.html', context)


@login_required
def venta_create(request):
    """Registrar nueva venta."""
    if not request.user.is_admin and not request.user.is_vendedor:
        messages.error(request, 'No tiene permisos para registrar ventas.')
        return redirect('sales:list')
    
    # Pre-seleccionar vehículo si viene de la página de detail
    vehiculo_inicial = request.GET.get('vehiculo', '')
    
    if request.method == 'POST':
        form = VentaVehiculoForm(request.POST)
        if form.is_valid():
            venta = form.save(commit=False)
            venta.created_by = request.user
            
            # Calcular coste total del vehículo
            vehiculo = venta.vehiculo
            venta.coste_total = vehiculo.coste_total
            
            # Calcular margen porcentaje
            if venta.coste_total > 0:
                venta.margen_porcentaje = (
                    (venta.precio_venta - venta.coste_total) / venta.coste_total * 100
                )
            
            venta.save()
            
            # Cambiar estado del vehículo a VENDIDO
            vehiculo.estado = 'VENDIDO'
            vehiculo.save()
            
            # Crear garantía automáticamente
            GarantiaVehiculo.objects.create(
                venta=venta,
                tipo_cliente=venta.tipo_cliente,
                fecha_inicio=venta.fecha_venta,
            )
            
            messages.success(
                request, 
                f'Venta registrada correctamente. Beneficio: €{venta.beneficio:.2f}'
            )
            return redirect('sales:detail', pk=venta.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        initial_data = {}
        if vehiculo_inicial:
            initial_data['vehiculo'] = vehiculo_inicial
        form = VentaVehiculoForm(initial=initial_data)
    
    context = {
        'form': form,
        'action': 'crear',
    }
    return render(request, 'sales/form.html', context)


@login_required
def venta_delete(request, pk):
    """Eliminar una venta (confirmación)."""
    venta = get_object_or_404(VentaVehiculo, pk=pk)
    
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para eliminar ventas.')
        return redirect('sales:list')
    
    if request.method == 'POST':
        # Restaurar estado del vehículo
        vehiculo = venta.vehiculo
        vehiculo.estado = 'ACONDICIONADO'
        vehiculo.save()
        
        venta.delete()
        messages.success(
            request, 
            f'Venta eliminada correctamente. Vehículo restaurado a ACONDICIONADO.'
        )
        return redirect('sales:list')
    
    context = {
        'venta': venta,
    }
    return render(request, 'sales/delete.html', context)


@login_required
def venta_generar_contrato(request, pk):
    """Generar contrato de compraventa en PDF."""
    venta = get_object_or_404(VentaVehiculo, pk=pk)
    
    try:
        from .services import generar_contrato_compraventa
        generar_contrato_compraventa(venta)
        messages.success(request, 'Contrato generado correctamente.')
    except Exception as e:
        messages.error(request, f'Error al generar el contrato: {str(e)}')
    
    return redirect('sales:detail', pk=pk)


@login_required
def venta_generar_mandato(request, pk):
    """Generar mandato de gestoría en PDF."""
    venta = get_object_or_404(VentaVehiculo, pk=pk)
    
    try:
        from .services import generar_mandato_gestoria
        generar_mandato_gestoria(venta)
        messages.success(request, 'Mandato generado correctamente.')
    except Exception as e:
        messages.error(request, f'Error al generar el mandato: {str(e)}')
    
    return redirect('sales:detail', pk=pk)
