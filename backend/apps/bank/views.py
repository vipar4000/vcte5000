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
    ReservaForm, ConciliacionUploadForm, DepositoForm,
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
    """Crear cuenta bancaria con deposito inicial opcional."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para crear cuentas bancarias.')
        return redirect('bank:cuenta_list')

    if request.method == 'POST':
        form = BancoCuentaForm(request.POST, request.FILES)
        if form.is_valid():
            cuenta = form.save()
            deposito = form.cleaned_data.get('deposito_inicial')
            if deposito and deposito > 0:
                notas = form.cleaned_data.get('notas_deposito', '')
                movimiento = crear_movimiento_banco(
                    banco_cuenta=cuenta,
                    fecha=date.today(),
                    concepto='Deposito inicial',
                    tipo='INGRESO',
                    importe=deposito,
                    notas=notas,
                )
                _crear_asiento_deposito(cuenta, deposito, 'Deposito inicial', date.today(), request.user)
                messages.success(request, f'Deposito inicial de {deposito} registrado.')
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
        form = BancoCuentaForm(request.POST, request.FILES, instance=cuenta, editing=True)
        if form.is_valid():
            cuenta = form.save()
            messages.success(request, f'Cuenta {cuenta.nombre} actualizada.')
            return redirect('bank:cuenta_detail', pk=cuenta.pk)
    else:
        form = BancoCuentaForm(instance=cuenta, editing=True)

    return render(request, 'bank/cuenta_form.html', {'form': form, 'action': 'editar'})


@login_required
def deposito_create(request, cuenta_pk):
    """Agregar un deposito (INGRESO) a una cuenta bancaria existente."""
    cuenta = get_object_or_404(BancoCuenta, pk=cuenta_pk)
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para registrar depositos.')
        return redirect('bank:cuenta_detail', pk=cuenta.pk)

    if request.method == 'POST':
        form = DepositoForm(request.POST, request.FILES)
        if form.is_valid():
            movimiento = crear_movimiento_banco(
                banco_cuenta=cuenta,
                fecha=form.cleaned_data['fecha'],
                concepto=form.cleaned_data['concepto'],
                tipo='INGRESO',
                importe=form.cleaned_data['importe'],
                notas=form.cleaned_data.get('notas', ''),
            )
            _crear_asiento_deposito(cuenta, form.cleaned_data['importe'], form.cleaned_data['concepto'], form.cleaned_data['fecha'], request.user)
            soporte = request.FILES.get('soporte')
            if soporte:
                movimiento.soporte = soporte
                movimiento.save()
            messages.success(request, f'Deposito de {form.cleaned_data["importe"]} registrado.')
            return redirect('bank:cuenta_detail', pk=cuenta.pk)
    else:
        form = DepositoForm()

    return render(request, 'bank/deposito_form.html', {
        'form': form, 'cuenta': cuenta, 'action': 'crear'
    })


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
                import csv
                import io
                from datetime import datetime as dt, timedelta

                content = archivo.read().decode('utf-8')

                # Detectar delimitador
                sniffer = csv.Sniffer()
                try:
                    dialect = sniffer.sniff(content[:2048])
                except csv.Error:
                    dialect = csv.excel

                reader = csv.DictReader(io.StringIO(content), dialect=dialect)

                # Mapear columnas comunes del extracto bancario
                col_map = {}
                for col in reader.fieldnames or []:
                    cl = col.strip().lower()
                    if 'fecha' in cl and 'valor' in cl:
                        col_map[col] = 'fecha_valor'
                    elif 'fecha' in cl:
                        col_map[col] = 'fecha'
                    elif 'concepto' in cl or 'descripcion' in cl:
                        col_map[col] = 'concepto'
                    elif 'tipo' in cl or 'operacion' in cl:
                        col_map[col] = 'tipo'
                    elif 'importe' in cl or 'amount' in cl or 'debito' in cl or 'credito' in cl or 'monto' in cl:
                        col_map[col] = 'importe'

                # Leer filas como lista de dicts con columnas normalizadas
                rows = []
                for raw_row in reader:
                    row = {}
                    for orig, mapped in col_map.items():
                        row[mapped] = raw_row.get(orig, '').strip()
                    rows.append(row)

                # Convertir formato de importe (25.000,50 / 2,420.00 / 2420,00 / 2420.00)
                for row in rows:
                    if 'importe' in row:
                        row['importe'] = _parse_importe(str(row['importe']))

                # Convertir fechas
                for row in rows:
                    if 'fecha' in row:
                        row['fecha'] = _parse_fecha(row['fecha'])

                # Normalizar tipo
                for row in rows:
                    if 'tipo' in row:
                        row['tipo'] = _normalizar_tipo(row['tipo'])
                    elif 'importe' in row:
                        row['tipo'] = 'INGRESO' if row['importe'] >= 0 else 'EGRESO'
                    else:
                        raise ValueError('El archivo no contiene columnas "tipo" ni "importe"')

                # Conciliar
                resultados = conciliar_extracto(banco_cuenta, rows)

                # Para filas sin match, buscar candidatos manuales
                from .models import BancoMovimiento
                for r in resultados:
                    if not r['erp_match']:
                        tipo = r['bank_row']['tipo']
                        importe = r['bank_row']['importe']
                        fecha = r['bank_row']['fecha']
                        tolerancia = importe * Decimal('0.10')
                        r['candidatos'] = BancoMovimiento.objects.filter(
                            banco_cuenta=banco_cuenta,
                            tipo=tipo,
                            conciliado=False,
                            importe__gte=importe - tolerancia,
                            importe__lte=importe + tolerancia,
                            fecha__gte=fecha - timedelta(days=30),
                            fecha__lte=fecha + timedelta(days=30),
                        ).order_by('fecha')[:10]
                    else:
                        r['candidatos'] = []

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

    movimientos_ids = []
    manual_count = 0

    # Recoger selecciones manuales del <select> (value=PK)
    for key, val in request.POST.items():
        if key.startswith('conciliar_manual_') and val:
            if val.isdigit():
                movimientos_ids.append(val)
            else:
                manual_count += 1

    movimientos_ids.extend(request.POST.getlist('movimientos_conciliar'))

    if movimientos_ids:
        count = conciliacion_batch(movimientos_ids)
        msg = f'{count} movimientos conciliados correctamente.'
        if manual_count:
            msg += f' {manual_count} marcados como conciliación manual (sin ERP).'
        messages.success(request, msg)
    elif manual_count:
        messages.success(request, f'{manual_count} movimientos marcados como conciliación manual (sin ERP).')
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


def _parse_fecha(valor):
    """Parsea una fecha en varios formatos comunes (dd/mm/aaaa, dd-mm-aaaa, etc.)."""
    from datetime import datetime
    valor = str(valor).strip()
    for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d.%m.%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(valor, fmt).date()
        except ValueError:
            continue
    raise ValueError(f'No se pudo parsear la fecha: "{valor}"')


def _parse_importe(valor):
    """Parsea un importe en formato español o ingles.

    Spanish:  2.420,00 → 2420.00
    English:  2,420.00 → 2420.00
    Simple:   2420.00  → 2420.00
    Simple:   2420,00  → 2420.00
    """
    valor = str(valor).strip()
    if not valor:
        return Decimal('0')

    negativo = False
    if valor.startswith('(') and valor.endswith(')'):
        negativo = True
        valor = valor[1:-1]
    if valor.endswith('-'):
        negativo = True
        valor = valor[:-1]
    valor = valor.replace('€', '').replace('$', '').replace(' ', '')

    tiene_punto = '.' in valor
    tiene_coma = ',' in valor

    if tiene_punto and tiene_coma:
        pos_punto = valor.rindex('.')
        pos_coma = valor.rindex(',')
        if pos_punto > pos_coma:
            # English: 2,420.00
            valor = valor.replace(',', '')
        else:
            # Spanish: 2.420,00
            valor = valor.replace('.', '').replace(',', '.')
    elif tiene_coma:
        parts = valor.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            # 2420,00 → decimal
            valor = valor.replace(',', '.')
        else:
            # 2,420,000 or just 2420,00 with more → thousands
            valor = valor.replace(',', '')
    elif tiene_punto:
        parts = valor.split('.')
        if len(parts) == 2 and len(parts[1]) <= 2:
            # 2420.00 → already decimal
            pass
        else:
            # 2.420.000 → thousands
            valor = valor.replace('.', '')

    result = Decimal(valor) if valor else Decimal('0')
    if negativo:
        result = -result
    return result


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


# =============================================================================
# GUÍA / AYUDA
# =============================================================================

@login_required
def banco_guia(request):
    """Guía paso a paso del módulo bancario."""
    return render(request, 'bank/guia.html')


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


def _crear_asiento_deposito(cuenta, importe, concepto, fecha, user):
    """Crea el asiento contable de un deposito: DEBE 572 (banco) / HABER 110 (resultados no asignados)."""
    from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable
    from apps.accounting.views import generar_numero_asiento

    cuenta_banco = CuentaContable.objects.get(codigo='572')
    cuenta_resultados = CuentaContable.objects.get(codigo='110')

    asiento = AsientoContable.objects.create(
        numero=generar_numero_asiento(),
        fecha=fecha,
        concepto=f'{concepto} - {cuenta.nombre}',
        estado='POSTEADO',
        tipo_documento='Banco',
        created_by=user,
    )

    MovimientoContable.objects.create(
        asiento=asiento, cuenta=cuenta_banco,
        debe=Decimal(str(importe)), haber=Decimal('0'),
        descripcion=f'{concepto} {cuenta.nombre}',
    )

    MovimientoContable.objects.create(
        asiento=asiento, cuenta=cuenta_resultados,
        debe=Decimal('0'), haber=Decimal(str(importe)),
        descripcion=f'{concepto} {cuenta.nombre}',
    )

    return asiento


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
