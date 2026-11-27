"""Regulariza la cuenta 310 (Mercaderías) vehículo a vehículo.

Compara lo que hay contabilizado en 310 con lo que debería haber:

    vehículo vendido (venta activa)  -> 0
    vehículo en stock               -> coste_inicial + OTs capitalizadas (posteadas)

Si hay diferencia (por ejemplo, un asiento de compra re-posteado después de
vender el coche), con `--corregir` se crea un asiento de regularización:

    sobra inventario (310 de más) -> DEBE 610 / HABER 310
    falta inventario (310 de menos) -> DEBE 310 / HABER 610

Es el mismo criterio que el PGC para la variación de existencias, y deja el
informe de Valoración de Existencias cuadrado con el saldo contable.

Uso:
    python manage.py regularizar_inventario_vehiculos --dry-run
    python manage.py regularizar_inventario_vehiculos --corregir
    python manage.py regularizar_inventario_vehiculos --matricula 1234ABC
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import (
    AsientoContable, CuentaContable, MovimientoContable,
)
from apps.accounting.views import generar_numero_asiento
from apps.vehicles.models import Vehiculo


class Command(BaseCommand):
    help = 'Cuadra la cuenta 310 con el inventario real de vehículos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--corregir', action='store_true',
            help='Crea los asientos de regularización (sin esta opción solo informa).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Igual que sin --corregir: solo muestra el diagnóstico.',
        )
        parser.add_argument(
            '--matricula', default='',
            help='Limita el proceso a una matrícula concreta.',
        )
        parser.add_argument(
            '--diagnostico', action='store_true',
            help='Muestra qué asientos suman en las cuentas 300-330.',
        )

    def _en_310(self, asientos):
        """Suma del debe-haber en cuentas 31x de los asientos indicados."""
        total = Decimal('0')
        for asiento in asientos:
            total += sum(
                (m.debe - m.haber for m in asiento.movimientos.all()
                 if m.cuenta.codigo.startswith('31')),
                Decimal('0'),
            )
        return total


    def _diagnostico(self):
        """Detalle de lo que suma en 300-330, agrupado por tipo de asiento."""
        from django.db.models import Sum

        from apps.accounting.models import MovimientoContable

        self.stdout.write('\nDiagnóstico de las cuentas 300-330 '
                          '(asientos POSTEADOS):')
        movimientos = MovimientoContable.objects.filter(
            cuenta__codigo__in=['300', '310', '320', '330'],
            asiento__estado='POSTEADO',
        ).select_related('asiento', 'cuenta').order_by('asiento__fecha', 'asiento__pk')

        por_tipo = {}
        for m in movimientos:
            clave = (m.asiento.tipo_documento or '(sin tipo)', m.cuenta.codigo)
            datos = por_tipo.setdefault(clave, {'debe': Decimal('0'),
                                                'haber': Decimal('0'),
                                                'n': 0, 'saldo': Decimal('0')})
            datos['debe'] += m.debe
            datos['haber'] += m.haber
            datos['n'] += 1
            datos['saldo'] += m.debe - m.haber

        for (tipo, cuenta), datos in sorted(por_tipo.items()):
            self.stdout.write(
                f'  {tipo:<28} {cuenta}  debe={datos["debe"]:>12,.2f}  '
                f'haber={datos["haber"]:>12,.2f}  saldo={datos["saldo"]:>12,.2f}'
                f'  ({datos["n"]} mov.)'
            )

        self.stdout.write('\nAsientos con importe en 300-330 que no son de '
                          'compra, venta ni OT:')
        for m in movimientos.exclude(
            asiento__tipo_documento__in=[
                'CompraVehiculo', 'VentaVehiculo', 'OrdenTrabajo',
                'RegularizacionInventario',
            ]
        ):
            self.stdout.write(
                f'  #{m.asiento.numero} {m.asiento.fecha} '
                f'{m.asiento.tipo_documento or "(sin tipo)"} · '
                f'{m.cuenta.codigo} {m.debe - m.haber:,.2f} € · '
                f'{m.asiento.concepto[:60]}'
            )

    def _cuentas_existencias(self):
        from apps.accounting.models import MovimientoContable

        movimientos = MovimientoContable.objects.filter(
            cuenta__codigo__in=['300', '310', '320', '330'],
            asiento__estado='POSTEADO',
        )
        total = Decimal('0')
        for m in movimientos:
            total += m.debe - m.haber
        return total

    def _valor_inventario(self):
        from apps.accounting.reports import obtener_valor_existencias

        datos = obtener_valor_existencias()
        return datos['total_valor']

    def _regularizar_global(self, corregir):
        """Cuadra el total de 300-330 con el valor del inventario.

        Primero anula las contrapartidas de anulación que se postearon por
        error (devuelven el coste a la 310 y descuadran). Si aun así queda
        diferencia, crea un asiento de regularización contra 610.
        """
        from apps.accounting.models import AsientoContable, CuentaContable, MovimientoContable
        from apps.accounting.views import generar_numero_asiento
        from apps.accounts.models import User

        saldo = self._cuentas_existencias()
        valor = self._valor_inventario()
        diferencia = saldo - valor
        self.stdout.write(
            f'\nComprobación global: saldo 300-330 = {saldo:,.2f} € · '
            f'inventario = {valor:,.2f} € · diferencia = {diferencia:,.2f} €'
        )
        if diferencia.quantize(Decimal('0.01')) == 0:
            return 0

        sospechosos = list(
            AsientoContable.objects.filter(
                estado='POSTEADO',
                tipo_documento__startswith='Anulacion',
            ).distinct()
        )
        sospechosos = [
            a for a in sospechosos
            if any(m.cuenta.codigo.startswith(('30', '31', '32', '33'))
                   for m in a.movimientos.all())
        ]

        if not corregir:
            self.stdout.write(
                f'  contrapartidas de anulación posteadas con existencias: '
                f'{len(sospechosos)}'
            )
            for a in sospechosos:
                self.stdout.write(
                    f'    #{a.numero} {a.fecha} {a.tipo_documento} · {a.concepto[:60]}'
                )
            self.stdout.write(
                '\nNo se ha cambiado nada. Para corregir: repita con --corregir.'
            )
            return 0

        usuario = User.objects.filter(rol='ADMIN').first()
        ajustes = 0
        for asiento in sospechosos:
            asiento.estado = 'ANULADO'
            asiento.save(update_fields=['estado'])
            ajustes += 1
            self.stdout.write(self.style.SUCCESS(
                f'  anulada la contrapartida #{asiento.numero} '
                f'({asiento.tipo_documento})'
            ))

        saldo = self._cuentas_existencias()
        diferencia = saldo - valor
        if diferencia.quantize(Decimal('0.01')) == 0 or usuario is None:
            return ajustes

        # Ajuste final contra variación de existencias
        cuenta_310 = CuentaContable.objects.get(codigo='310')
        cuenta_610 = CuentaContable.objects.get(codigo='610')
        asiento = AsientoContable.objects.create(
            numero=generar_numero_asiento(),
            fecha=timezone.localdate(),
            concepto='Regularización global de existencias (300-330)',
            estado='BORRADOR',
            tipo_documento='RegularizacionInventario',
            documento_id=0,
            created_by=usuario,
        )
        if diferencia > 0:
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_610, debe=diferencia, haber=Decimal('0'),
                descripcion='Variación de existencias (regularización)',
            )
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_310, debe=Decimal('0'), haber=diferencia,
                descripcion='Ajuste de inventario',
            )
        else:
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_310, debe=-diferencia, haber=Decimal('0'),
                descripcion='Ajuste de inventario',
            )
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_610, debe=Decimal('0'), haber=-diferencia,
                descripcion='Variación de existencias (regularización)',
            )
        if asiento.esta_cuadrado:
            asiento.estado = 'POSTEADO'
            asiento.save(update_fields=['estado'])
        self.stdout.write(self.style.SUCCESS(
            f'  regularización global por {diferencia:,.2f} €'
        ))
        return ajustes + 1

    def handle(self, *args, **opciones):
        corregir = opciones['corregir'] and not opciones['dry_run']
        vehiculos = Vehiculo.objects.order_by('matricula')
        if opciones['matricula']:
            vehiculos = vehiculos.filter(matricula__iexact=opciones['matricula'])

        from apps.accounts.models import User
        from apps.workshop.models import OrdenTrabajo

        usuario = User.objects.filter(rol='ADMIN').first()
        if usuario is None:
            self.stderr.write(self.style.ERROR(
                'No hay ningún usuario ADMIN para firmar los asientos.'
            ))
            return

        ajustes = 0
        revisados = 0

        for vehiculo in vehiculos:
            venta_activa = vehiculo.ventas.filter(anulada=False).first()
            ots = OrdenTrabajo.objects.filter(vehiculo=vehiculo)

            asientos = list(
                AsientoContable.objects.filter(
                    tipo_documento='CompraVehiculo', documento_id=vehiculo.pk,
                    estado='POSTEADO',
                )
            )
            asientos += list(
                AsientoContable.objects.filter(
                    tipo_documento='OrdenTrabajo',
                    documento_id__in=ots.values_list('pk', flat=True),
                    estado='POSTEADO',
                )
            )
            asientos += list(
                AsientoContable.objects.filter(
                    tipo_documento='VentaVehiculo',
                    documento_id__in=vehiculo.ventas.values_list('pk', flat=True),
                    estado='POSTEADO',
                )
            )

            actual = self._en_310(asientos)

            if venta_activa:
                esperado = Decimal('0')
            else:
                ots_posteadas = set(
                    AsientoContable.objects.filter(
                        tipo_documento='OrdenTrabajo',
                        documento_id__in=ots.values_list('pk', flat=True),
                        estado='POSTEADO',
                    ).values_list('documento_id', flat=True)
                )
                capitalizado = sum(
                    (ot.coste_total for ot in ots if ot.pk in ots_posteadas),
                    Decimal('0'),
                )
                esperado = vehiculo.coste_inicial + capitalizado

            diferencia = actual - esperado
            revisados += 1
            if diferencia.quantize(Decimal('0.01')) == 0:
                continue

            self.stdout.write(
                f'\n  {vehiculo.matricula} · {"VENDIDO" if venta_activa else "EN STOCK"} '
                f'· 310 actual={actual:.2f} € · esperado={esperado:.2f} € '
                f'· diferencia={diferencia:.2f} €'
            )

            if not corregir:
                continue

            with transaction.atomic():
                cuenta_310 = CuentaContable.objects.get(codigo='310')
                cuenta_610 = CuentaContable.objects.get(codigo='610')
                asiento = AsientoContable.objects.create(
                    numero=generar_numero_asiento(),
                    fecha=timezone.localdate(),
                    concepto=(
                        f'Regularización inventario {vehiculo.matricula} '
                        f'({vehiculo.marca} {vehiculo.modelo})'
                    ),
                    estado='BORRADOR',
                    tipo_documento='RegularizacionInventario',
                    documento_id=vehiculo.pk,
                    created_by=usuario,
                )
                if diferencia > 0:
                    # Hay de más en 310: se da de baja contra variación
                    MovimientoContable.objects.create(
                        asiento=asiento, cuenta=cuenta_610,
                        debe=diferencia, haber=Decimal('0'),
                        descripcion='Variación de existencias (regularización)',
                    )
                    MovimientoContable.objects.create(
                        asiento=asiento, cuenta=cuenta_310,
                        debe=Decimal('0'), haber=diferencia,
                        descripcion=f'Sale de inventario {vehiculo.matricula}',
                    )
                else:
                    MovimientoContable.objects.create(
                        asiento=asiento, cuenta=cuenta_310,
                        debe=-diferencia, haber=Decimal('0'),
                        descripcion=f'Entra en inventario {vehiculo.matricula}',
                    )
                    MovimientoContable.objects.create(
                        asiento=asiento, cuenta=cuenta_610,
                        debe=Decimal('0'), haber=-diferencia,
                        descripcion='Variación de existencias (regularización)',
                    )
                if asiento.esta_cuadrado:
                    asiento.estado = 'POSTEADO'
                    asiento.save(update_fields=['estado'])
            ajustes += 1
            self.stdout.write(self.style.SUCCESS(
                f'    regularizado: {diferencia:.2f} €'
            ))

        if opciones['diagnostico']:
            self._diagnostico()

        # Pasada global: la 310 puede tener importes que no cuelgan de ningún
        # vehículo (típicamente contrapartidas de anulación posteadas por error).
        ajustes += self._regularizar_global(corregir)

        if not ajustes:
            self.stdout.write(self.style.SUCCESS(
                f'Revisados {revisados} vehículos: la 310 está correcta.'
            ))
        elif not corregir:
            self.stdout.write(
                '\nNo se ha cambiado nada. Para corregir: '
                'repita con --corregir.'
            )
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n{ajustes} vehículo(s) regularizado(s). Vuelva a abrir la '
                f'Valoración de Existencias.'
            ))
