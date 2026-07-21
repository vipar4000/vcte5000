from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Sum
from datetime import date
from decimal import Decimal
from .models import BancoCuenta, BancoMovimiento, Reserva
from .forms import (
    BancoCuentaForm, BancoMovimientoFilterForm,
    ReservaForm, ConciliacionUploadForm,
)
from .services import (
    crear_movimiento_banco, obtener_cuenta_banco_default,
    conciliar_extracto, marcar_conciliado, conciliacion_batch,
)


# =============================================================================
# CUENTAS BANCARIAS
# =============================================================================

@login_required
def cuenta_list(request):
    """Lista de cuentas bancarias con saldos."""
    cuentas = BancoCuenta.objects.all()

    context = {
        'cuentas': cuentas,
    }
    return render(request, 'bank/cuenta_list.html', context)


@login_required
def cuenta_detail(request, pk):
    """Detalle de cuenta bancaria con movimientos filtrables."""
    cuenta = get_object_or_404(BancoCuenta, pk=pk)
    form = BancoMovimientoFilterForm(request.GET)
    movimientos = cuenta.movimientos.all()

    if form.is_valid():
        if form.cleaned_data.get('fecha_desde'):
            movimientos = movimientos.filter(fecha__gte=form.cleaned_data['fecha_desde'])
        if form.cleaned_data.get('fecha_hasta'):
            movimientos = movimientos.filter(fecha__lte=form.cleaned_data['fecha_hasta'])
        if form.cleaned_data.get('tipo'):
            movimientos = movimientos.filter(tipo=form.cleaned_data['tipo'])
        if form.cleaned_data.get('conciliado') is not None:
            movimientos = movimientos.filter(conciliado=form.cleaned_data['conciliado'])
        if form.cleaned_data.get('busqueda'):
            movimientos = movimientos.filter(
                concepto__icontains=form.cleaned_data['busqueda']
            )

    # Calcular balance
    total_ingresos = movimientos.filter(tipo='INGRESO').aggregate(
        total=Sum('importe'))['total'] or Decimal('0')
    total_egresos = movimientos.filter(tipo='EGRESO').aggregate(
        total=Sum('importe'))['total'] or Decimal('0')

    context = {
        'cuenta': cuenta,
        'movimientos': movimientos[:100],
        'form': form,
        'total_ingresos': total_ingresos,
        'total_egresos': total_egresos,
        'balance': total_ingresos - total_egresos,
    }
    return render(request, 'bank/cuenta_detail.html', context)


@login_required
def cuenta_create(request):
    """Crear cuenta bancaria."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para crear cuentas bancarias.')
        return redirect('bank:cuenta_list')

    if request.method == 'POST':
        form = BancoCuentaForm(request.POST)
        if form.is_valid():
            cuenta = form.save()
            messages.success(request, f'Cuenta {cuenta.nombre} creada correctamente.')
            return redirect('bank:cuenta_detail', pk=cuenta.pk)
    else:
        form = BancoCuentaForm()

    return render(request, 'bank/cuenta_form.html', {'form': form, 'action': 'crear'})


@login_required
def cuenta_edit(request, pk):
    """Editar cuenta bancaria."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para editar cuentas bancarias.')
        return redirect('bank:cuenta_list')

    cuenta = get_object_or_404(BancoCuenta, pk=pk)
    if request.method == 'POST':
        form = BancoCuentaForm(request.POST, instance=cuenta)
        if form.is_valid():
            cuenta = form.save()
            messages.success(request, f'Cuenta {cuenta.nombre} actualizada.')
            return redirect('bank:cuenta_detail', pk=cuenta.pk)
    else:
        form = BancoCuentaForm(instance=cuenta)

    return render(request, 'bank/cuenta_form.html', {'form': form, 'action': 'editar'})


# =============================================================================
# MOVIMIENTOS BANCARIOS
# =============================================================================

@login_required
def movimiento_list(request):
    """Lista global de movimientos bancarios con filtros."""
    form = BancoMovimientoFilterForm(request.GET)
    movimientos = BancoMovimiento.objects.select_related('banco_cuenta').all()

    if form.is_valid():
        if form.cleaned_data.get('fecha_desde'):
            movimientos = movimientos.filter(fecha__gte=form.cleaned_data['fecha_desde'])
        if form.cleaned_data.get('fecha_hasta'):
            movimientos = movimientos.filter(fecha__lte=form.cleaned_data['fecha_hasta'])
        if form.cleaned_data.get('tipo'):
            movimientos = movimientos.filter(tipo=form.cleaned_data['tipo'])
        if form.cleaned_data.get('conciliado') is not None:
            movimientos = movimientos.filter(conciliado=form.cleaned_data['conciliado'])
        if form.cleaned_data.get('busqueda'):
            movimientos = movimientos.filter(
                concepto__icontains=form.cleaned_data['busqueda']
            )

    context = {
        'movimientos': movimientos[:200],
        'form': form,
    }
    return render(request, 'bank/movimiento_list.html', context)


@login_required
def movimiento_detail(request, pk):
    """Detalle de un movimiento bancario."""
    movimiento = get_object_or_404(
        BancoMovimiento.objects.select_related('banco_cuenta', 'asiento_asociado'),
        pk=pk
    )
    context = {
        'movimiento': movimiento,
    }
    return render(request, 'bank/movimiento_detail.html', context)


# =============================================================================
# CONCILIACIÓN BANCARIA
# =============================================================================

@login_required
def conciliacion_upload(request):
    """Vista para subir extracto bancario y conciliar."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para conciliación bancaria.')
        return redirect('bank:cuenta_list')

    if request.method == 'POST':
        form = ConciliacionUploadForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data['archivo']
            banco_cuenta = form.cleaned_data['banco_cuenta']

            try:
                import pandas as pd

                if archivo.name.endswith('.csv'):
                    df = pd.read_csv(archivo)
                else:
                    df = pd.read_excel(archivo)

                # Normalizar columnas esperadas
                df.columns = [c.strip().lower() for c in df.columns]

                # Mapear columnas comunes del extracto bancario
                col_map = {}
                for col in df.columns:
                    if 'fecha' in col and 'valor' in col:
                        col_map[col] = 'fecha_valor'
                    elif 'fecha' in col:
                        col_map[col] = 'fecha'
                    elif 'concepto' in col or 'descripcion' in col:
                        col_map[col] = 'concepto'
                    elif 'tipo' in col or 'operacion' in col:
                        col_map[col] = 'tipo'
                    elif 'importe' in col or 'amount' in col or 'debito' in col or 'credito' in col:
                        col_map[col] = 'importe'

                df = df.rename(columns=col_map)

                # Convertir fechas
                if 'fecha' in df.columns:
                    df['fecha'] = pd.to_datetime(df['fecha']).dt.date

                # Normalizar tipo
                if 'tipo' in df.columns:
                    df['tipo'] = df['tipo'].apply(_normalizar_tipo)

                # Conciliar
                resultados = conciliar_extracto(banco_cuenta, df)

                context = {
                    'form': form,
                    'resultados': resultados,
                    'banco_cuenta': banco_cuenta,
                    'procesado': True,
                }
                return render(request, 'bank/conciliacion.html', context)

            except Exception as e:
                messages.error(request, f'Error al procesar el archivo: {str(e)}')
    else:
        form = ConciliacionUploadForm()

    context = {
        'form': form,
        'procesado': False,
    }
    return render(request, 'bank/conciliacion.html', context)


@login_required
def conciliacion_confirmar(request):
    """Confirma la conciliación de movimientos seleccionados."""
    if request.method != 'POST':
        return redirect('bank:conciliacion_upload')

    movimientos_ids = request.POST.getlist('movimientos_conciliar')
    if movimientos_ids:
        count = conciliacion_batch(movimientos_ids)
        messages.success(request, f'{count} movimientos conciliados correctamente.')
    else:
        messages.warning(request, 'No se seleccionaron movimientos para conciliar.')

    return redirect('bank:movimiento_list')


def _normalizar_tipo(valor):
    """Normaliza el tipo de movimiento del extracto bancario."""
    valor = str(valor).upper().strip()
    if any(p in valor for p in ['INGRESO', 'COBRO', 'ABONO', 'CREDITO', 'DEPOSITO']):
        return 'INGRESO'
    elif any(p in valor for p in ['EGRESO', 'CARGO', 'RECIBO', 'TRANSFERENCIA', 'PAGO', 'DEBITO']):
        return 'EGRESO'
    return 'INGRESO' if valor.startswith('+') else 'EGRESO'


# =============================================================================
# RESERVAS
# =============================================================================

@login_required
def reserva_list(request):
    """Lista de reservas."""
    reservas = Reserva.objects.select_related('vehiculo', 'created_by').all()

    estado = request.GET.get('estado', '')
    if estado:
        reservas = reservas.filter(estado=estado)

    context = {
        'reservas': reservas[:50],
        'estado_filtro': estado,
    }
    return render(request, 'bank/reserva_list.html', context)


@login_required
def reserva_create(request):
    """Crear una nueva reserva (arras/señal)."""
    if request.method == 'POST':
        form = ReservaForm(request.POST)
        if form.is_valid():
            reserva = form.save(commit=False)
            reserva.created_by = request.user

            # La cuenta bancaria por defecto
            banco_cuenta = obtener_cuenta_banco_default()
            if not banco_cuenta:
                messages.error(request, 'No hay cuentas bancarias configuradas.')
                return redirect('bank:reserva_list')

            # Crear movimiento bancario de ingreso
            with transaction.atomic():
                movimiento = crear_movimiento_banco(
                    banco_cuenta=banco_cuenta,
                    fecha=reserva.fecha_reserva,
                    concepto=f"Reserva/Señal {reserva.vehiculo} - {reserva.cliente_nombre}",
                    tipo='INGRESO',
                    importe=reserva.importe_reserva,
                )
                reserva.banco_movimiento = movimiento
                reserva.save()

                # Crear asiento contable: anticipo con IVA
                _crear_asiento_reserva(reserva, request.user)

            messages.success(
                request,
                f'Reserva creada: €{reserva.importe_reserva} - {reserva.vehiculo}'
            )
            return redirect('bank:reserva_detail', pk=reserva.pk)
    else:
        form = ReservaForm()

    context = {
        'form': form,
        'action': 'crear',
    }
    return render(request, 'bank/reserva_form.html', context)


@login_required
def reserva_detail(request, pk):
    """Detalle de una reserva."""
    reserva = get_object_or_404(
        Reserva.objects.select_related('vehiculo', 'banco_movimiento', 'venta'),
        pk=pk
    )

    context = {
        'reserva': reserva,
        'base_imponible': reserva.base_imponible,
        'cuota_iva': reserva.cuota_iva,
    }
    return render(request, 'bank/reserva_detail.html', context)


@login_required
def reserva_convertir(request, pk):
    """Convierte una reserva activa en una venta."""
    if request.method != 'POST':
        return redirect('bank:reserva_detail', pk=pk)

    reserva = get_object_or_404(Reserva, pk=pk, estado='ACTIVA')

    if reserva.venta:
        messages.warning(request, 'Esta reserva ya tiene una venta asociada.')
        return redirect('bank:reserva_detail', pk=pk)

    # Redirigir al formulario de venta con datos pre-cargados
    messages.info(
        request,
        f'Reserva de €{reserva.importe_reserva} será descontada del precio de venta.'
    )
    return redirect(
        f'/erp/ventas/nueva/?vehiculo={reserva.vehiculo.pk}'
        f'&reserva={reserva.pk}'
    )


@login_required
def reserva_cancelar(request, pk):
    """Cancela una reserva (devolución o penalización)."""
    if request.method != 'POST':
        return redirect('bank:reserva_detail', pk=pk)

    reserva = get_object_or_404(Reserva, pk=pk, estado='ACTIVA')
    accion = request.POST.get('accion', 'DEVUELTA')

    if accion not in ('DEVUELTA', 'PENALIZADA'):
        messages.error(request, 'Acción no válida.')
        return redirect('bank:reserva_detail', pk=pk)

    with transaction.atomic():
        reserva.estado = accion
        reserva.save(update_fields=['estado'])

        # Crear movimiento de egreso (devolución) si es devuelta
        if accion == 'DEVUELTA':
            banco_cuenta = reserva.banco_movimiento.banco_cuenta
            crear_movimiento_banco(
                banco_cuenta=banco_cuenta,
                fecha=date.today(),
                concepto=f"Devolución reserva {reserva.vehiculo} - {reserva.cliente_nombre}",
                tipo='EGRESO',
                importe=reserva.importe_reserva,
            )
        # Si es PENALIZADA, el dinero queda en la empresa (sin movimiento)

    messages.success(request, f'Reserva {reserva.get_estado_display().lower()} correctamente.')
    return redirect('bank:reserva_detail', pk=pk)


def _crear_asiento_reserva(reserva, user):
    """Crea el asiento contable del anticipo por reserva."""
    from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable
    from apps.accounting.views import generar_numero_asiento

    cuenta_banco = CuentaContable.objects.get(codigo='572')
    cuenta_anticipos = CuentaContable.objects.get(codigo='438')
    cuenta_iva = CuentaContable.objects.get(codigo='477')

    asiento = AsientoContable.objects.create(
        numero=generar_numero_asiento(),
        fecha=reserva.fecha_reserva,
        concepto=f"Anticipo reserva {reserva.vehiculo} - {reserva.cliente_nombre}",
        estado='BORRADOR',
        tipo_documento='Reserva',
        documento_id=reserva.pk,
        created_by=user,
    )

    MovimientoContable.objects.create(
        asiento=asiento, cuenta=cuenta_banco,
        debe=reserva.importe_reserva, haber=Decimal('0'),
        descripcion=f"Cobro reserva {reserva.cliente_nombre}",
    )

    MovimientoContable.objects.create(
        asiento=asiento, cuenta=cuenta_anticipos,
        debe=Decimal('0'), haber=reserva.base_imponible,
        descripcion=f"Anticipo cliente (base)",
    )

    MovimientoContable.objects.create(
        asiento=asiento, cuenta=cuenta_iva,
        debe=Decimal('0'), haber=reserva.cuota_iva,
        descripcion=f"IVA repercutido 21% anticipo",
    )

    return asiento
