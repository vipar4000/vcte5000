"""
Crea asientos contables retroactivos para movimientos bancarios de ingreso
que no tengan asiento asociado.
Ejecutar con: python manage.py backfill_asientos_banco
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal

from apps.bank.models import BancoMovimiento
from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable
from apps.accounting.views import generar_numero_asiento


class Command(BaseCommand):
    help = 'Crea asientos contables para movimientos de banco sin asiento asociado'

    def handle(self, *args, **options):
        from apps.accounts.models import User
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stdout.write(self.style.ERROR('No se encontró un usuario superuser'))
            return

        cuenta_banco = CuentaContable.objects.get(codigo='572')
        cuenta_resultados = CuentaContable.objects.get(codigo='110')

        movimientos = BancoMovimiento.objects.filter(
            tipo='INGRESO',
            asiento_asociado__isnull=True,
        )

        count = 0
        with transaction.atomic():
            for m in movimientos:
                asiento = AsientoContable.objects.create(
                    numero=generar_numero_asiento(),
                    fecha=m.fecha,
                    concepto=f'{m.concepto} - {m.banco_cuenta.nombre}',
                    estado='POSTEADO',
                    tipo_documento='Banco',
                    created_by=user,
                )

                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_banco,
                    debe=Decimal(str(m.importe)), haber=Decimal('0'),
                    descripcion=f'{m.concepto} {m.banco_cuenta.nombre}',
                )

                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_resultados,
                    debe=Decimal('0'), haber=Decimal(str(m.importe)),
                    descripcion=f'{m.concepto} {m.banco_cuenta.nombre}',
                )

                m.asiento_asociado = asiento
                m.save(update_fields=['asiento_asociado'])
                count += 1

        self.stdout.write(self.style.SUCCESS(
            f'{count} asiento(s) contable(s) creado(s) y posteeado(s).'
        ))
