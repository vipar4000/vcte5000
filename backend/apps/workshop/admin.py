from django.contrib import admin
from .models import OrdenTrabajo, Material, MaterialUsado


class MaterialUsadoInline(admin.TabularInline):
    model = MaterialUsado
    extra = 1
    fields = ['material', 'cantidad', 'subtotal']
    readonly_fields = ['subtotal']


@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'vehiculo', 'operario', 'titulo', 'estado',
        'horas_reales', 'coste_mano_obra', 'coste_materiales', 'coste_total'
    ]
    list_filter = ['estado', 'operario', 'fecha_inicio']
    search_fields = ['titulo', 'vehiculo__matricula', 'vehiculo__marca']
    inlines = [MaterialUsadoInline]
    readonly_fields = ['coste_mano_obra', 'coste_materiales', 'coste_total']
    
    def coste_mano_obra(self, obj):
        return f"€{obj.coste_mano_obra:,.2f}"
    coste_mano_obra.short_description = 'Mano de Obra'
    
    def coste_materiales(self, obj):
        return f"€{obj.coste_materiales:,.2f}"
    coste_materiales.short_description = 'Materiales'
    
    def coste_total(self, obj):
        return f"€{obj.coste_total:,.2f}"
    coste_total.short_description = 'Total'


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = [
        'nombre', 'stock_actual', 'stock_minimo', 
        'precio_unitario', 'alerta_stock'
    ]
    list_filter = ['alerta_stock', 'unidad']
    search_fields = ['nombre']
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('nombre')
