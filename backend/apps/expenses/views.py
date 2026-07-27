from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Sum
import csv
from .models import GastoEstructura, InversionInicial, LineaInversionInicial
from .forms import (
    GastoEstructuraForm, GastoBusquedaForm,
    InversionInicialForm, LineaInversionInicialFormSet,
)
from apps.workshop.models import Material


@login_required
def gasto_list(request):
    """Lista de gastos de estructura con filtros."""
    if not request.user.is_admin and not request.user.is_gestoria:
        messages.error(request, 'No tiene permisos para acceder a gastos.')
        return redirect('home')

    gastos = GastoEstructura.objects.select_related('created_by').all()

    form = GastoBusquedaForm(request.GET)
    busqueda = request.GET.get('busqueda', '')
    categoria = request.GET.get('categoria', '')
    pagado = request.GET.get('pagado', '')

    if busqueda:
        gastos = gastos.filter(
            Q(proveedor_acreedor__icontains=busqueda) |
            Q(cif_nif__icontains=busqueda)
        )

    if categoria:
        gastos = gastos.filter(categoria=categoria)

    if pagado:
        gastos = gastos.filter(pagado=pagado == 'True')

    stats = {
        'total': GastoEstructura.objects.count(),
        'total_importe': GastoEstructura.objects.aggregate(
            total=Sum('total_factura')
        )['total'] or 0,
        'pendientes': GastoEstructura.objects.filter(pagado=False).aggregate(
            total=Sum('total_factura')
        )['total'] or 0,
    }

    materiales_alerta = Material.objects.filter(alerta_stock=True)[:5]

    context = {
        'gastos': gastos[:50],
        'stats': stats,
        'form': form,
        'materiales_alerta': materiales_alerta,
    }
    return render(request, 'expenses/list.html', context)


@login_required
def gasto_create(request):
    """Crear nuevo gasto de estructura."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para crear gastos.')
        return redirect('expenses:list')

    if request.method == 'POST':
        form = GastoEstructuraForm(request.POST, request.FILES)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.created_by = request.user
            gasto.save()

            try:
                asiento = gasto.crear_asiento_contable()
                messages.success(
                    request,
                    f'Gasto registrado. Asiento contable #{asiento.numero} creado automáticamente.'
                )
            except Exception as e:
                messages.warning(
                    request,
                    f'Gasto registrado, pero no se pudo crear el asiento contable: {str(e)}'
                )

            return redirect('expenses:detail', pk=gasto.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = GastoEstructuraForm()

    materiales_alerta = Material.objects.filter(alerta_stock=True)

    context = {
        'form': form,
        'action': 'crear',
        'materiales_alerta': materiales_alerta,
    }
    return render(request, 'expenses/form.html', context)


@login_required
def gasto_detail(request, pk):
    """Detalle de un gasto."""
    if not request.user.is_admin and not request.user.is_gestoria:
        messages.error(request, 'No tiene permisos para ver gastos.')
        return redirect('home')

    gasto = get_object_or_404(
        GastoEstructura.objects.select_related('created_by'),
        pk=pk
    )

    asiento = None
    try:
        from apps.accounting.models import AsientoContable
        asiento = AsientoContable.objects.filter(
            tipo_documento='GastoEstructura',
            documento_id=gasto.pk
        ).first()
    except Exception:
        pass

    context = {
        'gasto': gasto,
        'asiento': asiento,
    }
    return render(request, 'expenses/detail.html', context)


@login_required
def gasto_update(request, pk):
    """Editar gasto de estructura."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para editar gastos.')
        return redirect('expenses:list')

    gasto = get_object_or_404(GastoEstructura, pk=pk)

    if request.method == 'POST':
        form = GastoEstructuraForm(request.POST, request.FILES, instance=gasto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Gasto actualizado correctamente.')
            return redirect('expenses:detail', pk=gasto.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = GastoEstructuraForm(instance=gasto)

    context = {
        'form': form,
        'gasto': gasto,
        'action': 'editar',
    }
    return render(request, 'expenses/form.html', context)


@login_required
def gasto_delete(request, pk):
    """Eliminar gasto de estructura."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para eliminar gastos.')
        return redirect('expenses:list')
    
    if not request.user.puede_eliminar:
        messages.error(request, 'No tiene permisos para eliminar registros.')
        return redirect('expenses:list')

    gasto = get_object_or_404(GastoEstructura, pk=pk)

    if request.method == 'POST':
        gasto.delete()
        messages.success(request, 'Gasto eliminado correctamente.')
        return redirect('expenses:list')

    context = {
        'gasto': gasto,
    }
    return render(request, 'expenses/delete.html', context)


@login_required
def gasto_export_csv(request):
    """Exportar gastos a CSV para la gestoría."""
    if not request.user.is_admin and not request.user.is_gestoria:
        messages.error(request, 'No tiene permisos para exportar gastos.')
        return redirect('home')

    gastos = GastoEstructura.objects.all()

    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    if fecha_desde:
        gastos = gastos.filter(fecha_factura__gte=fecha_desde)
    if fecha_hasta:
        gastos = gastos.filter(fecha_factura__lte=fecha_hasta)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="gastos_estructura.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Fecha', 'Proveedor', 'CIF/NIF', 'Categoría',
        'Base Imponible', 'Tipo IVA', 'Cuota IVA',
        'Retención IRPF', 'Cuota Retención', 'Total Factura',
        'Pagado', 'Fecha Pago',
    ])

    for gasto in gastos:
        writer.writerow([
            gasto.fecha_factura,
            gasto.proveedor_acreedor,
            gasto.cif_nif,
            gasto.get_categoria_display(),
            gasto.base_imponible,
            gasto.tipo_iva,
            gasto.cuota_iva,
            gasto.retencion_irpf,
            gasto.cuota_retencion,
            gasto.total_factura,
            'Sí' if gasto.pagado else 'No',
            gasto.fecha_pago or '',
        ])

    total_base = gastos.aggregate(t=Sum('base_imponible'))['t'] or 0
    total_iva = gastos.aggregate(t=Sum('cuota_iva'))['t'] or 0
    total_ret = gastos.aggregate(t=Sum('cuota_retencion'))['t'] or 0
    total_total = gastos.aggregate(t=Sum('total_factura'))['t'] or 0
    writer.writerow([])
    writer.writerow(['', '', '', 'TOTALES', total_base, '', total_iva, '', total_ret, total_total, '', ''])

    return response


# ---------------------------------------------------------------------------
# Inversión Inicial (asistente de apertura con desglose multilínea)
# ---------------------------------------------------------------------------

@login_required
def inversion_list(request):
    """Lista de inversiones iniciales."""
    if not request.user.is_admin and not request.user.is_gestoria:
        messages.error(request, 'No tiene permisos para acceder a inversiones.')
        return redirect('home')

    inversiones = InversionInicial.objects.select_related('created_by', 'forma_pago').all()
    context = {
        'inversiones': inversiones[:100],
    }
    return render(request, 'expenses/inversion_list.html', context)


@login_required
def inversion_create(request):
    """Asistente de registro de inversión inicial (cabecera + líneas)."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para registrar inversiones.')
        return redirect('expenses:inversion_list')

    if request.method == 'POST':
        form = InversionInicialForm(request.POST, request.FILES)
        formset = LineaInversionInicialFormSet(request.POST, instance=InversionInicial())
        form.lineas_formset = formset
        if formset.is_valid() and form.is_valid():
            inversion = form.save(commit=False)
            inversion.created_by = request.user
            inversion.save()
            formset.instance = inversion
            formset.save()

            try:
                asiento = inversion.crear_asiento_contable()
                messages.success(
                    request,
                    f'Inversión registrada. Asiento contable #{asiento.numero} creado automáticamente.'
                )
            except Exception as e:
                messages.warning(
                    request,
                    f'Inversión registrada, pero no se pudo crear el asiento contable: {str(e)}'
                )
            return redirect('expenses:inversion_detail', pk=inversion.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = InversionInicialForm()
        formset = LineaInversionInicialFormSet(instance=InversionInicial())
        form.lineas_formset = formset

    context = {
        'form': form,
        'formset': formset,
    }
    return render(request, 'expenses/inversion_form.html', context)


@login_required
def inversion_detail(request, pk):
    """Detalle de una inversión inicial con sus líneas y asiento."""
    if not request.user.is_admin and not request.user.is_gestoria:
        messages.error(request, 'No tiene permisos para ver inversiones.')
        return redirect('home')

    inversion = get_object_or_404(
        InversionInicial.objects.select_related('created_by', 'forma_pago'),
        pk=pk
    )
    asiento = None
    try:
        from apps.accounting.models import AsientoContable
        asiento = AsientoContable.objects.filter(
            tipo_documento='InversionInicial',
            documento_id=inversion.pk
        ).first()
    except Exception:
        pass

    context = {
        'inversion': inversion,
        'asiento': asiento,
    }
    return render(request, 'expenses/inversion_detail.html', context)
