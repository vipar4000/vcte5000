"""Gestión de usuarios dentro del ERP (sin pasar por el admin de Django).

Solo accesible para ADMIN. Permite listar, crear, editar, activar/desactivar y
desbloquear cuentas con la misma estética que el resto del sistema.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import UsuarioForm
from .models import User


def _denegar_si_no_admin(request):
    """Devuelve una redirección si el usuario no es ADMIN, o None si puede pasar."""
    if request.user.is_admin:
        return None
    messages.error(request, 'No tiene permisos para gestionar usuarios.')
    return redirect('home')


@login_required
def usuario_list(request):
    """Listado de usuarios con buscador."""
    denegado = _denegar_si_no_admin(request)
    if denegado:
        return denegado

    busqueda = request.GET.get('busqueda', '').strip()
    usuarios = User.objects.all()
    if busqueda:
        usuarios = usuarios.filter(
            Q(username__icontains=busqueda)
            | Q(first_name__icontains=busqueda)
            | Q(last_name__icontains=busqueda)
            | Q(email__icontains=busqueda)
        )

    contexto = {
        'usuarios': usuarios,
        'busqueda': busqueda,
        'total': User.objects.count(),
        'activos': User.objects.filter(is_active=True).count(),
        'admins': User.objects.filter(rol='ADMIN', is_active=True).count(),
    }
    return render(request, 'usuarios/list.html', contexto)


@login_required
def usuario_create(request):
    """Alta de usuario."""
    denegado = _denegar_si_no_admin(request)
    if denegado:
        return denegado

    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            messages.success(request, f'Usuario «{usuario.username}» creado correctamente.')
            return redirect('usuarios:list')
        messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = UsuarioForm(initial={'rol': 'OPERARIO', 'is_active': True, 'puede_eliminar': True})

    return render(request, 'usuarios/form.html', {'form': form, 'action': 'crear'})


@login_required
def usuario_update(request, pk):
    """Edición de usuario (la contraseña se cambia solo si se rellena)."""
    denegado = _denegar_si_no_admin(request)
    if denegado:
        return denegado

    usuario = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, f'Usuario «{usuario.username}» actualizado.')
            return redirect('usuarios:list')
        messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = UsuarioForm(instance=usuario)

    return render(request, 'usuarios/form.html', {
        'form': form,
        'action': 'editar',
        'usuario': usuario,
    })


@login_required
def usuario_toggle(request, pk):
    """Activa o desactiva una cuenta. Solo por POST."""
    denegado = _denegar_si_no_admin(request)
    if denegado:
        return denegado

    if request.method != 'POST':
        return redirect('usuarios:list')

    usuario = get_object_or_404(User, pk=pk)

    if usuario.pk == request.user.pk:
        messages.error(request, 'No puede desactivar su propia cuenta.')
        return redirect('usuarios:list')

    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=['is_active'])
    estado = 'activada' if usuario.is_active else 'desactivada'
    messages.success(request, f'Cuenta de «{usuario.username}» {estado}.')
    return redirect('usuarios:list')


@login_required
def usuario_unlock(request, pk):
    """Desbloquea una cuenta bloqueada por intentos fallidos."""
    denegado = _denegar_si_no_admin(request)
    if denegado:
        return denegado

    if request.method != 'POST':
        return redirect('usuarios:list')

    usuario = get_object_or_404(User, pk=pk)
    usuario.unlock_account()
    messages.success(request, f'Cuenta de «{usuario.username}» desbloqueada.')
    return redirect('usuarios:list')
