from django.contrib import admin
from .models import BancoCuenta, BancoMovimiento, Reserva


@admin.register(BancoCuenta)
class BancoCuentaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'iban', 'cuenta_contable', 'activa']
    list_filter = ['activa']
    search_fields = ['nombre', 'iban']


@admin.register(BancoMovimiento)
class BancoMovimientoAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'banco_cuenta', 'concepto', 'tipo', 'importe', 'conciliado']
    list_filter = ['tipo', 'conciliado', 'banco_cuenta']
    search_fields = ['concepto']
    date_hierarchy = 'fecha'


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ['vehiculo', 'cliente_nombre', 'fecha_reserva', 'importe_reserva', 'estado']
    list_filter = ['estado']
    search_fields = ['cliente_nombre', 'vehiculo__matricula']
