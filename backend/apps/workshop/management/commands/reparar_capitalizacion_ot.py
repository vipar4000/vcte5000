"""Postea las capitalizaciones de las OT que quedaron sin contabilizar.

Cuando una orden de trabajo termina con coste (mano de obra y materiales), su
asiento DEBE 310 / HABER 300 + 611 debe quedar **posteado**. Si se quedó en
BORRADOR (o no se generó), el valor del stock en el informe de existencias
supera al saldo contable: es la diferencia por mano de obra.

Este comando revisa las OT de los vehículos en stock y:
  - genera el asiento si no existe,
  - lo postea si está en BORRADOR y cuadra,
  - avisa si está descuadrado.

Uso:
    python manage.py reparar_capitalizacion_ot
    python manage.py reparar_capitalizacion_ot --dry-run
"""
from django.core.management.base import BaseCommand

from apps.accounting.models import AsientoContable
from apps.vehicles.models import Vehiculo
from apps.workshop.models import OrdenTrabajo


class Command(BaseCommand):
    help = 'Postea los asientos de capitalización de las OT pendientes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo muestra lo que haría, sin tocar la contabilidad.',
        )

    def handle(self, *args, **opciones):
        dry_run = opciones['dry_run']
        vehiculos = Vehiculo.objects.exclude(estado='VENDIDO')
        ots = OrdenTrabajo.objects.filter(vehiculo__in=vehiculos)

        creados = 0
        posteados = 0
        descuadrados = 0
        correctas = 0

        for ot in ots.select_related('vehiculo', 'operario'):
            if ot.coste_total <= 0:
                continue

            asiento = AsientoContable.objects.filter(
                tipo_documento='OrdenTrabajo', documento_id=ot.pk
            ).first()

            if asiento is None:
                if dry_run:
                    self.stdout.write(
                        f'  [crearía] OT-{ot.pk} ({ot.vehiculo.matricula}): '
                        f'{ot.coste_total:.2f} €'
                    )
                else:
                    ot.crear_asiento_contable()
                    creados += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  [OK] OT-{ot.pk} ({ot.vehiculo.matricula}): '
                            f'asiento creado y posteado por {ot.coste_total:.2f} €'
                        )
                    )
                continue

            if asiento.estado == 'POSTEADO':
                correctas += 1
                continue

            if not asiento.esta_cuadrado:
                descuadrados += 1
                self.stdout.write(self.style.WARNING(
                    f'  [AVISO] OT-{ot.pk}: el asiento #{asiento.numero} no '
                    f'cuadra (debe {asiento.total_debe:.2f} / '
                    f'haber {asiento.total_haber:.2f}). Revíselo a mano.'
                ))
                continue

            if dry_run:
                self.stdout.write(
                    f'  [postearía] OT-{ot.pk} ({ot.vehiculo.matricula}): '
                    f'asiento #{asiento.numero} por {asiento.total_debe:.2f} €'
                )
            else:
                asiento.estado = 'POSTEADO'
                asiento.save(update_fields=['estado'])
                posteados += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  [OK] OT-{ot.pk} ({ot.vehiculo.matricula}): '
                        f'asiento #{asiento.numero} posteado por {asiento.total_debe:.2f} €'
                    )
                )

        resumen = (
            f'\nOT revisadas: {ots.count()} · ya correctas: {correctas} · '
            f'creadas: {creados} · posteadas: {posteados} · '
            f'descuadradas: {descuadrados}'
        )
        if dry_run:
            resumen += '\n(dry-run: no se ha cambiado nada)'
        self.stdout.write(self.style.SUCCESS(resumen))
