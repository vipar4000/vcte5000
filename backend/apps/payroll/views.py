from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import NominaEstructura
from .forms import NominaEstructuraForm
from apps.core.formatting import format_euros


def _requiere_admin_o_gestoria(request):
    if not request.user.is_admin and not request.user.is_gestoria:
        messages.error(request, 'Solo administradores y gestoría pueden acceder a nóminas.')
        return False
    return True


@login_required
def nomina_list(request):
    """Lista de nóminas de estructura."""
    if not _requiere_admin_o_gestoria(request):
        return redirect('home')

    nominas = NominaEstructura.objects.select_related('empleado', 'created_by').all()

    context = {
        'nominas': nominas[:50],
        'total_nominas': nominas.count(),
    }
    return render(request, 'payroll/list.html', context)


@login_required
def nomina_create(request):
    """Crear nueva nómina de estructura."""
    if not _requiere_admin_o_gestoria(request):
        return redirect('home')

    if request.method == 'POST':
        form = NominaEstructuraForm(request.POST)
        if form.is_valid():
            nomina = form.save(commit=False)
            nomina.created_by = request.user
            nomina.save()

            try:
                asiento = nomina.crear_asiento_contable()
                messages.success(
                    request,
                    f'Nómina registrada. Asiento contable #{asiento.numero} creado automáticamente.'
                )
            except Exception as e:
                messages.warning(
                    request,
                    f'Nómina registrada pero no se pudo crear el asiento contable: {e}'
                )

            return redirect('payroll:detail', pk=nomina.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = NominaEstructuraForm()

    context = {
        'form': form,
        'action': 'crear',
    }
    return render(request, 'payroll/form.html', context)


@login_required
def nomina_detail(request, pk):
    """Detalle de una nómina de estructura."""
    if not _requiere_admin_o_gestoria(request):
        return redirect('home')

    nomina = get_object_or_404(
        NominaEstructura.objects.select_related('empleado', 'created_by', 'asiento_contable'),
        pk=pk
    )

    asiento = nomina.asiento_contable

    context = {
        'nomina': nomina,
        'asiento': asiento,
    }
    return render(request, 'payroll/detail.html', context)


@login_required
def nomina_generar_mensual(request):
    """Genera nóminas mensuales automáticamente para todos los operarios configurados."""
    if not request.user.is_admin:
        messages.error(request, 'Solo administradores pueden generar nóminas automáticas.')
        return redirect('payroll:list')

    from .services import generar_nomina_mensual
    resultado = generar_nomina_mensual()

    if resultado['status'] == 'ok':
        messages.success(
            request,
            f'{resultado["generadas"]} nómina(s) generada(s) correctamente.'
        )
    else:
        messages.error(request, f'Error al generar nóminas: {resultado.get("error", "desconocido")}')

    return redirect('payroll:list')
