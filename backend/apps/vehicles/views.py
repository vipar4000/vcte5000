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
    VehiculoComercialForm,
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

    # Un vehículo ya vendido no puede re-postear su compra: volvería a meter
    # el coste en la 310 (la venta ya lo dio de baja).
    if vehiculo.ventas.filter(anulada=False).exists():
        return vehiculo.asiento_contable

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


def _error_saldo_compra_vehiculo(form):
    """Comprueba que la cuenta de pago tenga saldo en la fecha de adquisición.

    Devuelve el mensaje de error o None. La caja (570) no genera movimiento
    bancario, así que no se valida.
    """
    from django.core.exceptions import ValidationError

    from apps.bank.services import cuenta_banco_para_pago, validar_saldo_egreso

    datos = form.cleaned_data
    forma_pago = datos.get('forma_pago')
    if forma_pago is not None and forma_pago.codigo.startswith('570'):
        return None

    cuenta = cuenta_banco_para_pago(forma_pago)
    if cuenta is None:
        return None

    total = (
        (datos.get('precio_subasta') or 0)
        + (datos.get('tasas_sala') or 0)
        + (datos.get('logistica_grua') or 0)
        + (datos.get('tipo_iva') or 0)
    )
    try:
        validar_saldo_egreso(cuenta, datos.get('fecha_adquisicion'), total)
    except ValidationError as error:
        return error.messages[0]
    return None


@login_required
def vehiculo_create(request):
    """Crear un vehículo (hoja técnica y de compra)."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para crear vehículos.')
        return redirect('vehicles:list')

    if request.method == 'POST':
        form = VehiculoForm(request.POST, request.FILES)
        if form.is_valid():
            error_saldo = _error_saldo_compra_vehiculo(form)
            if error_saldo:
                messages.error(request, error_saldo)
                return render(request, 'vehicles/form.html', {
                    'form': form, 'action': 'crear',
                })

            vehiculo = form.save(commit=False)
            vehiculo.created_by = request.user
            vehiculo.save()

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
            messages.info(
                request,
                'El estado, el precio de venta, la descripción y las fotos se '
                'editan en la pestaña 📢 Publicar.',
            )
            return redirect('vehicles:detail', pk=vehiculo.pk)
        messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = VehiculoForm()

    return render(request, 'vehicles/form.html', {
        'form': form,
        'action': 'crear',
    })


@login_required
def vehiculo_publicar(request, pk):
    """Publicar el vehículo: estado, precio de venta, descripción y fotos.

    Es una acción separada de la edición técnica a propósito: aquí no se tocan
    los costes de compra ni la contabilidad, así que el equipo de ventas puede
    trabajar sin ver márgenes y sin riesgo de descuadrar el asiento.
    """
    if not (request.user.is_admin or request.user.is_vendedor):
        messages.error(request, 'No tiene permisos para publicar vehículos.')
        return redirect('vehicles:detail', pk=pk)

    vehiculo = get_object_or_404(Vehiculo, pk=pk)

    if request.method == 'POST':
        form = VehiculoComercialForm(request.POST, request.FILES, instance=vehiculo)
        procesar_imagenes = 'imagenes-TOTAL_FORMS' in request.POST
        if procesar_imagenes:
            imagenes_formset = ImagenVehiculoFormSet(
                request.POST, request.FILES, instance=vehiculo, prefix='imagenes'
            )
        else:
            imagenes_formset = ImagenVehiculoFormSet(
                instance=vehiculo, prefix='imagenes'
            )

        if form.is_valid() and (
            not procesar_imagenes or imagenes_formset.is_valid()
        ):
            try:
                with transaction.atomic():
                    form.save()
                    if procesar_imagenes:
                        imagenes_formset.save()
            except Exception as error:
                # Nunca devolver un 500 por aquí: se informa del motivo real y,
                # si algo se guardó a medias, la transacción lo revierte.
                logger.exception(
                    'Error al guardar los datos comerciales del vehículo %s',
                    vehiculo.pk,
                )
                messages.error(
                    request,
                    f'No se pudieron guardar los datos comerciales: {error}. '
                    f'No se cambió nada.',
                )
            else:
                messages.success(request, 'Datos comerciales y fotos actualizados.')
                return redirect('vehicles:detail', pk=vehiculo.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = VehiculoComercialForm(instance=vehiculo)
        imagenes_formset = ImagenVehiculoFormSet(instance=vehiculo, prefix='imagenes')

    return render(request, 'vehicles/publicar.html', {
        'form': form,
        'vehiculo': vehiculo,
        'imagenes_formset': imagenes_formset,
    })

@login_required
def vehiculo_update(request, pk):
    """Editar la hoja técnica y de compra. Regenera el asiento al guardar."""
    vehiculo = get_object_or_404(Vehiculo, pk=pk)

    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para editar vehículos.')
        return redirect('vehicles:detail', pk=pk)

    if request.method == 'POST':
        form = VehiculoForm(request.POST, request.FILES, instance=vehiculo)
        if form.is_valid():
            error_saldo = _error_saldo_compra_vehiculo(form)
            if error_saldo:
                messages.error(request, error_saldo)
                return render(request, 'vehicles/form.html', {
                    'form': form, 'vehiculo': vehiculo, 'action': 'editar',
                })

            vehiculo = form.save()
            try:
                asiento = _regenerar_asiento_compra(vehiculo, request.user)
                messages.success(
                    request,
                    f'Vehículo actualizado. Asiento #{asiento.numero} regenerado '
                    f'(el anterior queda anulado con su contrapartida).',
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

    return render(request, 'vehicles/form.html', {
        'form': form,
        'vehiculo': vehiculo,
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

    from apps.core.protecciones import motivo_no_borrar_vehiculo

    motivo = motivo_no_borrar_vehiculo(vehiculo)
    if motivo:
        messages.error(request, motivo)
        return redirect('vehicles:detail', pk=pk)
    
    if request.method == 'POST':
        marca = vehiculo.marca
        modelo = vehiculo.modelo
        from django.db.models.deletion import ProtectedError

        try:
            vehiculo.delete()
        except ProtectedError:
            messages.error(
                request,
                'No se puede eliminar este vehículo: tiene operaciones '
                'asociadas (ventas, OT, asientos o pagos). Anúlelas primero.',
            )
            return redirect('vehicles:detail', pk=pk)
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
