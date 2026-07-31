"""Create test materials + multi-material purchase for pipeline testing."""
import os
import sys
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import django
django.setup()

from django.contrib.auth import get_user_model
from django.test.utils import setup_test_environment
from apps.workshop.models import Material, CompraMaterial
from apps.accounting.models import AsientoContable

User = get_user_model()

admin = User.objects.get(username='admin')

# 1. Create catalog materials
aceite, _ = Material.objects.get_or_create(
    nombre='Aceite motor 5W30',
    defaults=dict(
        descripcion='Aceite de motor sintético 5W30',
        unidad='L',
        stock_actual=0,
        stock_minimo=10,
        precio_unitario=Decimal('4.50'),
    ),
)
pastillas, _ = Material.objects.get_or_create(
    nombre='Pastillas de freno',
    defaults=dict(
        descripcion='Pastillas de freno delanteras',
        unidad='ud',
        stock_actual=0,
        stock_minimo=5,
        precio_unitario=Decimal('18.00'),
    ),
)
filtro, _ = Material.objects.get_or_create(
    nombre='Filtro de aceite',
    defaults=dict(
        descripcion='Filtro de aceite estándar',
        unidad='ud',
        stock_actual=15,
        stock_minimo=5,
        precio_unitario=Decimal('8.50'),
    ),
)

print(f'Materials ready: {Material.objects.count()} in catalog')

# 2. Create multi-material purchase (same invoice, 2 lines)
invoice_num = 'FAC-PRUEBA-001'
if CompraMaterial.objects.filter(numero_factura=invoice_num).exists():
    print(f'Purchase for invoice {invoice_num} already exists, skipping.')
else:
    from django.db import transaction

    lineas_data = [
        dict(material=aceite, cantidad=Decimal('20.00'), precio_unitario=Decimal('4.50')),
        dict(material=pastillas, cantidad=Decimal('3.00'), precio_unitario=Decimal('18.00')),
    ]

    with transaction.atomic():
        for ld in lineas_data:
            compra = CompraMaterial(
                material=ld['material'],
                cantidad=ld['cantidad'],
                precio_unitario=ld['precio_unitario'],
                proveedor='Distribuciones Auto S.L.',
                cif_nif='B87654321',
                fecha_compra='2026-07-30',
                numero_factura=invoice_num,
                tipo_inventario='300',
                tipo_iva=Decimal('21.00'),
                created_by=admin,
            )
            compra.save()
            asiento = compra.crear_asiento_contable()
            if asiento.esta_cuadrado:
                asiento.estado = 'POSTEADO'
                asiento.save()
                print(f'  [OK] {compra.material.nombre} x{compra.cantidad} — asiento #{asiento.numero} posteado')
            else:
                print(f'  [FAIL] {compra.material.nombre} — asiento no cuadrado')

    print(f'\nPurchase invoice {invoice_num} created: {len(lineas_data)} lines')

# 3. Summary
print('\n=== Stock summary ===')
for m in Material.objects.all().order_by('nombre'):
    print(f'  {m.nombre}: stock={m.stock_actual} {m.unidad}, precio={m.precio_unitario}€')
