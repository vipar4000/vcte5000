from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from datetime import date
from .models import AsientoContable, MovimientoContable, CuentaContable, PlanContableDefault
from .forms import (
    AsientoContableForm, MovimientoContableFormSet, FiltroAsientosForm,
    CuentaContableForm
)
from apps.core.formatting import format_euros


@login_required
def asiento_list(request):
    """Lista de asientos contables con filtros y paginación."""
    form = FiltroAsientosForm(request.GET)
    asientos = AsientoContable.objects.select_related('created_by').all()
    
    buscar = request.GET.get('buscar', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    estado = request.GET.get('estado', '')
    
    if buscar:
        asientos = asientos.filter(
            Q(numero__icontains=buscar) |
            Q(concepto__icontains=buscar)
        )
    
    if fecha_desde:
        asientos = asientos.filter(fecha__gte=fecha_desde)
    
    if fecha_hasta:
        asientos = asientos.filter(fecha__lte=fecha_hasta)
    
    if estado:
        asientos = asientos.filter(estado=estado)
    
    # Paginación
    paginator = Paginator(asientos, 20)
    page = request.GET.get('page', 1)
    asientos_paginados = paginator.get_page(page)
    
    # Estadísticas
    stats = {
        'total': AsientoContable.objects.count(),
        'borradores': AsientoContable.objects.filter(estado='BORRADOR').count(),
        'posteados': AsientoContable.objects.filter(estado='POSTEADO').count(),
        'total_debe': AsientoContable.objects.filter(estado='POSTEADO').aggregate(
            total=Sum('movimientos__debe')
        )['total'] or 0,
    }
    
    context = {
        'asientos': asientos_paginados,
        'form': form,
        'stats': stats,
    }
    return render(request, 'accounting/list.html', context)


@login_required
def asiento_create(request):
    """Crear un nuevo asiento contable."""
    if request.method == 'POST':
        form = AsientoContableForm(request.POST)
        formset = MovimientoContableFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            asiento = form.save(commit=False)
            asiento.created_by = request.user
            asiento.save()
            
            formset.instance = asiento
            formset.save()
            
            # Validar cuadre del asiento
            if not asiento.esta_cuadrado:
                messages.warning(
                    request,
                    f'Asiento creado pero NO cuadrado (Debe: {format_euros(asiento.total_debe)} / Haber: {format_euros(asiento.total_haber)})'
                )
            else:
                messages.success(request, 'Asiento contable creado correctamente')
            
            return redirect('accounting:detail', pk=asiento.pk)
    else:
        form = AsientoContableForm(initial={
            'fecha': date.today(),
            'numero': generar_numero_asiento(),
        })
        formset = MovimientoContableFormSet()
    
    context = {
        'form': form,
        'formset': formset,
        'titulo': 'Nuevo Asiento Contable',
    }
    return render(request, 'accounting/form.html', context)


@login_required
def asiento_detail(request, pk):
    """Detalle de un asiento contable."""
    asiento = get_object_or_404(
        AsientoContable.objects.prefetch_related('movimientos__cuenta'),
        pk=pk
    )
    
    context = {
        'asiento': asiento,
    }
    return render(request, 'accounting/detail.html', context)


@login_required
def asiento_update(request, pk):
    """Actualizar un asiento contable."""
    asiento = get_object_or_404(AsientoContable, pk=pk)
    
    if asiento.estado == 'POSTEADO':
        messages.error(request, 'No se puede editar un asiento ya posteado')
        return redirect('accounting:detail', pk=asiento.pk)
    
    if request.method == 'POST':
        form = AsientoContableForm(request.POST, instance=asiento)
        formset = MovimientoContableFormSet(request.POST, instance=asiento)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            messages.success(request, 'Asiento actualizado correctamente')
            return redirect('accounting:detail', pk=asiento.pk)
    else:
        form = AsientoContableForm(instance=asiento)
        formset = MovimientoContableFormSet(instance=asiento)
    
    context = {
        'form': form,
        'formset': formset,
        'asiento': asiento,
        'titulo': f'Editar Asiento {asiento.numero}',
    }
    return render(request, 'accounting/form.html', context)


@login_required
def asiento_postear(request, pk):
    """Postear un asiento contable (validar y marcar como final)."""
    asiento = get_object_or_404(AsientoContable, pk=pk)
    
    if asiento.estado != 'BORRADOR':
        messages.error(request, 'Solo se pueden postear asientos en borrador')
        return redirect('accounting:detail', pk=asiento.pk)
    
    # Validar cuadre
    if not asiento.esta_cuadrado:
        messages.error(
            request,
            f'El asiento no está cuadrado (Debe: {format_euros(asiento.total_debe)} / Haber: {format_euros(asiento.total_haber)})'
        )
        return redirect('accounting:detail', pk=asiento.pk)
    
    # Validar que tenga movimientos
    if asiento.movimientos.count() < 2:
        messages.error(request, 'El asiento debe tener al menos 2 movimientos')
        return redirect('accounting:detail', pk=asiento.pk)
    
    asiento.estado = 'POSTEADO'
    asiento.save()
    
    messages.success(request, f'Asiento {asiento.numero} posteado correctamente')
    return redirect('accounting:detail', pk=asiento.pk)


@login_required
def asiento_anular(request, pk):
    """Anular un asiento contable."""
    asiento = get_object_or_404(AsientoContable, pk=pk)
    
    if asiento.estado == 'ANULADO':
        messages.error(request, 'El asiento ya está anulado')
        return redirect('accounting:detail', pk=asiento.pk)
    
    asiento.estado = 'ANULADO'
    asiento.save()
    
    messages.success(request, f'Asiento {asiento.numero} anulado')
    return redirect('accounting:detail', pk=asiento.pk)


@login_required
def cuenta_contable_list(request):
    """Lista de cuentas contables."""
    cuentas = CuentaContable.objects.all()
    
    # Filtros
    buscar = request.GET.get('buscar', '')
    tipo = request.GET.get('tipo', '')
    
    if buscar:
        cuentas = cuentas.filter(
            Q(codigo__icontains=buscar) |
            Q(nombre__icontains=buscar)
        )
    
    if tipo:
        cuentas = cuentas.filter(tipo=tipo)
    
    context = {
        'cuentas': cuentas,
    }
    return render(request, 'accounting/cuentas.html', context)


@login_required
def cuenta_contable_create(request):
    """Crear una cuenta contable."""
    if request.method == 'POST':
        form = CuentaContableForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cuenta contable creada')
            return redirect('accounting:cuentas')
    else:
        form = CuentaContableForm()
    
    context = {
        'form': form,
        'titulo': 'Nueva Cuenta Contable',
    }
    return render(request, 'accounting/cuenta_form.html', context)


@login_required
def inicializar_plan_contable(request):
    """Inicializa el plan contable base del PGC."""
    if not request.user.is_admin:
        messages.error(request, 'Solo los administradores pueden inicializar el plan contable')
        return redirect('accounting:cuentas')
    
    PlanContableDefault.crear_plan_base()
    messages.success(request, 'Plan contable inicializado correctamente')
    return redirect('accounting:cuentas')


def generar_numero_asiento():
    """Genera el siguiente número de asiento."""
    ultimo = AsientoContable.objects.order_by('-numero').first()
    if ultimo:
        try:
            numero = int(ultimo.numero) + 1
        except ValueError:
            numero = 1
    else:
        numero = 1
    return str(numero).zfill(6)
