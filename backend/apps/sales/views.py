from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Sum
from decimal import Decimal
from .models import VentaVehiculo, FacturaVenta, DetalleRebu, CostoAcondicionamiento
from .forms import VentaVehiculoForm, CostoAcondicionamientoForm
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
            
            # Crear asiento contable automáticamente
            try:
                venta.crear_asiento_contable()
            except Exception as e:
                messages.warning(
                    request,
                    f'Venta registrada, pero no se pudo crear el asiento contable: {str(e)}'
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
    
    if not request.user.puede_eliminar:
        messages.error(request, 'No tiene permisos para eliminar registros.')
        return redirect('sales:list')
    
    if request.method == 'POST':
        # Restaurar estado del vehículo
        vehiculo = venta.vehiculo
        vehiculo.estado = 'ACONDICIONADO'
        vehiculo.save()
        
        # Borrar asiento contable asociado
        if venta.asiento_contable:
            venta.asiento_contable.delete()
        
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


# =============================================================================
# VISTAS DE FACTURACIÓN REBU
# =============================================================================

@login_required
def factura_list(request):
    """Lista de facturas REBU."""
    facturas = FacturaVenta.objects.select_related('venta', 'venta__vehiculo').all()
    
    busqueda = request.GET.get('busqueda', '')
    tipo = request.GET.get('tipo', '')
    
    if busqueda:
        facturas = facturas.filter(
            Q(codigo_factura__icontains=busqueda) |
            Q(cliente_nombre__icontains=busqueda) |
            Q(cliente_nif__icontains=busqueda)
        )
    
    if tipo:
        facturas = facturas.filter(tipo_factura=tipo)
    
    context = {
        'facturas': facturas[:50],
        'busqueda': busqueda,
        'tipo_seleccionado': tipo,
    }
    return render(request, 'sales/factura_list.html', context)


@login_required
def factura_detail(request, pk):
    """Detalle de una factura."""
    factura = get_object_or_404(
        FacturaVenta.objects.select_related('venta', 'venta__vehiculo'),
        pk=pk
    )
    
    context = {
        'factura': factura,
    }
    return render(request, 'sales/factura_detail.html', context)


@login_required
def factura_generar(request, pk):
    """Generar factura para una venta existente."""
    venta = get_object_or_404(VentaVehiculo, pk=pk)
    
    if FacturaVenta.objects.filter(venta=venta).exists():
        messages.warning(request, 'Esta venta ya tiene una factura generada.')
        return redirect('sales:factura_list')
    
    try:
        from .services import crear_factura_venta, generar_pdf_factura
        factura = crear_factura_venta(venta, request.user)
        generar_pdf_factura(factura)
        messages.success(
            request,
            f'Factura {factura.codigo_factura} generada correctamente.'
        )
        return redirect('sales:factura_detail', pk=factura.pk)
    except Exception as e:
        messages.error(request, f'Error al generar la factura: {str(e)}')
        return redirect('sales:detail', pk=pk)


@login_required
def factura_generar_pdf(request, pk):
    """Regenerar el PDF de una factura existente."""
    factura = get_object_or_404(FacturaVenta, pk=pk)
    
    try:
        from .services import generar_pdf_factura
        generar_pdf_factura(factura)
        messages.success(request, f'PDF de {factura.codigo_factura} generado correctamente.')
    except Exception as e:
        messages.error(request, f'Error al generar el PDF: {str(e)}')
    
    return redirect('sales:factura_detail', pk=pk)


@login_required
def factura_rectificativa(request, pk):
    """Crear factura rectificativa (R1 o R4) para una factura."""
    factura_original = get_object_or_404(FacturaVenta, pk=pk)
    
    if request.method == 'POST':
        tipo = request.POST.get('tipo_rectificacion', 'R1')
        motivo = request.POST.get('motivo', '')
        
        if tipo not in ('R1', 'R4'):
            messages.error(request, 'Tipo de rectificación no válido.')
            return redirect('sales:factura_detail', pk=pk)
        
        try:
            from .services import crear_factura_rectificativa, generar_pdf_factura_rectificativa
            factura_rect = crear_factura_rectificativa(
                factura_original, tipo, motivo, request.user
            )
            generar_pdf_factura_rectificativa(factura_rect)
            messages.success(
                request,
                f'Factura rectificativa {factura_rect.codigo_factura} generada.'
            )
            return redirect('sales:factura_detail', pk=factura_rect.pk)
        except Exception as e:
            messages.error(request, f'Error al crear la rectificativa: {str(e)}')
    
    context = {
        'factura_original': factura_original,
    }
    return render(request, 'sales/factura_rectificativa_form.html', context)


# =============================================================================
# VISTAS DE COSTOS DE ACONDICIONAMIENTO
# =============================================================================

@login_required
def costo_acondicionamiento_list(request, vehiculo_pk):
    """Lista de costos de acondicionamiento de un vehículo."""
    vehiculo = get_object_or_404(Vehiculo, pk=vehiculo_pk)
    costos = CostoAcondicionamiento.objects.filter(vehiculo=vehiculo)
    
    total_costos = sum(c.total for c in costos)
    
    context = {
        'vehiculo': vehiculo,
        'costos': costos,
        'total_costos': total_costos,
        'bloqueado': vehiculo.estado == 'VENDIDO',
    }
    return render(request, 'sales/costo_acondicionamiento_list.html', context)


@login_required
def costo_acondicionamiento_create(request, vehiculo_pk):
    """Añadir un costo de acondicionamiento."""
    vehiculo = get_object_or_404(Vehiculo, pk=vehiculo_pk)
    
    if vehiculo.estado == 'VENDIDO':
        messages.error(
            request,
            'No se pueden añadir costos a un vehículo ya vendido.'
        )
        return redirect('sales:costos_list', vehiculo_pk=vehiculo_pk)
    
    if request.method == 'POST':
        form = CostoAcondicionamientoForm(request.POST)
        if form.is_valid():
            costo = form.save(commit=False)
            costo.vehiculo = vehiculo
            costo.created_by = request.user
            
            try:
                costo.crear_asiento_contable()
            except Exception as e:
                messages.warning(
                    request,
                    f'Costo registrado, pero no se pudo crear asiento: {str(e)}'
                )
            
            costo.save()
            
            messages.success(
                request,
                f'Costo de acondicionamiento registrado: €{costo.total}'
            )
            return redirect('sales:costos_list', vehiculo_pk=vehiculo_pk)
    else:
        form = CostoAcondicionamientoForm()
    
    context = {
        'form': form,
        'vehiculo': vehiculo,
    }
    return render(request, 'sales/costo_acondicionamiento_form.html', context)
