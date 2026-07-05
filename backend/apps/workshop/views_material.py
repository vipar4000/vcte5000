from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F, ExpressionWrapper, DecimalField
from .models import Material, MaterialUsado, OrdenTrabajo
from .forms import MaterialForm


@login_required
def material_list(request):
    """Lista de materiales con gestión de stock."""
    materiales = Material.objects.all()
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    alerta = request.GET.get('alerta', '')
    
    if busqueda:
        materiales = materiales.filter(
            Q(nombre__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )
    
    if alerta == '1':
        materiales = materiales.filter(alerta_stock=True)
    
    # Estadísticas
    valor_total_expr = ExpressionWrapper(
        F('stock_actual') * F('precio_unitario'),
        output_field=DecimalField()
    )
    stats = {
        'total': Material.objects.count(),
        'con_alerta': Material.objects.filter(alerta_stock=True).count(),
        'valor_total': Material.objects.aggregate(
            total=Sum(valor_total_expr)
        )['total'] or 0,
    }
    
    # Materiales con alerta para el panel
    materiales_con_alerta = Material.objects.filter(alerta_stock=True)[:5]
    
    context = {
        'materiales': materiales,
        'stats': stats,
        'materiales_con_alerta': materiales_con_alerta,
        'busqueda': busqueda,
        'mostrar_alertas': alerta == '1',
    }
    return render(request, 'workshop/material_list.html', context)


@login_required
def material_detail(request, pk):
    """Detalle de un material con historial de uso."""
    material = get_object_or_404(Material, pk=pk)
    
    # Historial de uso del material
    usos = MaterialUsado.objects.filter(
        material=material
    ).select_related(
        'orden_trabajo', 'orden_trabajo__vehiculo', 'orden_trabajo__operario'
    ).order_by('-orden_trabajo__created_at')[:20]
    
    # Estadísticas de uso
    stats = {
        'total_usado': usos.aggregate(total=Sum('cantidad'))['total'] or 0,
        'veces_usado': usos.count(),
        'valor_stock': material.stock_actual * material.precio_unitario,
    }
    
    context = {
        'material': material,
        'usos': usos,
        'stats': stats,
    }
    return render(request, 'workshop/material_detail.html', context)


@login_required
def material_create(request):
    """Crear nuevo material."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para crear materiales.')
        return redirect('workshop:material_list')
    
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            material = form.save()
            messages.success(
                request, 
                f'Material "{material.nombre}" creado correctamente.'
            )
            return redirect('workshop:material_detail', pk=material.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = MaterialForm()
    
    context = {
        'form': form,
        'action': 'crear',
    }
    return render(request, 'workshop/material_form.html', context)


@login_required
def material_update(request, pk):
    """Actualizar un material."""
    material = get_object_or_404(Material, pk=pk)
    
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para editar materiales.')
        return redirect('workshop:material_detail', pk=pk)
    
    if request.method == 'POST':
        form = MaterialForm(request.POST, instance=material)
        if form.is_valid():
            material = form.save()
            messages.success(
                request, 
                f'Material "{material.nombre}" actualizado correctamente.'
            )
            return redirect('workshop:material_detail', pk=material.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = MaterialForm(instance=material)
    
    context = {
        'form': form,
        'material': material,
        'action': 'editar',
    }
    return render(request, 'workshop/material_form.html', context)


@login_required
def material_delete(request, pk):
    """Eliminar un material (confirmación)."""
    material = get_object_or_404(Material, pk=pk)
    
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para eliminar materiales.')
        return redirect('workshop:material_detail', pk=pk)
    
    if request.method == 'POST':
        nombre = material.nombre
        material.delete()
        messages.success(
            request, 
            f'Material "{nombre}" eliminado correctamente.'
        )
        return redirect('workshop:material_list')
    
    context = {
        'material': material,
    }
    return render(request, 'workshop/material_delete.html', context)


@login_required
def alertas_stock(request):
    """Panel de alertas de stock bajo."""
    materiales_con_alerta = Material.objects.filter(alerta_stock=True).order_by('stock_actual')
    
    # Calcular déficit y coste de reposición para cada material
    materiales_con_datos = []
    total_reposicion = 0
    
    for material in materiales_con_alerta:
        deficit = material.stock_minimo - material.stock_actual
        coste_reposicion = deficit * material.precio_unitario
        material.deficit = deficit
        material.coste_reposicion = coste_reposicion
        total_reposicion += coste_reposicion
        materiales_con_datos.append(material)
    
    context = {
        'materiales': materiales_con_datos,
        'total_alertas': materiales_con_alerta.count(),
        'total_reposicion': total_reposicion,
    }
    return render(request, 'workshop/alertas_stock.html', context)
