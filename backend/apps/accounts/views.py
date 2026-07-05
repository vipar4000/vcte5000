from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import User


def login_view(request):
    """Vista de login personalizada."""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Verificar si el usuario existe
        try:
            user_obj = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, 'Usuario no encontrado.')
            return render(request, 'accounts/login.html')
        
        # Verificar si está bloqueado
        if user_obj.is_locked:
            messages.error(
                request, 
                'Cuenta bloqueada. Intente de nuevo en 1 hora.'
            )
            return render(request, 'accounts/login.html')
        
        # Autenticar
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            user.reset_failed_attempts()
            login(request, user)
            messages.success(request, f'Bienvenido {user.get_full_name() or user.username}')
            
            # Redirigir según rol
            if user.is_admin:
                return redirect('admin:index')
            elif user.is_operario:
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
    
    return render(request, 'accounts/login.html')


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
