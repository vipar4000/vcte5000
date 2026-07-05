from django.contrib import admin
from .models import Marcaje, ConfiguracionNomina


@admin.register(Marcaje)
class MarcajeAdmin(admin.ModelAdmin):
    list_display = [
        'operario', 'tipo', 'fecha_hora', 'ip_address', 'validado'
    ]
    list_filter = ['tipo', 'fecha_hora', 'operario']
    search_fields = ['operario__username', 'operario__first_name']
    readonly_fields = ['ip_address', 'validado']


@admin.register(ConfiguracionNomina)
class ConfiguracionNominaAdmin(admin.ModelAdmin):
    list_display = [
        'operario', 'salario_base_mensual', 
        'porcentaje_ss_patronal', 'coste_hora'
    ]
    readonly_fields = ['coste_hora']
