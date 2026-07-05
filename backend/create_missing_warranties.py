"""
Script para crear garantías faltantes para ventas existentes.

Ejecutar desde backend/ con:
    DJANGO_SETTINGS_MODULE=config.settings.development python create_missing_warranties.py

O desde Django shell:
    exec(open('create_missing_warranties.py').read())
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from apps.sales.models import VentaVehiculo
from apps.warranty.models import GarantiaVehiculo


def create_missing_warranties():
    ventas = VentaVehiculo.objects.all()
    created = 0
    skipped = 0

    for venta in ventas:
        if hasattr(venta, 'garantia'):
            skipped += 1
            continue

        GarantiaVehiculo.objects.create(
            venta=venta,
            tipo_cliente=venta.tipo_cliente,
            fecha_inicio=venta.fecha_venta,
        )
        print(f'Garantía creada para venta #{venta.pk}: {venta.vehiculo} → {venta.cliente_nombre}')
        created += 1

    print(f'\nResumen: {created} garantías creadas, {skipped} ya existían')


if __name__ == '__main__':
    create_missing_warranties()
