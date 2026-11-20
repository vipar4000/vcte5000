"""Corrige los importes de compra de un vehículo y regenera su asiento.

Pensado para deshacer el daño del antiguo fallo que multiplicaba los importes
por 10.000 al guardar el formulario técnico (7.500 → 750.000 → 75.000.000).
Los asientos no se borran: se anulan con su contrapartida (Ley Antifraude) y se
registra uno nuevo con los importes correctos.

Ejemplo:
    python manage.py corregir_coste_vehiculo 1234ABC \
        --precio-subasta 7500 --tasas 400 --grua 250
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounting.models import AsientoContable, MovimientoContable
from apps.accounting.views import generar_numero_asiento
from apps.bank.models import BancoMovimiento
from apps.vehicles.models import Vehiculo


class Command(BaseCommand):
    help = 'Corrige los importes de compra de un vehículo y regenera su asiento.'

    def add_arguments(self, parser):
        parser.add_argument('matricula', help='Matrícula del vehículo.')
        parser.add_argument(
            '--precio-subasta', required=True,
            help='Precio de adjudicación correcto (acepta 7.500,00 o 7500.00).',
        )
        parser.add_argument('--tasas', required=True, help='Tasas de sala correctas.')
        parser.add_argument('--grua', required=True, help='Logística/grúa correctas.')
        parser.add_argument(
            '--tipo-iva', default=None,
            help='IVA soportado correcto (si no se indica, se conserva).',
        )
        parser.add_argument(
            '--sin-asiento', action='store_true',
            help='Solo corrige los importes, sin tocar el asiento contable.',
        )

    def handle(self, *args, **opciones):
        from apps.vehicles.forms import parsear_importe

        matricula = opciones['matricula'].strip().upper()
        vehiculo = Vehiculo.objects.filter(matricula__iexact=matricula).first()
        if not vehiculo:
            raise CommandError(f'No existe ningún vehículo con matrícula {matricula}.')

        precio = parsear_importe(opciones['precio_subasta'])
        tasas = parsear_importe(opciones['tasas'])
        grua = parsear_importe(opciones['grua'])
        tipo_iva = (
            parsear_importe(opciones['tipo_iva'])
            if opciones['tipo_iva'] is not None else vehiculo.tipo_iva
        )
        if None in (precio, tasas, grua, tipo_iva):
            raise CommandError('Los importes deben ser números.')

        anteriores = (
            vehiculo.precio_subasta, vehiculo.tasas_sala,
            vehiculo.logistica_grua, vehiculo.tipo_iva,
        )

        with transaction.atomic():
            asiento_viejo = vehiculo.asiento_contable
            if asiento_viejo and not opciones['sin_asiento']:
                self._anular(vehiculo, asiento_viejo)
                vehiculo.asiento_contable = None

            vehiculo.precio_subasta = precio
            vehiculo.tasas_sala = tasas
            vehiculo.logistica_grua = grua
            vehiculo.tipo_iva = tipo_iva
            vehiculo.save()

            if asiento_viejo and not opciones['sin_asiento']:
                asiento = vehiculo.crear_asiento_contable()
                BancoMovimiento.objects.filter(vehiculo_asociado=vehiculo).delete()
                vehiculo.registrar_movimiento_banco(asiento=asiento)
                self.stdout.write(self.style.SUCCESS(
                    f'Asiento #{asiento.numero} regenerado y posteado.'
                ))

        self.stdout.write(
            f'{matricula}: {anteriores[0]} → {vehiculo.precio_subasta} | '
            f'{anteriores[1]} → {vehiculo.tasas_sala} | '
            f'{anteriores[2]} → {vehiculo.logistica_grua} | '
            f'coste inicial {vehiculo.coste_inicial}'
        )
        self.stdout.write(self.style.SUCCESS('Vehículo corregido.'))

    def _anular(self, vehiculo, asiento):
        """Anula el asiento con contrapartida y elimina su movimiento bancario."""
        BancoMovimiento.objects.filter(asiento_asociado=asiento).delete()

        reversion = AsientoContable.objects.create(
            numero=generar_numero_asiento(),
            fecha=date.today(),
            concepto=f'ANULACIÓN: {asiento.concepto}',
            estado='BORRADOR',
            tipo_documento='AnulacionVehiculo',
            documento_id=asiento.documento_id,
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
        asiento.estado = 'ANULADO'
        asiento.save(update_fields=['estado'])
        self.stdout.write(
            f'Asiento #{asiento.numero} anulado con contrapartida '
            f'(#{reversion.numero}).'
        )
