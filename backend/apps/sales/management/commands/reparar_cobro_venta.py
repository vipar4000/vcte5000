"""Repara una venta a la que le falta el ingreso en Banco.

Caso real (V-2): se registró la venta por transferencia y el INGRESO no llegó a
Banco (porque falló el asiento o no había cuenta activa en ese momento). La
venta y su asiento existen, pero el banco no refleja el cobro.

Este comando:
1. Comprueba si la venta ya tiene su INGRESO en banco (no duplica).
2. Calcula lo que falta por cobrar: precio de venta − señal de la reserva.
3. Crea el movimiento y lo enlaza al asiento de la venta.
4. Si la venta es financiada, no hace nada (no entra dinero en banco).

Uso:
    python manage.py reparar_cobro_venta --venta 2
    python manage.py reparar_cobro_venta --matricula 1234ABC
    python manage.py reparar_cobro_venta --todas [--dry-run]
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.bank.models import BancoMovimiento, Reserva
from apps.sales.models import VentaVehiculo


class Command(BaseCommand):
    help = 'Crea el ingreso en Banco que le falta a una venta.'

    def add_arguments(self, parser):
        parser.add_argument('--venta', type=int, help='PK de la venta')
        parser.add_argument('--matricula', help='Matrícula del vehículo')
        parser.add_argument(
            '--todas', action='store_true',
            help='Revisa todas las ventas no financiadas',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo muestra lo que haría, sin crear movimientos',
        )

    def handle(self, *args, **opciones):
        ventas = self._resolver_ventas(opciones)
        if not ventas:
            self.stdout.write(self.style.WARNING('No hay ventas que revisar.'))
            return

        reparadas = 0
        for venta in ventas:
            if venta.metodo_pago == 'FINANCIADO':
                self.stdout.write(
                    f'Venta #{venta.pk}: financiada, no debe tener ingreso en banco.'
                )
                continue

            if self._cobro_existente(venta):
                self.stdout.write(
                    f'Venta #{venta.pk} ({venta.vehiculo.matricula}): ya tiene su '
                    f'ingreso en banco, se omite.'
                )
                continue

            reserva = Reserva.objects.filter(
                venta=venta, estado='CONVERTIDA'
            ).first() or Reserva.objects.filter(
                vehiculo=venta.vehiculo, estado='CONVERTIDA'
            ).first()
            anticipo = (
                reserva.importe_reserva if reserva else Decimal('0')
            )
            importe = venta.precio_venta - anticipo

            if importe <= 0:
                self.stdout.write(
                    f'Venta #{venta.pk}: la señal cubre el precio, no hay nada que cobrar.'
                )
                continue

            if opciones['dry_run']:
                self.stdout.write(
                    f'[dry-run] Venta #{venta.pk} ({venta.vehiculo.matricula}): '
                    f'crearía un INGRESO de {importe} € '
                    f'({venta.precio_venta} − señal {anticipo}).'
                )
                continue

            try:
                with transaction.atomic():
                    movimiento = venta.registrar_movimiento_banco(
                        asiento=venta.asiento_contable, anticipo=anticipo
                    )
            except Exception as error:
                self.stderr.write(self.style.ERROR(
                    f'Venta #{venta.pk}: no se pudo crear el ingreso: {error}'
                ))
                continue

            if movimiento is None:
                self.stdout.write(
                    f'Venta #{venta.pk}: no se creó movimiento (revisar cuenta bancaria).'
                )
                continue

            reparadas += 1
            self.stdout.write(self.style.SUCCESS(
                f'Venta #{venta.pk} ({venta.vehiculo.matricula}) reparada: '
                f'INGRESO de {importe} € en {movimiento.banco_cuenta.nombre}.'
            ))

        if reparadas:
            self.stdout.write(self.style.SUCCESS(
                f'\n{reparadas} venta(s) reparada(s).'
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
                VentaVehiculo.objects.select_related('vehiculo')
                .exclude(metodo_pago='FINANCIADO')
            )

        raise CommandError(
            'Indique --venta, --matricula o --todas (use --dry-run para probar)'
        )

    def _cobro_existente(self, venta):
        """¿Ya hay un INGRESO de la venta? (no duplicar al reparar)."""
        return BancoMovimiento.objects.filter(
            vehiculo_asociado=venta.vehiculo,
            tipo='INGRESO',
            concepto__startswith='Cobro venta',
        ).exists()
