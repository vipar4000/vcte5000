from django.contrib import admin
from django.utils.html import format_html
from .models import GastoEstructura


@admin.register(GastoEstructura)
class GastoEstructuraAdmin(admin.ModelAdmin):
    list_display = [
        'fecha_factura', 'proveedor_acreedor', 'cif_nif',
        'categoria', 'base_imponible', 'total_factura',
        'pagado_display',
    ]
    list_filter = ['categoria', 'pagado', 'fecha_factura']
    search_fields = ['proveedor_acreedor', 'cif_nif']
    readonly_fields = ['cuota_iva', 'cuota_retencion', 'total_factura', 'created_at', 'updated_at']

    fieldsets = (
        ('Datos de la Factura', {
            'fields': (
                'fecha_factura', 'proveedor_acreedor', 'cif_nif',
                'categoria', 'documento_pdf',
            )
        }),
        ('Importes', {
            'fields': (
                'base_imponible', 'tipo_iva', 'cuota_iva',
                'retencion_irpf', 'cuota_retencion', 'total_factura',
            )
        }),
        ('Pago', {
            'fields': ('pagado', 'fecha_pago'),
        }),
        ('Auditoría', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def pagado_display(self, obj):
        if obj.pagado:
            return format_html('<span style="color: green;">✅ Pagado</span>')
        return format_html('<span style="color: red;">❌ Pendiente</span>')
    pagado_display.short_description = 'Estado'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
