"""Protecciones de borrado: qué registros no se pueden eliminar y por qué.

Decisión de producción (prueba E2E, §6): en lugar de permitir borrados que
descuadren banco, contabilidad o stock, el sistema **bloquea** la eliminación
con un mensaje claro cuando el registro tiene una operación asociada.

Los movimientos de banco no se borran nunca: se compensan (H7).
"""
from apps.accounting.models import AsientoContable
from apps.bank.models import BancoMovimiento


def motivo_no_borrar_vehiculo(vehiculo):
    """Devuelve el motivo por el que no se puede borrar el vehículo, o None."""
    from apps.sales.models import VentaVehiculo

    if VentaVehiculo.objects.filter(vehiculo=vehiculo).exists():
        return (
            'No se puede eliminar un vehículo con una venta asociada. '
            'Anule primero la venta.'
        )
    if vehiculo.ordenes_trabajo.exists():
        return (
            'No se puede eliminar un vehículo con órdenes de trabajo. '
            'Elimine o anule antes sus OT.'
        )
    if vehiculo.asiento_contable_id:
        return (
            'No se puede eliminar un vehículo con asiento contable de compra. '
            'Anule antes su asiento de compra.'
        )
    if BancoMovimiento.objects.filter(vehiculo_asociado=vehiculo).exists():
        return (
            'No se puede eliminar un vehículo con un pago registrado en Banco. '
            'Anule antes el pago.'
        )
    return None


def motivo_no_borrar_gasto(gasto):
    """Gasto con asiento o pago: no se borra, se deshace el pago."""
    if gasto.pagado:
        return (
            'No se puede eliminar un gasto pagado. Deshaga primero el pago '
            'desde la ficha del gasto.'
        )
    if AsientoContable.objects.filter(
        tipo_documento__in=['GastoEstructura', 'PagoGastoEstructura'],
        documento_id=gasto.pk,
    ).exclude(estado='ANULADO').exists():
        return (
            'No se puede eliminar un gasto con asiento contable. '
            'Anule antes su asiento (Ley Antifraude: los asientos no se borran).'
        )
    return None


def motivo_no_borrar_ot(ot):
    """OT con materiales o capitalización contable: no se borra."""
    if ot.materiales_usados.exists():
        return (
            'No se puede eliminar una OT con materiales consumidos: el stock '
            'quedaría descuadrado. Anule antes su capitalización.'
        )
    if AsientoContable.objects.filter(
        tipo_documento='OrdenTrabajo', documento_id=ot.pk
    ).exclude(estado='ANULADO').exists():
        return (
            'No se puede eliminar una OT con asiento de capitalización. '
            'Anule antes el asiento.'
        )
    return None


def motivo_no_anular_asiento(asiento):
    """Un asiento vinculado a Banco no se anula: se compensa con un movimiento."""
    movimiento = BancoMovimiento.objects.filter(
        asiento_asociado=asiento
    ).first()
    if movimiento is None:
        return None
    return (
        f'No se puede anular el asiento {asiento.numero}: está vinculado al '
        f'movimiento de banco «{movimiento.concepto}» '
        f'({movimiento.importe:.2f} €). Los movimientos de banco no se borran: '
        f'registre el movimiento de compensación con el signo contrario.'
    )
