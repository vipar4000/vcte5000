from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import Vehiculo, ImagenVehiculo
from .forms import VehiculoForm, VehiculoBusquedaForm, ImagenVehiculoFormSet


@login_required
def vehiculo_list(request):
    """Lista de vehículos con filtros."""
    vehiculos = Vehiculo.objects.all()
    
    # Aplicar filtros
    busqueda = request.GET.get('busqueda', '')
    estado = request.GET.get('estado', '')
    marca = request.GET.get('marca', '')
    
    if busqueda:
        vehiculos = vehiculos.filter(
            Q(matricula__icontains=busqueda) |
            Q(bastidor__icontains=busqueda) |
            Q(marca__icontains=busqueda) |
            Q(modelo__icontains=busqueda)
        )
    
    if estado:
        vehiculos = vehiculos.filter(estado=estado)
    
    if marca:
        vehiculos = vehiculos.filter(marca__icontains=marca)
    
    # Estadísticas
    stats = {
        'total': Vehiculo.objects.count(),
        'adquiridos': Vehiculo.objects.filter(estado='ADQUIRIDO').count(),
        'en_taller': Vehiculo.objects.filter(estado='TALLER').count(),
        'acondicionados': Vehiculo.objects.filter(estado='ACONDICIONADO').count(),
        'en_venta': Vehiculo.objects.filter(estado='EN_VENTA').count(),
        'vendidos': Vehiculo.objects.filter(estado='VENDIDO').count(),
    }
    
    context = {
        'vehiculos': vehiculos[:50],
        'stats': stats,
        'busqueda': busqueda,
        'estado_seleccionado': estado,
        'marca_seleccionada': marca,
    }
    return render(request, 'vehicles/list.html', context)


@login_required
def vehiculo_detail(request, pk):
    """Detalle de un vehículo."""
    vehiculo = get_object_or_404(Vehiculo, pk=pk)
    imagenes = vehiculo.imagenes.all()
    
    context = {
        'vehiculo': vehiculo,
        'imagenes': imagenes,
        'coste_reparacion': vehiculo.coste_reparacion,
        'coste_total': vehiculo.coste_total,
    }
    return render(request, 'vehicles/detail.html', context)


@login_required
def vehiculo_create(request):
    """Crear un nuevo vehículo."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para crear vehículos.')
        return redirect('vehicles:list')
    
    if request.method == 'POST':
        form = VehiculoForm(request.POST, request.FILES)
        estado_es_venta = form.data.get('estado') == 'EN_VENTA'
        imagenes_formset = ImagenVehiculoFormSet(
            request.POST, request.FILES, prefix='imagenes'
        ) if estado_es_venta else None
        if form.is_valid() and (imagenes_formset is None or imagenes_formset.is_valid()):
            vehiculo = form.save(commit=False)
            vehiculo.created_by = request.user
            vehiculo.save()
            if estado_es_venta:
                imagenes_formset.instance = vehiculo
                imagenes_formset.save()
            elif any(request.FILES.getlist('imagenes-' + k) for k in ('imagen',)) or request.FILES.get('imagen_principal'):
                messages.error(
                    request,
                    'Las imágenes solo se pueden subir cuando el vehículo está en estado EN_VENTA.'
                )
                return redirect('vehicles:detail', pk=vehiculo.pk)
            messages.success(
                request, 
                f'Vehículo {vehiculo.marca} {vehiculo.modelo} creado correctamente.'
            )
            return redirect('vehicles:detail', pk=vehiculo.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = VehiculoForm()
        imagenes_formset = None
    
    context = {
        'form': form,
        'imagenes_formset': imagenes_formset,
        'action': 'crear',
    }
    return render(request, 'vehicles/form.html', context)


@login_required
def vehiculo_update(request, pk):
    """Actualizar un vehículo."""
    vehiculo = get_object_or_404(Vehiculo, pk=pk)
    
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para editar vehículos.')
        return redirect('vehicles:detail', pk=pk)
    
    if request.method == 'POST':
        form = VehiculoForm(request.POST, request.FILES, instance=vehiculo)
        estado_es_venta = form.data.get('estado') == 'EN_VENTA'
        imagenes_formset = ImagenVehiculoFormSet(
            request.POST, request.FILES, instance=vehiculo, prefix='imagenes'
        ) if estado_es_venta else None
        if form.is_valid() and (imagenes_formset is None or imagenes_formset.is_valid()):
            nuevo_estado = form.cleaned_data.get('estado')
            # Si el vehículo deja de estar EN_VENTA, eliminar sus imágenes.
            if nuevo_estado != 'EN_VENTA':
                if vehiculo.imagen_principal:
                    vehiculo.imagen_principal.delete(save=False)
                vehiculo.imagenes.all().delete()
            vehiculo = form.save()
            if estado_es_venta:
                imagenes_formset.instance = vehiculo
                imagenes_formset.save()
            elif request.FILES.get('imagen_principal') or any(
                f'imagenes-{i}-imagen' in request.FILES for i in range(0, 20)
            ):
                messages.error(
                    request,
                    'Las imágenes solo se pueden subir cuando el vehículo está en estado EN_VENTA.'
                )
            messages.success(
                request, 
                f'Vehículo {vehiculo.marca} {vehiculo.modelo} actualizado correctamente.'
            )
            return redirect('vehicles:detail', pk=vehiculo.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = VehiculoForm(instance=vehiculo)
        imagenes_formset = ImagenVehiculoFormSet(instance=vehiculo, prefix='imagenes') if vehiculo.estado == 'EN_VENTA' else None
    
    context = {
        'form': form,
        'vehiculo': vehiculo,
        'imagenes_formset': imagenes_formset,
        'action': 'editar',
    }
    return render(request, 'vehicles/form.html', context)


@login_required
def vehiculo_delete(request, pk):
    """Eliminar un vehículo (confirmación)."""
    vehiculo = get_object_or_404(Vehiculo, pk=pk)
    
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para eliminar vehículos.')
        return redirect('vehicles:detail', pk=pk)
    
    if not request.user.puede_eliminar:
        messages.error(request, 'No tiene permisos para eliminar registros.')
        return redirect('vehicles:detail', pk=pk)
    
    if vehiculo.estado == 'VENDIDO':
        messages.error(request, 'No se puede eliminar un vehículo vendido.')
        return redirect('vehicles:detail', pk=pk)
    
    if request.method == 'POST':
        marca = vehiculo.marca
        modelo = vehiculo.modelo
        vehiculo.delete()
        messages.success(
            request, 
            f'Vehículo {marca} {modelo} eliminado correctamente.'
        )
        return redirect('vehicles:list')
    
    context = {
        'vehiculo': vehiculo,
    }
    return render(request, 'vehicles/delete.html', context)


@login_required
def vehiculo_cambiar_estado(request, pk):
    """Cambiar estado de un vehículo."""
    vehiculo = get_object_or_404(Vehiculo, pk=pk)
    
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para cambiar el estado.')
        return redirect('vehicles:detail', pk=pk)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        estados_validos = [e[0] for e in Vehiculo.ESTADOS]
        
        if nuevo_estado in estados_validos:
            vehiculo.estado = nuevo_estado
            vehiculo.save()
            messages.success(
                request, 
                f'Estado cambiado a {vehiculo.get_estado_display()}.'
            )
        else:
            messages.error(request, 'Estado no válido.')
    
    return redirect('vehicles:detail', pk=pk)
