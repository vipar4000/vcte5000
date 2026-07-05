from django.contrib import admin
from .models import GarantiaVehiculo, HistorialReparacionGarantia


@admin.register(GarantiaVehiculo)
class GarantiaVehiculoAdmin(admin.ModelAdmin):
    list_display = [
        'venta', 'tipo_cliente', 'fecha_inicio', 
        'fecha_fin', 'esta_vigente', 'meses_restantes'
    ]
    list_filter = ['tipo_cliente', 'fecha_inicio']
    search_fields = ['venta__vehiculo__matricula', 'venta__cliente_nombre']
    
    def esta_vigente(self, obj):
        return obj.esta_vigente
    esta_vigente.boolean = True
    esta_vigente.short_description = 'Vigente'


@admin.register(HistorialReparacionGarantia)
class HistorialReparacionGarantiaAdmin(admin.ModelAdmin):
    list_display = [
        'garantia', 'fecha_ingreso_taller', 'estado',
        'total_costo_reparacion', 'fecha_resolucion'
    ]
    list_filter = ['estado', 'fecha_ingreso_taller']
    readonly_fields = ['total_costo_reparacion']
