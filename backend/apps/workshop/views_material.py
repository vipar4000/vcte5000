from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F, ExpressionWrapper, DecimalField
from django.db import transaction
from django.core.files import File
from datetime import date
from decimal import Decimal
from .models import (
    Material, MaterialUsado, OrdenTrabajo, CompraMaterial,
    _anular_asiento_pago_compra,
)
from .forms import MaterialForm, CompraFacturaForm, CompraMaterialLineaFormSet
from apps.accounting.models import CuentaContable
from apps.bank.models import BancoCuenta
from apps.bank.services import obtener_cuenta_banco_default
from apps.core.formatting import format_euros


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

    compras = material.compras.select_related('asiento_contable').all()
    
    context = {
        'material': material,
        'usos': usos,
        'stats': stats,
        'compras': compras,
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
            if 'guardar_otro' in request.POST:
                messages.info(request, 'Puede crear el siguiente material.')
                return redirect('workshop:material_create')
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
def compra_material_create(request):
    """Registrar compra de material(es) en una misma factura (cabecera + líneas)."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para registrar compras de material.')
        return redirect('workshop:material_list')

    if request.method == 'POST':
        header_form = CompraFacturaForm(request.POST, request.FILES)
        linea_formset = CompraMaterialLineaFormSet(request.POST, prefix='lineas')

        if header_form.is_valid() and linea_formset.is_valid():
            pdf_file = header_form.cleaned_data.get('documento_pdf')
            forma_pago_code = header_form.cleaned_data.get('forma_pago') or ''
            pagado = header_form.cleaned_data.get('pagado', False)
            fecha_pago = header_form.cleaned_data.get('fecha_pago') or None
            cuenta_pago_code = header_form.cleaned_data.get('cuenta_pago') or ''

            # Resolver la cuenta de contrapartida (vacío = crédito 410)
            forma_pago_cuenta = None
            if forma_pago_code:
                try:
                    forma_pago_cuenta = CuentaContable.objects.get(
                        codigo=forma_pago_code
                    )
                except CuentaContable.DoesNotExist:
                    messages.error(
                        request,
                        f'Falta la cuenta contable {forma_pago_code} en el plan '
                        f'contable. Inicialice el plan en Contabilidad > Cuentas > '
                        f'Inicializar.'
                    )
                    return render(request, 'workshop/material_compra_form.html', {
                        'header_form': header_form,
                        'linea_formset': linea_formset,
                        'materiales': Material.objects.all().order_by('nombre'),
                    })

            # El checkbox "Pagar ahora" solo aplica a crédito; en contado el
            # pago ya quedó registrado en el asiento de compra.
            pagar_ahora = pagado and (not forma_pago_code or forma_pago_code == '410')
            cuenta_pago = None
            if pagar_ahora and cuenta_pago_code:
                try:
                    cuenta_pago = CuentaContable.objects.get(codigo=cuenta_pago_code)
                except CuentaContable.DoesNotExist:
                    messages.error(
                        request,
                        f'Falta la cuenta contable {cuenta_pago_code} en el plan '
                        f'contable. Inicialice el plan en Contabilidad > Cuentas > '
                        f'Inicializar.'
                    )
                    return render(request, 'workshop/material_compra_form.html', {
                        'header_form': header_form,
                        'linea_formset': linea_formset,
                        'materiales': Material.objects.all().order_by('nombre'),
                    })

            # Validar saldo disponible ANTES de crear nada (evita errores a
            # mitad de la transacción si el banco no cubre el total a pagar).
            paga_con_banco = pagar_ahora and (not cuenta_pago_code or cuenta_pago_code == '572')
            if forma_pago_code == '572' or paga_con_banco:
                total_a_pagar = Decimal('0')
                for linea_form in linea_formset:
                    if not linea_form.cleaned_data or linea_form.cleaned_data.get('DELETE'):
                        continue
                    material = linea_form.cleaned_data.get('material')
                    cantidad = linea_form.cleaned_data.get('cantidad')
                    precio = linea_form.cleaned_data.get('precio_unitario')
                    if not material or cantidad is None or precio is None:
                        continue
                    tipo_iva = header_form.cleaned_data['tipo_iva']
                    total_a_pagar += cantidad * precio * (
                        Decimal('1') + tipo_iva / Decimal('100')
                    )
                banco_cuenta = BancoCuenta.objects.filter(
                    cuenta_contable__codigo='572'
                ).first()
                if not banco_cuenta:
                    banco_cuenta = obtener_cuenta_banco_default()
                if banco_cuenta and total_a_pagar > banco_cuenta.saldo_pendiente:
                    messages.error(
                        request,
                        f'Saldo insuficiente en {banco_cuenta.nombre} para el pago '
                        f'de {format_euros(total_a_pagar)}. '
                        f'Disponible: {format_euros(banco_cuenta.saldo_pendiente)}.'
                    )
                    return render(request, 'workshop/material_compra_form.html', {
                        'header_form': header_form,
                        'linea_formset': linea_formset,
                        'materiales': Material.objects.all().order_by('nombre'),
                    })

            lineas_creadas = 0
            asientos_ok = 0
            pagos_ok = 0

            with transaction.atomic():
                for i, linea_form in enumerate(linea_formset):
                    # Saltar formularios vacíos o marcados para borrar
                    if not linea_form.cleaned_data or linea_form.cleaned_data.get('DELETE'):
                        continue
                    material = linea_form.cleaned_data.get('material')
                    cantidad = linea_form.cleaned_data.get('cantidad')
                    precio_unitario = linea_form.cleaned_data.get('precio_unitario')
                    if not material or cantidad is None or precio_unitario is None:
                        continue
                    compra = CompraMaterial(
                        material=material,
                        cantidad=cantidad,
                        precio_unitario=precio_unitario,
                        proveedor=header_form.cleaned_data['proveedor'],
                        cif_nif=header_form.cleaned_data['cif_nif'],
                        fecha_compra=header_form.cleaned_data['fecha_compra'],
                        numero_factura=header_form.cleaned_data.get('numero_factura', ''),
                        tipo_inventario=header_form.cleaned_data['tipo_inventario'],
                        tipo_iva=header_form.cleaned_data['tipo_iva'],
                        forma_pago=forma_pago_cuenta,
                        created_by=request.user,
                    )
                    if i == 0 and pdf_file:
                        compra.documento_pdf = pdf_file
                    compra.save()
                    lineas_creadas += 1

                    try:
                        asiento = compra.crear_asiento_contable()
                        if asiento.esta_cuadrado:
                            asiento.estado = 'POSTEADO'
                            asiento.save()
                            asientos_ok += 1

                        # "Pagar ahora" (solo crédito): asiento de pago
                        # automático (DEBE 410 / HABER tesorería) + EGRESO si 572.
                        if pagar_ahora:
                            compra.pagado = True
                            compra.fecha_pago = fecha_pago
                            compra.cuenta_pago = cuenta_pago
                            compra.crear_asiento_pago()
                            compra.save(update_fields=['pagado', 'fecha_pago', 'cuenta_pago'])
                            pagos_ok += 1
                    except Exception as e:
                        # La factura se procesa en una única transacción atómica:
                        # cualquier error revierte todas las líneas (stock, asientos
                        # y movimientos bancarios) y se informa al usuario.
                        transaction.set_rollback(True)
                        messages.error(
                            request,
                            f'Error al contabilizar la línea {lineas_creadas} '
                            f'({compra.material.nombre}): {e}. '
                            f'No se guardó ninguna línea de la factura.'
                        )
                        return render(request, 'workshop/material_compra_form.html', {
                            'header_form': header_form,
                            'linea_formset': linea_formset,
                            'materiales': Material.objects.all().order_by('nombre'),
                        })

            descripcion_pago = {
                '': 'Crédito (pendiente en 410)',
                '572': 'Contado banco (EGRESO registrado)',
                '570': 'Contado caja',
            }.get(forma_pago_code, 'Crédito (pendiente en 410)')
            if pagar_ahora:
                descripcion_pago = (
                    'Crédito pagado (asiento de pago DEBE 410 / HABER tesorería'
                    ' generado por línea)'
                )
            if pagado and not pagar_ahora:
                descripcion_pago += ' — el checkbox "Pagar ahora" no aplica al contado'
            messages.success(
                request,
                f'Factura registrada: {lineas_creadas} material(es) comprado(s), '
                f'{asientos_ok} asiento(s) posteado(s)'
                f'{" y " + str(pagos_ok) + " pago(s) registrado(s)" if pagos_ok else ""}. '
                f'{descripcion_pago}.'
            )
            return redirect('workshop:material_list')
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        header_form = CompraFacturaForm()
        linea_formset = CompraMaterialLineaFormSet(prefix='lineas')

    context = {
        'header_form': header_form,
        'linea_formset': linea_formset,
        'materiales': Material.objects.all().order_by('nombre'),
    }
    return render(request, 'workshop/material_compra_form.html', context)


@login_required
def compra_pagar(request, pk):
    """Marcar como pagada una compra de material a crédito (asiento + EGRESO)."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para pagar compras.')
        return redirect('workshop:material_list')

    compra = get_object_or_404(CompraMaterial, pk=pk)

    if request.method != 'POST':
        return redirect('workshop:material_detail', pk=compra.material.pk)

    if not compra.es_credito:
        messages.error(
            request,
            'La compra se registró al contado: su pago ya quedó reflejado '
            'en el asiento de compra.'
        )
        return redirect('workshop:material_detail', pk=compra.material.pk)

    if compra.pagado:
        messages.info(request, 'La compra ya está marcada como pagada.')
        return redirect('workshop:material_detail', pk=compra.material.pk)

    fecha_pago = request.POST.get('fecha_pago') or None
    if fecha_pago:
        try:
            fecha_pago = date.fromisoformat(fecha_pago)
        except ValueError:
            fecha_pago = None
    cuenta_pago_code = request.POST.get('cuenta_pago') or ''
    cuenta_pago = None
    if cuenta_pago_code in ('570', '572'):
        cuenta_pago = CuentaContable.objects.filter(
            codigo=cuenta_pago_code
        ).first()
        if not cuenta_pago:
            messages.error(
                request,
                f'Falta la cuenta contable {cuenta_pago_code} en el plan '
                f'contable. Inicialice el plan en Contabilidad > Cuentas > '
                f'Inicializar.'
            )
            return redirect('workshop:material_detail', pk=compra.material.pk)

    compra.pagado = True
    compra.fecha_pago = fecha_pago
    compra.cuenta_pago = cuenta_pago
    compra.save(update_fields=['pagado', 'fecha_pago', 'cuenta_pago'])

    try:
        pago = compra.crear_asiento_pago()
        codigo = pago.movimientos.filter(haber__gt=0).first()
        codigo_pago = codigo.cuenta.codigo if codigo else 'tesorería'
        messages.success(
            request,
            f'Compra pagada. Asiento de pago #{pago.numero} '
            f'(DEBE 410 / HABER {codigo_pago}) generado automáticamente.'
        )
    except Exception as e:
        messages.error(
            request,
            f'No se pudo generar el asiento de pago: {e}'
        )
        return redirect('workshop:material_detail', pk=compra.material.pk)

    return redirect('workshop:material_detail', pk=compra.material.pk)


@login_required
def compra_deshacer_pago(request, pk):
    """Desmarcar el pago de una compra (anula el asiento y elimina el EGRESO)."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para modificar compras.')
        return redirect('workshop:material_list')

    compra = get_object_or_404(CompraMaterial, pk=pk)

    if request.method != 'POST':
        return redirect('workshop:material_detail', pk=compra.material.pk)

    if not compra.pagado:
        messages.info(request, 'La compra no está marcada como pagada.')
        return redirect('workshop:material_detail', pk=compra.material.pk)

    with transaction.atomic():
        _anular_asiento_pago_compra(compra, request.user)
        compra.pagado = False
        compra.fecha_pago = None
        compra.cuenta_pago = None
        compra.save(update_fields=['pagado', 'fecha_pago', 'cuenta_pago'])

    messages.success(
        request,
        'Pago deshecho: asiento de pago anulado (Ley Antifraude) y EGRESO '
        'bancario eliminado. La compra vuelve a quedar pendiente en 410.'
    )
    return redirect('workshop:material_detail', pk=compra.material.pk)


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
    
    if not request.user.puede_eliminar:
        messages.error(request, 'No tiene permisos para eliminar registros.')
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
