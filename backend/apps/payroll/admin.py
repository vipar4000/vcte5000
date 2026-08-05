from django.contrib import admin
from .models import NominaEstructura


@admin.register(NominaEstructura)
class NominaEstructuraAdmin(admin.ModelAdmin):
    list_display = [
        'empleado', 'fecha_nomina', 'salario_bruto',
        'ss_patronal', 'liquido_percibir', 'created_at',
    ]
    list_filter = ['fecha_nomina', 'empleado']
    search_fields = ['empleado__username', 'empleado__first_name', 'empleado__last_name']
    readonly_fields = ['liquido_percibir', 'asiento_contable', 'created_at', 'updated_at']
    date_hierarchy = 'fecha_nomina'
