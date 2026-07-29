import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
django.setup()

from apps.expenses.models import InversionInicial
from apps.accounting.models import AsientoContable
from apps.bank.models import BancoCuenta, BancoMovimiento
from apps.bank.services import crear_movimiento_banco

inversion = InversionInicial.objects.first()

if not inversion:
    print('No hay inversiones registradas.')
    sys.exit(1)

asiento = AsientoContable.objects.filter(
    tipo_documento='InversionInicial',
    documento_id=inversion.pk
).first()

if not asiento:
    print(f'Inversion {inversion} no tiene asiento contable.')
    sys.exit(1)

mov_existente = BancoMovimiento.objects.filter(asiento_asociado=asiento).first()
if mov_existente:
    print(f'Inversion {inversion} ya tiene BancoMovimiento: {mov_existente}')
    print('No es necesario ejecutar el fix.')
    sys.exit(0)

banco_cuenta = BancoCuenta.objects.filter(
    cuenta_contable=inversion.forma_pago
).first()

if not banco_cuenta:
    from apps.bank.services import obtener_cuenta_banco_default
    banco_cuenta = obtener_cuenta_banco_default()
    if not banco_cuenta:
        print('No hay cuenta bancaria disponible.')
        sys.exit(1)

try:
    movimiento = crear_movimiento_banco(
        banco_cuenta=banco_cuenta,
        fecha=inversion.fecha_emision,
        concepto=f"Inversión inicial {inversion.numero_factura}: {inversion.proveedor_acreedor}",
        tipo='EGRESO',
        importe=inversion.total_calculado,
        asiento=asiento,
    )
    print(f'OK: BancoMovimiento creado: {movimiento}')
    print(f'    Cuenta: {banco_cuenta.nombre}')
    print(f'    Importe: {inversion.total_calculado} EUR')
    print(f'    Asiento: #{asiento.numero}')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
