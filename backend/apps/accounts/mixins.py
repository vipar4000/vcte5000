from django.contrib import admin
from .models import User


class UserRolesMixin:
    """Mixin para filtrar usuarios por rol en formularios."""
    
    def get_operarios(self):
        return User.objects.filter(rol='OPERARIO', is_active=True)
    
    def get_vendedores(self):
        return User.objects.filter(rol='VENDEDOR', is_active=True)
