from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q
import logging
from decimal import Decimal
from apps.bank.models import BancoMovimiento
from .models import Vehiculo, ImagenVehiculo
from .forms import (
    VehiculoForm, VehiculoBusquedaForm, ImagenVehiculoFormSet,
)

logger = logging.getLogger(__name__)


def _regenerar_asiento_compra(vehiculo, user):
    """Anula el asiento de compra con contrapartida y crea el nuevo.

    Se usa cuando cambian los importes: el asiento anterior no se borra (Ley
    Antifraude), se contrarresta y queda ANULADO; después se genera y postea el
    nuevo asiento con el coste corregido y su movimiento bancario.
    """
    from datetime import date

    from apps.accounting.models import AsientoContable, MovimientoContable
    from apps.accounting.views import generar_numero_asiento

    with transaction.atomic():
        viejo = vehiculo.asiento_contable
        if viejo:
            BancoMovimiento.objects.filter(asiento_asociado=viejo).delete()
            reversion = AsientoContable.objects.create(
                numero=generar_numero_asiento(),
                fecha=date.today(),
                concepto=f'ANULACIÓN: {viejo.concepto}',
                estado='BORRADOR',
                tipo_documento='AnulacionVehiculo',
                documento_id=viejo.documento_id,
                created_by=user,
            )
            for movimiento in viejo.movimientos.all():
                MovimientoContable.objects.create(
                    asiento=reversion,
                    cuenta=movimiento.cuenta,
                    debe=movimiento.haber,
                    haber=movimiento.debe,
                    descripcion=f'Reversión: {movimiento.descripcion}',
                )
            viejo.estado = 'ANULADO'
            viejo.save(update_fields=['estado'])
            vehiculo.asiento_contable = None
            vehiculo.save(update_fields=['asiento_contable'])

        BancoMovimiento.objects.filter(vehiculo_asociado=vehiculo).delete()
        asiento = vehiculo.crear_asiento_contable()
        vehiculo.registrar_movimiento_banco(asiento=asiento)
        return asiento


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
    """Crear un vehículo con todos sus datos (técnicos, compra y comerciales)."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para crear vehículos.')
        return redirect('vehicles:list')

    if request.method == 'POST':
        form = VehiculoForm(request.POST, request.FILES)
        mostrar_imagenes = request.POST.get('estado') == 'EN_VENTA'
        procesar_imagenes = mostrar_imagenes and 'imagenes-TOTAL_FORMS' in request.POST

        if procesar_imagenes:
            imagenes_formset = ImagenVehiculoFormSet(
                request.POST, request.FILES, prefix='imagenes'
            )
        else:
            imagenes_formset = ImagenVehiculoFormSet(prefix='imagenes')

        if form.is_valid() and (not procesar_imagenes or imagenes_formset.is_valid()):
            vehiculo = form.save(commit=False)
            vehiculo.created_by = request.user
            vehiculo.save()
            if procesar_imagenes:
                imagenes_formset.instance = vehiculo
                imagenes_formset.save()
            elif request.FILES.get('imagen_principal') or any(
                f'imagenes-{i}-imagen' in request.FILES for i in range(0, 20)
            ):
                messages.error(
                    request,
                    'Las imágenes solo se pueden subir cuando el vehículo está '
                    'en estado EN_VENTA.',
                )
                return redirect('vehicles:detail', pk=vehiculo.pk)

            try:
                asiento = vehiculo.crear_asiento_contable()
                vehiculo.registrar_movimiento_banco(asiento=asiento)
                messages.success(
                    request,
                    f'Vehículo creado. Asiento #{asiento.numero} registrado.',
                )
            except Exception as e:
                messages.warning(
                    request,
                    f'Vehículo creado, pero no se pudo crear el asiento contable: {e}',
                )
            return redirect('vehicles:detail', pk=vehiculo.pk)
        messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = VehiculoForm()
        procesar_imagenes = False
        mostrar_imagenes = False
        imagenes_formset = ImagenVehiculoFormSet(prefix='imagenes')

    return render(request, 'vehicles/form.html', {
        'form': form,
        'imagenes_formset': imagenes_formset,
        'mostrar_imagenes': mostrar_imagenes,
        'action': 'crear',
    })


@login_required
def vehiculo_update(request, pk):
    """Actualizar un vehículo. Si cambian los importes, rehace el asiento."""
    vehiculo = get_object_or_404(Vehiculo, pk=pk)

    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para editar vehículos.')
        return redirect('vehicles:detail', pk=pk)

    if request.method == 'POST':
        # Valor previo de la portada: si el vehículo sale de EN_VENTA hay que
        # restaurarlo, porque validar el formulario ya vuelca el archivo nuevo
        # sobre la instancia del modelo.
        imagen_principal_previa = vehiculo.imagen_principal
        economicos_previos = {
            campo: getattr(vehiculo, campo)
            for campo in VehiculoForm.CAMPOS_ECONOMICOS
        }
        form = VehiculoForm(request.POST, request.FILES, instance=vehiculo)
        mostrar_imagenes = request.POST.get('estado') == 'EN_VENTA'
        procesar_imagenes = mostrar_imagenes and 'imagenes-TOTAL_FORMS' in request.POST

        if procesar_imagenes:
            imagenes_formset = ImagenVehiculoFormSet(
                request.POST, request.FILES, instance=vehiculo, prefix='imagenes'
            )
        else:
            imagenes_formset = ImagenVehiculoFormSet(
                instance=vehiculo, prefix='imagenes'
            )

        if form.is_valid() and (not procesar_imagenes or imagenes_formset.is_valid()):
            nuevo_estado = form.cleaned_data.get('estado')
            # Las fotos NO se borran al salir de EN_VENTA: se conservan ocultas.
            tenia_fotos = bool(vehiculo.imagen_principal) or vehiculo.imagenes.exists()
            if nuevo_estado != 'EN_VENTA':
                form.cleaned_data.pop('imagen_principal', None)
                form.instance.imagen_principal = imagen_principal_previa
                if tenia_fotos:
                    messages.info(
                        request,
                        'El vehículo ya no está EN VENTA: sus fotos se conservan '
                        'ocultas y reaparecerán si vuelve a ese estado.',
                    )

            vehiculo = form.save()
            if procesar_imagenes:
                imagenes_formset.instance = vehiculo
                imagenes_formset.save()
            elif request.FILES.get('imagen_principal') or any(
                f'imagenes-{i}-imagen' in request.FILES for i in range(0, 20)
            ):
                messages.error(
                    request,
                    'Las imágenes solo se pueden subir cuando el vehículo está '
                    'en estado EN_VENTA.',
                )

            economicos_nuevos = {
                campo: getattr(vehiculo, campo)
                for campo in VehiculoForm.CAMPOS_ECONOMICOS
            }
            if economicos_previos == economicos_nuevos:
                messages.success(
                    request,
                    'Vehículo actualizado. Los importes de compra no han '
                    'cambiado: el asiento se mantiene.',
                )
            else:
                try:
                    asiento = _regenerar_asiento_compra(vehiculo, request.user)
                    messages.success(
                        request,
                        f'Vehículo actualizado. Asiento #{asiento.numero} '
                        f'regenerado con los nuevos importes (el anterior queda '
                        f'anulado con su contrapartida).',
                    )
                except Exception as e:
                    messages.warning(
                        request,
                        f'Vehículo actualizado, pero no se pudo regenerar el '
                        f'asiento: {e}',
                    )
            return redirect('vehicles:detail', pk=vehiculo.pk)
        messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = VehiculoForm(instance=vehiculo)
        mostrar_imagenes = vehiculo.estado == 'EN_VENTA'
        imagenes_formset = ImagenVehiculoFormSet(instance=vehiculo, prefix='imagenes')

    return render(request, 'vehicles/form.html', {
        'form': form,
        'vehiculo': vehiculo,
        'imagenes_formset': imagenes_formset,
        'mostrar_imagenes': mostrar_imagenes,
        'action': 'editar',
    })


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


@login_required
def vehiculo_costes_report(request, bastidor):
    """REQ-01: Trazabilidad por vehículo (Cost-Pooling).

    Consolida en tiempo real todos los costes asociados a un NÚMERO_BASTIDOR:
    precio subasta + tasas + grúa + repuestos internos consumidos (OTs).
    """
    vehiculo = get_object_or_404(Vehiculo, bastidor__iexact=bastidor)

    from apps.workshop.models import OrdenTrabajo, MaterialUsado
    from apps.sales.models import CostoAcondicionamiento

    ots = OrdenTrabajo.objects.filter(vehiculo=vehiculo)
    materiales_usados = MaterialUsado.objects.filter(orden_trabajo__vehiculo=vehiculo)
    costos_acondicionamiento = CostoAcondicionamiento.objects.filter(vehiculo=vehiculo)

    repuestos_internos = sum((mu.subtotal for mu in materiales_usados), Decimal('0'))
    acondicionamiento = sum((c.total for c in costos_acondicionamiento), Decimal('0'))

    # Costes de adquisición
    precio_subasta = vehiculo.precio_subasta
    tasas_subasta = vehiculo.tasas_sala
    grua = vehiculo.logistica_grua
    coste_inicial = vehiculo.coste_inicial
    coste_reparacion = vehiculo.coste_reparacion

    total_coste = coste_inicial + coste_reparacion + acondicionamiento

    context = {
        'vehiculo': vehiculo,
        'ots': ots,
        'materiales_usados': materiales_usados,
        'costos_acondicionamiento': costos_acondicionamiento,
        'desglose': {
            'precio_subasta': precio_subasta,
            'tasas_subasta': tasas_subasta,
            'grua': grua,
            'coste_inicial': coste_inicial,
            'coste_reparacion': coste_reparacion,
            'repuestos_internos': repuestos_internos,
            'acondicionamiento': acondicionamiento,
        },
        'total_coste': total_coste,
    }
    return render(request, 'vehicles/costes_report.html', context)
