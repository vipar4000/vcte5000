"""Regulariza los anticipos de clientes (438) y las devoluciones de reservas.

Detecta reservas devueltas o penalizadas a las que les falta su asiento
contable (versiones anteriores solo creaban el movimiento de banco) y, con
`--corregir`, los crea y postea:

    devuelta    -> DEBE 438 / HABER 572 (o caja)
    penalizada  -> DEBE 438 / HABER 759

Después cuadra el saldo de la 438 con las reservas activas: si queda un
remanente que no corresponde a ningún anticipo vivo, lo lleva a 759.

Uso:
    python manage.py regularizar_reservas --dry-run
    python manage.py regularizar_reservas --corregir
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import (
    AsientoContable, CuentaContable, MovimientoContable,
)
from apps.accounting.views import generar_numero_asiento
from apps.bank.models import Reserva
from apps.bank.services import crear_asiento_devolucion_reserva


class Command(BaseCommand):
    help = 'Crea los asientos de devolución/penalización que falten y cuadra la 438.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--corregir', action='store_true',
            help='Aplica la corrección (sin esta opción solo informa).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Igual que sin --corregir: solo muestra el diagnóstico.',
        )

    def _saldo_438(self):
        debe, haber = Decimal('0'), Decimal('0')
        for movimiento in MovimientoContable.objects.filter(
            cuenta__codigo='438', asiento__estado='POSTEADO'
        ):
            debe += movimiento.debe
            haber += movimiento.haber
        return debe, haber

    def handle(self, *args, **opciones):
        corregir = opciones['corregir'] and not opciones['dry_run']

        pendientes = []
        for reserva in Reserva.objects.filter(
            estado__in=['DEVUELTA', 'PENALIZADA']
        ).order_by('pk'):
            tipo = (
                'PenalizacionReserva' if reserva.estado == 'PENALIZADA'
                else 'DevolucionReserva'
            )
            if AsientoContable.objects.filter(
                tipo_documento=tipo, documento_id=reserva.pk
            ).exclude(estado='ANULADO').exists():
                continue
            pendientes.append((reserva, tipo))

        if pendientes:
            self.stdout.write(self.style.WARNING(
                f'Reservas sin asiento de devolución/penalización: {len(pendientes)}'
            ))
            for reserva, tipo in pendientes:
                self.stdout.write(
                    f'  Reserva #{reserva.pk} · {reserva.estado} · '
                    f'{reserva.importe_reserva:.2f} € · {reserva.vehiculo} · '
                    f'{reserva.cliente_nombre}'
                )
        else:
            self.stdout.write('Todas las reservas devueltas/penalizadas tienen '
                              'su asiento.')

        debe, haber = self._saldo_438()
        activas = sum(
            (r.importe_reserva for r in Reserva.objects.filter(estado='ACTIVA')),
            Decimal('0'),
        )
        # La 438 es un activo: saldo deudor = debe - haber. Un anticipo vivo
        # la deja en negativo (acreedor) por el importe de la señal activa.
        saldo = debe - haber
        esperado = -activas
        self.stdout.write(
            f'\nSaldo 438 = {saldo:.2f} € · esperado (reservas activas) = '
            f'{esperado:.2f} € · diferencia = {saldo - esperado:.2f} €'
        )

        if not corregir:
            if pendientes or (saldo - esperado).quantize(Decimal('0.01')) != 0:
                self.stdout.write(
                    '\nNo se ha cambiado nada. Para corregir: '
                    'repita con --corregir.'
                )
            return

        with transaction.atomic():
            for reserva, tipo in pendientes:
                crear_asiento_devolucion_reserva(
                    reserva,
                    movimiento=reserva.banco_movimiento,
                )
                self.stdout.write(self.style.SUCCESS(
                    f'  asiento creado para la reserva #{reserva.pk} ({tipo})'
                ))

            debe, haber = self._saldo_438()
            saldo = debe - haber
            diferencia = saldo - esperado
            if diferencia.quantize(Decimal('0.01')) != 0:
                from apps.accounts.models import User

                usuario = User.objects.filter(rol='ADMIN').first()
                cuenta_438 = CuentaContable.objects.get(codigo='438')
                cuenta_otros = CuentaContable.objects.get(codigo='759')
                asiento = AsientoContable.objects.create(
                    numero=generar_numero_asiento(),
                    fecha=timezone.localdate(),
                    concepto='Regularización de anticipos de clientes (438)',
                    estado='BORRADOR',
                    tipo_documento='RegularizacionAnticipos',
                    documento_id=0,
                    created_by=usuario,
                )
                if diferencia < 0:
                    MovimientoContable.objects.create(
                        asiento=asiento, cuenta=cuenta_438,
                        debe=-diferencia, haber=Decimal('0'),
                        descripcion='Anticipo que ya no está vivo',
                    )
                    MovimientoContable.objects.create(
                        asiento=asiento, cuenta=cuenta_otros,
                        debe=Decimal('0'), haber=-diferencia,
                        descripcion='Regularización de anticipos',
                    )
                else:
                    MovimientoContable.objects.create(
                        asiento=asiento, cuenta=cuenta_otros,
                        debe=diferencia, haber=Decimal('0'),
                        descripcion='Regularización de anticipos',
                    )
                    MovimientoContable.objects.create(
                        asiento=asiento, cuenta=cuenta_438,
                        debe=Decimal('0'), haber=diferencia,
                        descripcion='Anticipo pendiente de contabilizar',
                    )
                if asiento.esta_cuadrado:
                    asiento.estado = 'POSTEADO'
                    asiento.save(update_fields=['estado'])
                self.stdout.write(self.style.SUCCESS(
                    f'  regularización de la 438 por {diferencia:.2f} €'
                ))

        self.stdout.write(self.style.SUCCESS(
            '\nListo. Abra el Balance de Situación y compruebe la ecuación.'
        ))
