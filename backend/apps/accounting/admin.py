from django.contrib import admin
from .models import CuentaContable, AsientoContable, MovimientoContable


class MovimientoContableInline(admin.TabularInline):
    model = MovimientoContable
    extra = 2
    fields = ['cuenta', 'debe', 'haber', 'descripcion']


@admin.register(CuentaContable)
class CuentaContableAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'tipo', 'saldo', 'activa']
    list_filter = ['tipo', 'activa']
    search_fields = ['codigo', 'nombre']


@admin.register(AsientoContable)
class AsientoContableAdmin(admin.ModelAdmin):
    list_display = [
        'numero', 'fecha', 'concepto', 'estado',
        'total_debe', 'total_haber', 'esta_cuadrado'
    ]
    list_filter = ['estado', 'fecha']
    search_fields = ['numero', 'concepto']
    inlines = [MovimientoContableInline]
    
    def esta_cuadrado(self, obj):
        return obj.esta_cuadrado
    esta_cuadrado.boolean = True
    esta_cuadrado.short_description = 'Cuadrado'
