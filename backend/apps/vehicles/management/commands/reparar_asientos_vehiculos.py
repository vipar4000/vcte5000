"""Detecta y repara asientos de compra de vehículo duplicados en la 310.

Si un vehículo tiene más de un asiento POSTEADO de tipo `CompraVehiculo`, su
coste aparece dos veces en la cuenta 310 (y el pago, dos veces en banco).

Con `--corregir`:
  1. Anula **con contrapartida** todos los asientos de compra de ese vehículo
     (Ley Antifraude: no se borran).
  2. Compensa en banco los movimientos EGRESO vinculados (movimiento contrario).
  3. Genera un asiento nuevo por el `coste_inicial` actual y su movimiento.

Después, ejecute `reparar_capitalizacion_ot` para capitalizar las OT
completadas. El resultado correcto es:

    310 = coste_inicial del coche + coste de sus OT capitalizadas
    300 = materiales comprados - materiales consumidos en las OT

Uso:
    python manage.py reparar_asientos_vehiculos --dry-run
    python manage.py reparar_asientos_vehiculos --corregir
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounting.models import AsientoContable, MovimientoContable
from apps.accounting.views import generar_numero_asiento
from apps.bank.models import BancoMovimiento
from apps.bank.services import crear_movimiento_banco
from apps.vehicles.models import Vehiculo


class Command(BaseCommand):
    help = 'Detecta y corrige asientos de compra de vehículo duplicados.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--corregir', action='store_true',
            help='Aplica la corrección (sin esta opción solo informa).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Igual que sin --corregir: solo muestra el diagnóstico.',
        )

    def handle(self, *args, **opciones):
        corregir = opciones['corregir'] and not opciones['dry_run']

        problemas = []
        for vehiculo in Vehiculo.objects.order_by('matricula'):
            asientos = list(
                AsientoContable.objects.filter(
                    tipo_documento='CompraVehiculo',
                    documento_id=vehiculo.pk,
                ).exclude(estado='ANULADO').order_by('pk')
            )
            if len(asientos) <= 1:
                continue

            total_310 = Decimal('0')
            for asiento in asientos:
                total_310 += sum(
                    (m.debe - m.haber for m in asiento.movimientos.all()
                     if m.cuenta.codigo.startswith('310')),
                    Decimal('0'),
                )
            problemas.append((vehiculo, asientos, total_310))

        if not problemas:
            self.stdout.write(self.style.SUCCESS(
                'No hay asientos de compra duplicados. Todo correcto.'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'Vehículos con asiento de compra duplicado: {len(problemas)}'
        ))
        for vehiculo, asientos, total_310 in problemas:
            self.stdout.write(
                f'\n  {vehiculo.matricula} ({vehiculo.marca} {vehiculo.modelo}) '
                f'coste_inicial={vehiculo.coste_inicial:.2f} €'
            )
            for asiento in asientos:
                self.stdout.write(
                    f'    asiento #{asiento.numero} · {asiento.fecha} · '
                    f'{asiento.concepto}'
                )
            self.stdout.write(
                f'    total en 310 por estos asientos: {total_310:.2f} €'
            )

            if not corregir:
                continue

            with transaction.atomic():
                for asiento in asientos:
                    # Compensar el banco (no se borran movimientos)
                    for movimiento in BancoMovimiento.objects.filter(
                        asiento_asociado=asiento
                    ):
                        crear_movimiento_banco(
                            banco_cuenta=movimiento.banco_cuenta,
                            fecha=movimiento.fecha,
                            concepto=f'Anulación asiento duplicado: {movimiento.concepto}',
                            tipo='INGRESO' if movimiento.tipo == 'EGRESO' else 'EGRESO',
                            importe=movimiento.importe,
                            notas='Corrección de asiento de compra duplicado',
                        )

                    reversion = AsientoContable.objects.create(
                        numero=generar_numero_asiento(),
                        fecha=asiento.fecha,
                        concepto=f'ANULACIÓN: {asiento.concepto}',
                        estado='BORRADOR',
                        tipo_documento='AnulacionVehiculo',
                        documento_id=vehiculo.pk,
                        created_by=asiento.created_by,
                    )
                    for movimiento in asiento.movimientos.all():
                        MovimientoContable.objects.create(
                            asiento=reversion,
                            cuenta=movimiento.cuenta,
                            debe=movimiento.haber,
                            haber=movimiento.debe,
                            descripcion=f'Reversión: {movimiento.descripcion}',
                        )
                    # Documental: no se postea (el original queda ANULADO y
                    # deja de contar en los saldos).
                    asiento.estado = 'ANULADO'
                    asiento.save(update_fields=['estado'])

                vehiculo.asiento_contable = None
                vehiculo.save(update_fields=['asiento_contable'])
                nuevo = vehiculo.crear_asiento_contable()
                vehiculo.registrar_movimiento_banco(asiento=nuevo)

            self.stdout.write(self.style.SUCCESS(
                f'    corregido: asiento nuevo #{nuevo.numero} por '
                f'{vehiculo.coste_inicial:.2f} €'
            ))

        if not corregir:
            self.stdout.write(
                '\nNo se ha cambiado nada. Para corregir: '
                'repita con --corregir.'
            )
        else:
            self.stdout.write(self.style.SUCCESS(
                '\nListo. Ejecute ahora "reparar_capitalizacion_ot" para '
                'capitalizar las OT completadas.'
            ))
