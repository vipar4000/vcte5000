from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        'username', 'email', 'get_full_name', 'rol', 
        'is_active', 'is_locked', 'date_joined'
    ]
    list_filter = ['rol', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('R Car Rogil', {
            'fields': (
                'rol', 'movil', 'pin_kiosco',
                'salario_base_mensual', 'porcentaje_ss_patronal',
                'requires_password_change', 'failed_login_attempts', 'locked_until'
            )
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('R Car Rogil', {
            'fields': ('email', 'rol', 'movil')
        }),
    )
    
    def is_locked(self, obj):
        if obj.is_locked:
            return format_html('<span style="color: red;">🔒 Bloqueado</span>')
        return format_html('<span style="color: green;">✅ Activo</span>')
    is_locked.short_description = 'Estado'
    
    def get_rol_display(self, obj):
        return obj.get_rol_display()
    get_rol_display.short_description = 'Rol'
