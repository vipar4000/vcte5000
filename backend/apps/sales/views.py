from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Sum
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.db.models.deletion import ProtectedError
from .models import VentaVehiculo, FacturaVenta, DetalleRebu, CostoAcondicionamiento
from .forms import VentaVehiculoForm, CostoAcondicionamientoForm
from apps.vehicles.models import Vehiculo
from apps.bank.models import Reserva
from apps.warranty.models import GarantiaVehiculo
from apps.core.formatting import format_euros


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
    
    from apps.bank.models import BancoMovimiento

    # Cobros en banco de este vehículo (la señal y el cobro de la venta)
    cobros = BancoMovimiento.objects.filter(
        vehiculo_asociado=venta.vehiculo, tipo='INGRESO'
    ).select_related('banco_cuenta').order_by('fecha')
    cobro_venta = cobros.filter(concepto__startswith='Cobro venta').first()
    total_banco = sum((c.importe for c in cobros), Decimal('0'))

    context = {
        'venta': venta,
        'beneficio': venta.beneficio,
        'precio_final': venta.precio_final_cliente,
        'cobros': cobros,
        'cobro_venta': cobro_venta,
        'total_banco': total_banco,
        'falta_cobro': (
            venta.metodo_pago != 'FINANCIADO' and cobro_venta is None
        ),
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
    # Reserva de la que viene la venta (se descuenta su señal)
    reserva_id = request.GET.get('reserva', '') or request.POST.get('reserva', '')
    reserva_inicial = None
    if reserva_id:
        reserva_inicial = Reserva.objects.filter(pk=reserva_id).first()
    
    if request.method == 'POST':
        form = VentaVehiculoForm(request.POST)
        if form.is_valid():
            vehiculo = form.cleaned_data.get('vehiculo')
            if vehiculo and vehiculo.ventas.filter(anulada=False).exists():
                form.add_error(
                    'vehiculo',
                    'Este vehículo ya tiene una venta activa. Anule esa venta '
                    'antes de registrar otra (la anulada queda en el histórico).',
                )
        if form.is_valid():
            try:
                # Todo o nada: venta, asiento y cobro en banco. Antes, si el
                # asiento o el movimiento fallaban, la venta quedaba guardada
                # sin ingreso en Banco y solo salía un aviso amarillo.
                with transaction.atomic():
                    venta = form.save(commit=False)
                    venta.created_by = request.user

                    vehiculo = venta.vehiculo
                    venta.coste_total = vehiculo.coste_total

                    if venta.coste_total > 0:
                        venta.margen_porcentaje = (
                            (venta.precio_venta - venta.coste_total)
                            / venta.coste_total * 100
                        )

                    venta.save()

                    vehiculo.estado = 'VENDIDO'
                    vehiculo.save()

                    GarantiaVehiculo.objects.create(
                        venta=venta,
                        tipo_cliente=venta.tipo_cliente,
                        fecha_inicio=venta.fecha_venta,
                    )

                    # Señal de la reserva: se descuenta y queda convertida
                    reserva = None
                    if reserva_inicial and reserva_inicial.estado == 'ACTIVA':
                        reserva = reserva_inicial
                    if reserva is None:
                        reserva = Reserva.objects.filter(
                            vehiculo=venta.vehiculo, estado='ACTIVA'
                        ).first()

                    anticipo = reserva.importe_reserva if reserva else 0

                    asiento = venta.crear_asiento_contable(anticipo=anticipo)
                    movimiento = venta.registrar_movimiento_banco(
                        asiento=asiento, anticipo=anticipo
                    )

                    if reserva:
                        reserva.estado = 'CONVERTIDA'
                        reserva.venta = venta
                        reserva.save(update_fields=['estado', 'venta'])
            except Exception as error:
                messages.error(
                    request,
                    f'No se pudo registrar la venta y no se guardó nada: {error}'
                )
                return render(request, 'sales/form.html', {
                    'form': form, 'action': 'crear',
                    'reserva_id': reserva_inicial.pk if reserva_inicial else '',
                    'reserva': reserva_inicial,
                })

            if reserva:
                messages.info(
                    request,
                    f'Se aplicó la señal de {format_euros(reserva.importe_reserva)} '
                    f'de la reserva de {reserva.cliente_nombre}: quedan '
                    f'{format_euros(venta.precio_venta - reserva.importe_reserva)} '
                    f'por cobrar.'
                )
            if movimiento is not None:
                messages.info(
                    request,
                    f'Cobro registrado en Banco: {format_euros(movimiento.importe)} '
                    f'en {movimiento.banco_cuenta.nombre}.'
                )
            elif venta.metodo_pago == 'FINANCIADO':
                messages.info(
                    request,
                    'Venta financiada: no entra dinero en el banco; el importe '
                    'queda pendiente en clientes (430).'
                )

            messages.success(
                request,
                f'Venta registrada correctamente. Beneficio: {format_euros(venta.beneficio)}'
            )
            return redirect('sales:detail', pk=venta.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        initial_data = {}
        if vehiculo_inicial:
            initial_data['vehiculo'] = vehiculo_inicial

        # Venta desde una reserva: se cargan los datos fiscales del comprador
        if reserva_inicial is not None:
            initial_data.update({
                'vehiculo': reserva_inicial.vehiculo,
                'tipo_cliente': reserva_inicial.tipo_cliente,
                'cliente_nombre': reserva_inicial.cliente_nombre,
                'cliente_dni': reserva_inicial.cliente_dni,
                'cliente_direccion': reserva_inicial.cliente_direccion,
                'cliente_poblacion': reserva_inicial.cliente_poblacion,
                'cliente_provincia': reserva_inicial.cliente_provincia,
                'cliente_cp': reserva_inicial.cliente_cp,
                'cliente_telefono': reserva_inicial.cliente_telefono,
                'cliente_email': reserva_inicial.cliente_email,
                'fecha_venta': timezone.localdate(),
            })
            if reserva_inicial.vehiculo.precio_venta:
                initial_data['precio_venta'] = reserva_inicial.vehiculo.precio_venta

        form = VentaVehiculoForm(initial=initial_data)
    
    context = {
        'form': form,
        'action': 'crear',
        'reserva_id': reserva_inicial.pk if reserva_inicial else '',
        'reserva': reserva_inicial,
    }
    return render(request, 'sales/form.html', context)


@login_required
def venta_anular(request, pk):
    """Anula una venta sin borrarla: contra-asiento, abono y rectificativa.

    Ley Antifraude y normativa de facturación: la venta y su factura se
    conservan; si había factura emitida se genera una rectificativa (R1).
    """
    venta = get_object_or_404(
        VentaVehiculo.objects.select_related('vehiculo'), pk=pk
    )

    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para anular ventas.')
        return redirect('sales:list')

    if venta.anulada:
        messages.info(request, 'Esta venta ya está anulada.')
        return redirect('sales:detail', pk=pk)

    factura = FacturaVenta.objects.filter(venta=venta).first()

    if request.method == 'POST':
        motivo = (request.POST.get('motivo') or '').strip()

        try:
            with transaction.atomic():
                if factura and factura.rectificativa_vigente is None:
                    from .services import (
                        crear_factura_rectificativa,
                        generar_pdf_factura_rectificativa,
                    )

                    rectificativa = crear_factura_rectificativa(
                        factura, 'R1',
                        motivo or 'Anulación de la venta',
                        request.user,
                    )
                    generar_pdf_factura_rectificativa(rectificativa)

                _anular_venta(venta, request.user, motivo)
        except Exception as error:
            messages.error(
                request, f'No se pudo anular la venta: {error}'
            )
            return redirect('sales:detail', pk=pk)

        if factura and factura.rectificativa_vigente is None:
            detalle_factura = '; se ha emitido la factura rectificativa.'
        elif factura:
            detalle_factura = (
                '; se reutiliza la rectificativa '
                f'{factura.rectificativa_vigente.codigo_factura} ya emitida.'
            )
        else:
            detalle_factura = '.'
        messages.success(
            request,
            f'Venta V-{pk} anulada. El asiento queda anulado con contrapartida, '
            f'el cobro compensado en banco y el vehículo disponible'
            + detalle_factura,
        )
        return redirect('sales:detail', pk=pk)

    return render(request, 'sales/anular.html', {
        'venta': venta,
        'factura': factura,
    })


@login_required
def venta_delete(request, pk):
    """Eliminar una venta deshaciendo su contabilidad y su cobro en banco.

    Ley Antifraude: el asiento no se borra, se anula con contrapartida.
    Si la venta tiene factura REBU, hay que confirmar expresamente su borrado
    (para pruebas); si no, se avisa sin lanzar un error 500.
    """
    venta = get_object_or_404(
        VentaVehiculo.objects.select_related('vehiculo'), pk=pk
    )

    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para eliminar ventas.')
        return redirect('sales:list')

    if not request.user.puede_eliminar:
        messages.error(request, 'No tiene permisos para eliminar registros.')
        return redirect('sales:list')

    from apps.bank.models import BancoMovimiento

    factura = FacturaVenta.objects.filter(venta=venta).first()

    # «Eliminar» queda solo para borradores sin movimientos. Con asiento,
    # cobro, factura o plazos hay que usar «Anular venta» (histórico y
    # rectificativa).
    movimientos = BancoMovimiento.objects.filter(
        vehiculo_asociado=venta.vehiculo, concepto__startswith='Cobro venta'
    ).exists()
    if venta.asiento_contable_id or factura or movimientos or venta.cobros.exists():
        messages.error(
            request,
            'Esta venta tiene asiento contable, cobro o factura: no se puede '
            'eliminar. Use «Anular venta» para conservar el histórico y '
            'generar la rectificativa.',
        )
        return redirect('sales:detail', pk=pk)

    if request.method == 'POST':
        if factura and not request.POST.get('eliminar_factura'):
            messages.error(
                request,
                f'La venta tiene la factura {factura.codigo_factura}. Para '
                f'eliminarla, marque «Eliminar también la factura» (solo para '
                f'correcciones); en producción lo correcto es emitir una '
                f'factura rectificativa.',
            )
            return redirect('sales:delete', pk=pk)

        try:
            with transaction.atomic():
                if factura:
                    factura.delete()
                _deshacer_venta(venta, request.user)
        except ProtectedError as error:
            messages.error(
                request,
                f'No se pudo eliminar la venta: {error}. Anule primero lo que '
                f'la referencia (factura, cobros o reserva).',
            )
            return redirect('sales:detail', pk=pk)
        except Exception as error:
            messages.error(request, f'No se pudo eliminar la venta: {error}')
            return redirect('sales:detail', pk=pk)

        messages.success(
            request,
            f'Venta V-{pk} eliminada. El vehículo vuelve a estar disponible y '
            f'su asiento queda anulado con contrapartida.',
        )
        return redirect('sales:list')

    context = {
        'venta': venta,
        'factura': factura,
    }
    return render(request, 'sales/delete.html', context)


def _revertir_venta(venta, user):
    """Anula el asiento con contrapartida y compensa el cobro en banco.

    Devuelve el asiento de anulación. No borra la venta: eso lo decide el
    llamador (anular vs eliminar borrador).
    """
    from datetime import date

    from apps.accounting.models import AsientoContable, MovimientoContable
    from apps.accounting.views import generar_numero_asiento
    from apps.bank.models import BancoMovimiento, Reserva
    from apps.bank.services import crear_movimiento_banco

    vehiculo = venta.vehiculo
    reversion = None

    asiento = venta.asiento_contable
    if asiento:
        reversion = AsientoContable.objects.create(
            numero=generar_numero_asiento(),
            fecha=date.today(),
            concepto=f'ANULACIÓN: {asiento.concepto}',
            estado='BORRADOR',
            tipo_documento='AnulacionVenta',
            documento_id=asiento.pk,
            created_by=user,
        )
        for movimiento in asiento.movimientos.all():
            MovimientoContable.objects.create(
                asiento=reversion,
                cuenta=movimiento.cuenta,
                debe=movimiento.haber,
                haber=movimiento.debe,
                descripcion=f'Reversión: {movimiento.descripcion}',
            )
        # Documental: el original queda ANULADO (deja de contar en los saldos)
        # y la contrapartida se guarda en BORRADOR como traza. Postearla
        # devolvería el coste a la 310 y descuadraría las existencias.
        asiento.estado = 'ANULADO'
        asiento.save(update_fields=['estado'])

        # Compensar el cobro. Los movimientos de banco no se borran (H7):
        # se registra el contrario, unificado por id para no duplicar.
        movimientos_venta = {
            m.pk: m
            for m in BancoMovimiento.objects.filter(asiento_asociado=asiento)
        }
        for movimiento in BancoMovimiento.objects.filter(
            vehiculo_asociado=vehiculo,
            tipo='INGRESO',
            concepto__startswith='Cobro venta',
        ):
            movimientos_venta.setdefault(movimiento.pk, movimiento)

        for movimiento in movimientos_venta.values():
            crear_movimiento_banco(
                banco_cuenta=movimiento.banco_cuenta,
                fecha=date.today(),
                concepto=f'Anulación venta: {movimiento.concepto}',
                tipo='EGRESO' if movimiento.tipo == 'INGRESO' else 'INGRESO',
                importe=movimiento.importe,
                asiento=reversion,
                notas='Compensación por anulación de venta',
            )

    # La reserva vuelve a estar activa (el dinero de la señal sigue en banco)
    Reserva.objects.filter(venta=venta, estado='CONVERTIDA').update(
        estado='ACTIVA', venta=None
    )

    # El vehículo vuelve a estar disponible
    vehiculo.estado = 'EN_VENTA' if vehiculo.precio_venta else 'ACONDICIONADO'
    vehiculo.save(update_fields=['estado'])

    return reversion


def _anular_venta(venta, user, motivo=''):
    """Anula la venta conservándola en el histórico (abono/rectificativa)."""
    from datetime import date

    _revertir_venta(venta, user)

    venta.anulada = True
    venta.fecha_anulacion = date.today()
    venta.motivo_anulacion = motivo or 'Anulación de la venta'
    venta.anulada_por = user
    venta.save(update_fields=[
        'anulada', 'fecha_anulacion', 'motivo_anulacion', 'anulada_por',
    ])
    return venta


def _deshacer_venta(venta, user):
    """Borra un borrador de venta tras revertir su contabilidad y su cobro."""
    _revertir_venta(venta, user)
    venta.delete()



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

    existente = factura_original.rectificativa_vigente
    if existente:
        messages.info(
            request,
            f'La factura {factura_original.codigo_factura} ya tiene la '
            f'rectificativa {existente.codigo_factura}. No se emite otra.',
        )
        return redirect('sales:factura_detail', pk=existente.pk)

    if factura_original.tipo_factura in ('R1', 'R4'):
        messages.error(
            request,
            'Esta factura ya es una rectificativa: rectifique la original.',
        )
        return redirect('sales:factura_detail', pk=factura_original.pk)
    
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
                f'Costo de acondicionamiento registrado: {format_euros(costo.total)}'
            )
            return redirect('sales:costos_list', vehiculo_pk=vehiculo_pk)
    else:
        form = CostoAcondicionamientoForm()
    
    context = {
        'form': form,
        'vehiculo': vehiculo,
    }
    return render(request, 'sales/costo_acondicionamiento_form.html', context)


# =============================================================================
# VISTAS DE COBROS FRACCIONADOS
# =============================================================================

@login_required
def cobro_list(request, venta_pk):
    """Lista de cobros fraccionados de una venta."""
    venta = get_object_or_404(VentaVehiculo, pk=venta_pk)
    cobros = venta.cobros.all()

    total_cobrado = sum(
        c.importe for c in cobros.filter(estado='RECIBIDO')
    )
    total_pendiente = sum(
        c.importe for c in cobros.filter(estado='PENDIENTE')
    )

    context = {
        'venta': venta,
        'cobros': cobros,
        'total_cobrado': total_cobrado,
        'total_pendiente': total_pendiente,
    }
    return render(request, 'sales/cobro_list.html', context)


@login_required
def cobro_create(request, venta_pk):
    """Añadir un plazo de cobro fraccionado."""
    venta = get_object_or_404(VentaVehiculo, pk=venta_pk)

    if not request.user.is_admin and not request.user.is_vendedor:
        messages.error(request, 'No tiene permisos para crear cobros.')
        return redirect('sales:detail', pk=venta.pk)

    if request.method == 'POST':
        from .models import CobroFraccionado
        from decimal import Decimal

        fecha_vencimiento = request.POST.get('fecha_vencimiento')
        importe = request.POST.get('importe')
        tipo_financiacion = request.POST.get('tipo_financiacion', 'CONTADO')
        comision = request.POST.get('comision_financiera', '0')
        notas = request.POST.get('notas', '')

        # Calcular siguiente número de plazo
        ultimo_plazo = venta.cobros.order_by('-numero_plazo').first()
        siguiente_plazo = (ultimo_plazo.numero_plazo + 1) if ultimo_plazo else 1

        cobro = CobroFraccionado.objects.create(
            venta=venta,
            fecha_vencimiento=fecha_vencimiento,
            importe=Decimal(importe),
            tipo_financiacion=tipo_financiacion,
            comision_financiera=Decimal(comision),
            numero_plazo=siguiente_plazo,
            notas=notas,
        )

        messages.success(
            request,
            f'Plazo {siguiente_plazo} creado: {format_euros(importe)} - vence {fecha_vencimiento}'
        )
        return redirect('sales:cobro_list', venta_pk=venta.pk)

    context = {
        'venta': venta,
    }
    return render(request, 'sales/cobro_form.html', context)


@login_required
def cobro_recibir(request, venta_pk, pk):
    """Marcar un cobro como recibido y generar asiento contable."""
    from .models import CobroFraccionado

    cobro = get_object_or_404(
        CobroFraccionado, pk=pk, venta__pk=venta_pk, estado='PENDIENTE'
    )

    if not request.user.is_admin and not request.user.is_vendedor:
        messages.error(request, 'No tiene permisos para recibir cobros.')
        return redirect('sales:cobro_list', venta_pk=venta_pk)

    if request.method != 'POST':
        return redirect('sales:cobro_list', venta_pk=venta_pk)

    try:
        cobro.recibir(request.user)
        messages.success(
            request,
            f'Plazo {cobro.numero_plazo} recibido: {format_euros(cobro.importe)}'
        )
    except Exception as e:
        messages.error(request, f'Error al recibir el cobro: {str(e)}')

    return redirect('sales:cobro_list', venta_pk=venta_pk)
