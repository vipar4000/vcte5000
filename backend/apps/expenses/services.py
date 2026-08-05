from decimal import Decimal
from django.db.models import Sum


def transferir_coste_garantia(venta, descripcion, costo_repuestos, costo_mano_obra):
    """Transfiere costes de reparación en garantía como gasto del ejercicio (Cuenta 629/607)."""
    from apps.expenses.models import GastoEstructura
    from apps.accounts.models import User

    total = Decimal(str(costo_repuestos)) + Decimal(str(costo_mano_obra))
    if total <= 0:
        return None

    admin_user = User.objects.filter(is_admin=True).first()
    if not admin_user:
        return None

    gasto = GastoEstructura.objects.create(
        fecha_factura=venta.fecha_venta,
        proveedor_acreedor=f"Garantía - {venta.vehiculo}",
        cif_nif=venta.cliente_dni,
        categoria='LIMPIEZA_SERV',
        base_imponible=total,
        tipo_iva=Decimal('21.00'),
        retencion_irpf=Decimal('0.00'),
        pagado=False,
        created_by=admin_user,
    )

    try:
        asiento = gasto.crear_asiento_contable()
        return {'gasto': gasto, 'asiento': asiento}
    except Exception:
        return {'gasto': gasto, 'asiento': None}
