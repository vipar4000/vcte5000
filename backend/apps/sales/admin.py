from django.contrib import admin
from django.utils.html import format_html
from .models import VentaVehiculo
from apps.warranty.models import GarantiaVehiculo


@admin.register(VentaVehiculo)
class VentaVehiculoAdmin(admin.ModelAdmin):
    list_display = [
        'vehiculo', 'cliente_nombre', 'fecha_venta', 
        'precio_venta', 'beneficio_display', 'tiene_contrato'
    ]
    list_filter = ['fecha_venta', 'metodo_pago', 'tipo_cliente']
    search_fields = [
        'vehiculo__matricula', 'cliente_nombre', 
        'cliente_dni', 'cliente_email'
    ]
    readonly_fields = [
        'coste_total', 'base_imponible', 'cuota_iva', 
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Vehículo', {
            'fields': ('vehiculo', 'fecha_venta', 'metodo_pago')
        }),
        ('Cliente', {
            'fields': (
                'tipo_cliente', 'cliente_nombre', 'cliente_dni',
                'cliente_direccion', 'cliente_poblacion', 
                'cliente_provincia', 'cliente_cp',
                'cliente_telefono', 'cliente_email'
            )
        }),
        ('Precios e IVA', {
            'fields': (
                'precio_venta', 'coste_total', 'margen_porcentaje',
                'base_imponible', 'cuota_iva'
            )
        }),
        ('Documentos', {
            'fields': ('contrato_pdf', 'mandato_pdf'),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def beneficio_display(self, obj):
        beneficio = obj.beneficio
        color = 'green' if beneficio > 0 else 'red'
        return format_html(
            '<span style="color: {};">€{}</span>',
            color, f'{beneficio:,.2f}'
        )
    beneficio_display.short_description = 'Beneficio'
    
    def tiene_contrato(self, obj):
        if obj.contrato_pdf:
            return format_html('✅')
        return format_html('❌')
    tiene_contrato.short_description = 'Contrato'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        vehiculo = obj.vehiculo
        obj.coste_total = vehiculo.coste_total

        if obj.coste_total and obj.coste_total > 0:
            obj.margen_porcentaje = (
                (obj.precio_venta - obj.coste_total) / obj.coste_total * 100
            )

        super().save_model(request, obj, form, change)

        # Cambiar estado del vehículo a VENDIDO
        vehiculo.estado = 'VENDIDO'
        vehiculo.save()
        
        # Crear garantía automáticamente solo al crear
        if not change:
            GarantiaVehiculo.objects.create(
                venta=obj,
                tipo_cliente=obj.tipo_cliente,
                fecha_inicio=obj.fecha_venta,
            )
            
            # Crear asiento contable automáticamente
            try:
                obj.crear_asiento_contable()
            except Exception:
                pass
