"""Repara una venta registrada teniendo una reserva (señal) activa.

Antes del arreglo, `vents_create` ignoraba la reserva: se apuntaba un ingreso por
el precio completo y otro por la señal, y la reserva seguía «Activa».

Este comando:
1. Anula el asiento de la venta con contrapartida (Ley Antifraude).
2. Borra el ingreso bancario equivocado y crea el correcto (precio − señal).
3. Regenera el asiento aplicando el anticipo (cancela 438 y 477).
4. Marca la reserva como CONVERTIDA y la enlaza con la venta.

Uso:
    python manage.py reparar_venta_con_reserva --matricula 1234ABC
    python manage.py reparar_venta_con_reserva --venta 7
    python manage.py reparar_venta_con_reserva --todas [--dry-run]
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounting.models import AsientoContable, MovimientoContable
from apps.accounting.views import generar_numero_asiento
from apps.bank.models import BancoMovimiento, Reserva
from apps.sales.models import VentaVehiculo


class Command(BaseCommand):
    help = 'Corrige ventas con reserva activa: un solo cobro y anticipo aplicado.'

    def add_arguments(self, parser):
        parser.add_argument('--venta', type=int, help='PK de la venta')
        parser.add_argument('--matricula', help='Matrícula del vehículo')
        parser.add_argument(
            '--todas', action='store_true',
            help='Repara todas las ventas con reserva activa',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo muestra lo que haría, sin tocar nada',
        )

    def handle(self, *args, **opciones):
        ventas = self._resolver_ventas(opciones)

        if not ventas:
            self.stdout.write(self.style.WARNING('No hay ventas que reparar.'))
            return

        for venta in ventas:
            reserva = venta.vehiculo.reservas.filter(estado='ACTIVA').first()
            if not reserva:
                self.stdout.write(
                    f'Venta #{venta.pk}: no tiene reserva activa, se omite.'
                )
                continue

            if opciones['dry_run']:
                self.stdout.write(
                    f'[dry-run] Venta #{venta.pk} ({venta.vehiculo.matricula}): '
                    f'cobro pasaría a '
                    f'{venta.precio_venta - reserva.importe_reserva} € '
                    f'y la reserva #{reserva.pk} quedaría CONVERTIDA.'
                )
                continue

            with transaction.atomic():
                self._reparar(venta, reserva)

            self.stdout.write(self.style.SUCCESS(
                f'Venta #{venta.pk} ({venta.vehiculo.matricula}) reparada: '
                f'cobro de {venta.precio_venta - reserva.importe_reserva} € '
                f'y reserva #{reserva.pk} convertida.'
            ))

    def _resolver_ventas(self, opciones):
        if opciones['venta']:
            try:
                return [VentaVehiculo.objects.get(pk=opciones['venta'])]
            except VentaVehiculo.DoesNotExist:
                raise CommandError(f'No existe la venta #{opciones["venta"]}')

        if opciones['matricula']:
            ventas = list(VentaVehiculo.objects.filter(
                vehiculo__matricula__iexact=opciones['matricula']
            ))
            if not ventas:
                raise CommandError(
                    f'No hay venta para la matrícula {opciones["matricula"]}'
                )
            return ventas

        if opciones['todas']:
            return list(
                VentaVehiculo.objects
                .filter(vehiculo__reservas__estado='ACTIVA')
                .distinct()
            )

        raise CommandError(
            'Indique --venta, --matricula o --todas (use --dry-run para probar)'
        )

    def _reparar(self, venta, reserva):
        """Anula el asiento viejo y lo rehace con la señal aplicada."""
        user = reserva.created_by

        viejo = venta.asiento_contable
        if viejo:
            # 1) Contrapartida del asiento anterior (no se borra)
            reversion = AsientoContable.objects.create(
                numero=generar_numero_asiento(),
                fecha=date.today(),
                concepto=f'ANULACIÓN: {viejo.concepto}',
                estado='BORRADOR',
                tipo_documento='AnulacionVenta',
                documento_id=viejo.documento_id,
                created_by=user,
            )
            for movimiento in viejo.movimientos.all():
                MovimientoContable.objects.create(
                    asiento=reversion,
                    cuenta=movimiento.cuenta,
                    debe=movimiento.haber,
                    haber=movimiento.debe,
                    descripcion=f'Reversión: {movimiento.descripcion}',
                )
            viejo.estado = 'ANULADO'
            viejo.save(update_fields=['estado'])

            # 2) Fuera el ingreso equivocado de la venta
            BancoMovimiento.objects.filter(asiento_asociado=viejo).delete()
            venta.asiento_contable = None
            venta.save(update_fields=['asiento_contable'])

        # 3) Asiento nuevo con el anticipo aplicado y su cobro correcto
        anticipo = reserva.importe_reserva or Decimal('0')
        asiento = venta.crear_asiento_contable(anticipo=anticipo)
        venta.registrar_movimiento_banco(asiento=asiento, anticipo=anticipo)

        # 4) La reserva queda convertida y enlazada
        reserva.estado = 'CONVERTIDA'
        reserva.venta = venta
        reserva.save(update_fields=['estado', 'venta'])
