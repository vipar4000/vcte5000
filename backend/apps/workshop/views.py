from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum, Count

from apps.accounts.models import User
from apps.vehicles.models import Vehiculo

from .models import OrdenTrabajo, Material, MaterialUsado
from .forms import OrdenTrabajoForm, MaterialForm, MaterialUsadoFormSet


@login_required
def orden_trabajo_list(request):
    """Lista de órdenes de trabajo con filtros."""
    ots = OrdenTrabajo.objects.select_related('vehiculo', 'operario').all()
    
    # Filtros
    estado = request.GET.get('estado', '')
    operario_id = request.GET.get('operario', '')
    vehiculo_id = request.GET.get('vehiculo', '')
    busqueda = request.GET.get('busqueda', '')
    
    if estado:
        ots = ots.filter(estado=estado)
    
    if operario_id:
        ots = ots.filter(operario_id=operario_id)
    
    if vehiculo_id:
        ots = ots.filter(vehiculo_id=vehiculo_id)
    
    if busqueda:
        ots = ots.filter(
            Q(titulo__icontains=busqueda) |
            Q(descripcion__icontains=busqueda) |
            Q(vehiculo__matricula__icontains=busqueda) |
            Q(vehiculo__marca__icontains=busqueda)
        )
    
    # Estadísticas
    stats = {
        'total': OrdenTrabajo.objects.count(),
        'pendientes': OrdenTrabajo.objects.filter(estado='PENDIENTE').count(),
        'en_progreso': OrdenTrabajo.objects.filter(estado='EN_PROGRESO').count(),
        'completadas': OrdenTrabajo.objects.filter(estado='COMPLETADA').count(),
    }
    
    from apps.accounts.models import User
    operarios = User.objects.filter(rol='OPERARIO', is_active=True)
    
    context = {
        'ots': ots[:50],
        'stats': stats,
        'operarios': operarios,
        'estado_seleccionado': estado,
        'operario_seleccionado': operario_id,
    }
    return render(request, 'workshop/list.html', context)


@login_required
def orden_trabajo_detail(request, pk):
    """Detalle de una orden de trabajo."""
    ot = get_object_or_404(
        OrdenTrabajo.objects.select_related('vehiculo', 'operario'),
        pk=pk
    )
    materiales = ot.materiales_usados.select_related('material').all()
    
    context = {
        'ot': ot,
        'materiales': materiales,
        'coste_mano_obra': ot.coste_mano_obra,
        'coste_materiales': ot.coste_materiales,
        'coste_total': ot.coste_total,
    }
    return render(request, 'workshop/detail.html', context)


@login_required
def orden_trabajo_create(request):
    """Crear una orden de trabajo.

    Es la **misma vista** para los dos accesos del menú:
      - Taller -> + Nueva OT
      - Vehículos -> ficha -> + Nueva OT (con `?vehiculo=<pk>`)
    """
    if not request.user.is_admin and not request.user.is_operario:
        messages.error(request, 'No tiene permisos para crear órdenes de trabajo.')
        return redirect('workshop:list')

    # Vehículo precargado cuando se entra desde la ficha del coche
    vehiculo_id = request.GET.get('vehiculo') or request.POST.get('vehiculo')
    vehiculo_inicial = None
    if vehiculo_id:
        vehiculo_inicial = Vehiculo.objects.filter(pk=vehiculo_id).first()
        if vehiculo_inicial is not None and vehiculo_inicial.estado == 'VENDIDO':
            messages.warning(
                request,
                'Ese vehículo está vendido: no se pueden abrir órdenes de '
                'trabajo nuevas sobre él.',
            )
            vehiculo_inicial = None

    if request.method == 'POST':
        form = OrdenTrabajoForm(request.POST)
        # El navegador envía siempre el management form; si falta, se entiende
        # que la OT se crea sin materiales.
        procesar_materiales = 'materiales_usados-TOTAL_FORMS' in request.POST
        formset = (
            MaterialUsadoFormSet(request.POST)
            if procesar_materiales
            else MaterialUsadoFormSet()
        )

        if form.is_valid() and (not procesar_materiales or formset.is_valid()):
            with transaction.atomic():
                ot = form.save(commit=False)
                ot.created_by = request.user
                ot.save()

                if procesar_materiales:
                    formset.instance = ot
                    formset.save()

                # Si el vehículo estaba Adquirido, pasa a En Taller
                vehiculo = ot.vehiculo
                if vehiculo.estado == 'ADQUIRIDO':
                    vehiculo.estado = 'TALLER'
                    vehiculo.save(update_fields=['estado'])

            messages.success(
                request,
                f'Orden de trabajo OT-{ot.pk} creada correctamente.'
            )
            return redirect('workshop:detail_ot', pk=ot.pk)

        messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        initial_data = {}
        if vehiculo_inicial is not None:
            initial_data['vehiculo'] = vehiculo_inicial
        form = OrdenTrabajoForm(initial=initial_data)
        formset = MaterialUsadoFormSet()

    operarios = User.objects.filter(rol='OPERARIO', is_active=True)
    operarios_coste_hora = {}
    for operario in operarios:
        if operario.salario_base_mensual and operario.porcentaje_ss_patronal is not None:
            coste_mensual = operario.salario_base_mensual * (
                1 + operario.porcentaje_ss_patronal / Decimal('100')
            )
            operarios_coste_hora[operario.pk] = float(coste_mensual / 176)

    context = {
        'form': form,
        'formset': formset,
        'vehiculo_inicial': vehiculo_inicial,
        'operarios': operarios,
        'operarios_coste_hora_json': operarios_coste_hora,
        'action': 'crear',
    }
    return render(request, 'workshop/form.html', context)



@login_required
def orden_trabajo_update(request, pk):
    """Actualizar una orden de trabajo."""
    from apps.accounts.models import User
    from apps.vehicles.models import Vehiculo
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    
    if not request.user.is_admin and request.user != ot.operario:
        messages.error(request, 'No tiene permisos para editar esta OT.')
        return redirect('workshop:list')

    # Capturar el estado ANTES de is_valid(): full_clean muta la instancia
    # (construct_instance), así que leerlo después siempre daría el estado nuevo.
    estado_anterior = ot.estado

    if request.method == 'POST':
        form = OrdenTrabajoForm(request.POST, instance=ot)
        formset = MaterialUsadoFormSet(request.POST, instance=ot)

        if form.is_valid():
            ot = form.save()
            
            if formset.is_valid():
                formset.save()
            
            # Si se completó la OT desde este formulario, capitalizar reparación
            if ot.estado == 'COMPLETADA' and estado_anterior != 'COMPLETADA':
                try:
                    ot.crear_asiento_contable()
                except Exception as e:
                    messages.warning(
                        request,
                        f'OT completada, pero no se pudo capitalizar el coste: {str(e)}'
                    )
            
            # Si se completó la OT, verificar si el vehículo está listo
            if ot.estado == 'COMPLETADA':
                vehiculo = ot.vehiculo
                # Verificar si todas las OTs del vehículo están completadas
                ots_pendientes = OrdenTrabajo.objects.filter(
                    vehiculo=vehiculo
                ).exclude(estado='COMPLETADA').exclude(estado='CANCELADA')
                
                if not ots_pendientes.exists() and vehiculo.estado == 'TALLER':
                    messages.info(
                        request,
                        'Todas las OTs están completadas. Considere cambiar el estado del vehículo a ACONDICIONADO.'
                    )
            
            messages.success(
                request, 
                f'Orden de trabajo OT-{ot.pk} actualizada correctamente.'
            )
            return redirect('workshop:detail_ot', pk=ot.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = OrdenTrabajoForm(instance=ot)
        formset = MaterialUsadoFormSet(instance=ot)
    
    operarios = User.objects.filter(rol='OPERARIO', is_active=True)
    operarios_coste_hora = {}
    for op in operarios:
        if op.salario_base_mensual and op.porcentaje_ss_patronal is not None:
            from decimal import Decimal
            coste_mensual = op.salario_base_mensual * (1 + op.porcentaje_ss_patronal / Decimal('100'))
            operarios_coste_hora[op.pk] = float(coste_mensual / 176)
    
    context = {
        'form': form,
        'formset': formset,
        'ot': ot,
        'operarios_coste_hora_json': operarios_coste_hora,
        'action': 'editar',
    }
    return render(request, 'workshop/form.html', context)


@login_required
def orden_trabajo_delete(request, pk):
    """Eliminar una orden de trabajo (confirmación)."""
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para eliminar OTs.')
        return redirect('workshop:list')
    
    if not request.user.puede_eliminar:
        messages.error(request, 'No tiene permisos para eliminar registros.')
        return redirect('workshop:list')
    
    if request.method == 'POST':
        ot.delete()
        messages.success(
            request, 
            f'Orden de trabajo OT-{pk} eliminada correctamente.'
        )
        return redirect('workshop:list')
    
    context = {
        'ot': ot,
    }
    return render(request, 'workshop/delete.html', context)


@login_required
def orden_trabajo_cambiar_estado(request, pk):
    """Cambiar estado de una OT."""
    ot = get_object_or_404(OrdenTrabajo, pk=pk)
    
    if not request.user.is_admin and request.user != ot.operario:
        messages.error(request, 'No tiene permisos para cambiar el estado.')
        return redirect('workshop:list')
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        estados_validos = [e[0] for e in OrdenTrabajo.ESTADOS]
        
        if nuevo_estado in estados_validos:
            ot.estado = nuevo_estado
            
            # Si se completa, establecer fecha de fin
            if nuevo_estado == 'COMPLETADA' and not ot.fecha_fin:
                from django.utils import timezone
                ot.fecha_fin = timezone.now().date()
            
            ot.save()

            # Capitalizar coste de reparación en inventario (310)
            if nuevo_estado == 'COMPLETADA':
                try:
                    ot.crear_asiento_contable()
                except Exception as e:
                    messages.warning(
                        request,
                        f'OT completada, pero no se pudo capitalizar el coste: {str(e)}'
                    )

            messages.success(
                request, 
                f'Estado de OT-{ot.pk} cambiado a {ot.get_estado_display()}.'
            )
        else:
            messages.error(request, 'Estado no válido.')
    
    return redirect('workshop:detail_ot', pk=pk)
