from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from .models import User


def login_view(request):
    """Vista de login personalizada."""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = request.POST.get('next') or request.GET.get('next')
        
        # Verificar si el usuario existe
        try:
            user_obj = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, 'Usuario no encontrado.')
            return render(request, 'accounts/login.html', {'next': next_url})
        
        # Verificar si está bloqueado
        if user_obj.is_locked:
            messages.error(
                request, 
                'Cuenta bloqueada. Intente de nuevo en 1 hora.'
            )
            return render(request, 'accounts/login.html', {'next': next_url})
        
        # Autenticar
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            user.reset_failed_attempts()
            # Auto-reparar rol vacio en cuentas de personal (creadas via createsuperuser)
            if user.is_staff and not user.rol:
                user.rol = 'ADMIN'
                user.save(update_fields=['rol'])
            login(request, user)
            messages.success(request, f'Bienvenido {user.get_full_name() or user.username}')
            
            # Redirigir a next si es seguro, sino segun rol
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            
            if user.is_operario:
                return redirect('attendance:kiosco')
            elif user.is_vendedor:
                return redirect('sales:list')
            else:
                return redirect('home')
        else:
            user_obj.increment_failed_attempts()
            remaining = 5 - user_obj.failed_login_attempts
            if remaining > 0:
                messages.error(
                    request, 
                    f'Contraseña incorrecta. {remaining} intentos restantes.'
                )
            else:
                messages.error(
                    request, 
                    'Cuenta bloqueada tras 5 intentos fallidos.'
                )
    
    next_url = request.GET.get('next')
    return render(request, 'accounts/login.html', {'next': next_url})


@login_required
def logout_view(request):
    """Vista de logout."""
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    """Vista de perfil de usuario."""
    return render(request, 'accounts/profile.html', {
        'user': request.user
    })
