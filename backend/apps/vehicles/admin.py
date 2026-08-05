from django.contrib import admin
from django.utils.html import format_html
from .models import Vehiculo, ImagenVehiculo
from apps.sales.models import VentaVehiculo
from apps.core.formatting import format_euros


class ImagenVehiculoInline(admin.TabularInline):
    model = ImagenVehiculo
    extra = 1
    max_num = 8
    fields = ['imagen', 'es_principal', 'orden']


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = [
        'matricula', 'marca', 'modelo', 'anio', 'estado',
        'coste_inicial_display', 'dias_en_inventario', 'created_at', 'detalle_link'
    ]
    list_filter = ['estado', 'marca', 'anio', 'combustible', 'tipo_dano']
    search_fields = ['matricula', 'bastidor', 'marca', 'modelo']
    readonly_fields = ['coste_inicial', 'coste_total_adquisicion', 'cuota_iva', 'created_at', 'updated_at', 'detalle_link', 'documentos_venta']
    inlines = [ImagenVehiculoInline]
    
    fieldsets = (
        ('Datos Técnicos', {
            'fields': (
                'matricula', 'bastidor', 'marca', 'modelo', 'anio',
                'combustible', 'kilometraje', 'tipo_dano', 'etiqueta_ambiental'
            )
        }),
        ('Estado', {
            'fields': ('estado', 'fecha_adquisicion', 'plataforma_subasta', 'detalle_link')
        }),
        ('Costes de Adquisición', {
            'fields': (
                'precio_subasta', 'tasas_sala', 'logistica_grua', 'coste_inicial'
            )
        }),
        ('Factura de Compra', {
            'fields': (
                'proveedor', 'cif_nif', 'numero_factura', 'factura_compra_pdf',
                'tipo_iva', 'coste_total_adquisicion', 'cuota_iva', 'forma_pago',
            )
        }),
        ('Precio de Venta', {
            'fields': ('precio_venta',)
        }),
        ('Descripción', {
            'fields': ('descripcion_dano',)
        }),
        ('Imágenes', {
            'fields': ('imagen_principal',)
        }),
        ('Auditoría', {
            'fields': ('created_by', 'created_at', 'updated_at', 'asiento_contable'),
            'classes': ('collapse',)
        }),
        ('Documentos de Venta', {
            'fields': ('documentos_venta',),
            'classes': ('collapse',)
        }),
    )
    
    def coste_inicial_display(self, obj):
        return format_euros(obj.coste_inicial)
    coste_inicial_display.short_description = 'Coste Inicial'
    
    def detalle_link(self, obj):
        if obj.pk:
            return format_html(
                '<a href="/vehiculos/{}/" target="_blank">🔍 Ver detalle en ERP</a>',
                obj.pk
            )
        return '-'
    detalle_link.short_description = 'Detalle ERP'
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        for valor, nombre in Vehiculo.ESTADOS:
            def make_action(estado_valor, estado_nombre):
                def action(modeladmin, request, queryset):
                    updated = queryset.update(estado=estado_valor)
                    modeladmin.message_user(
                        request,
                        f'{updated} vehículo(s) cambiado(s) a {estado_nombre}'
                    )
                action.short_description = f'Cambiar estado a: {estado_nombre}'
                action.__name__ = f'marcar_{estado_valor}'
                return action
            action = make_action(valor, nombre)
            actions[action.__name__] = (action, action.__name__, action.short_description)
        return actions
    
    def documentos_venta(self, obj):
        try:
            venta = obj.venta
        except VentaVehiculo.DoesNotExist:
            return '-'
        
        links = []
        if venta.contrato_pdf:
            links.append(f'<a href="{venta.contrato_pdf.url}" target="_blank">📄 Contrato</a>')
        else:
            links.append(f'<a href="/ventas/{venta.pk}/contrato/">➕ Generar Contrato</a>')
        
        if venta.mandato_pdf:
            links.append(f'<a href="{venta.mandato_pdf.url}" target="_blank">📄 Mandato</a>')
        else:
            links.append(f'<a href="/ventas/{venta.pk}/mandato/">➕ Generar Mandato</a>')
        
        return format_html(' &middot; '.join(links))
    documentos_venta.short_description = 'Documentos de Venta'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_admin:
            qs = qs.filter(estado__in=['EN_VENTA', 'VENDIDO'])
        return qs
