"""
Comando de gestión para la regularización anual de existencias (PGC 300/610).
Ejecutar con: python manage.py regularizar_existencias --ano 2025
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from datetime import date

from apps.core.formatting import format_euros


class Command(BaseCommand):
    help = 'Regularización anual de existencias no vendidas (asiento 300/610)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ano', type=int, required=True,
            help='Año a regularizar (ej: 2025)',
        )

    def handle(self, *args, **options):
        ano = options['ano']
        resultado = regularizar_existencias_anual(ano)
        self.stdout.write(self.style.SUCCESS(resultado))


def regularizar_existencias_anual(ano):
    """
    Regularización de existencias al cierre de ejercicio.

    Asiento contable:
        DEBE  300 (Existencias / Mercaderías) → valor del stock no vendido
        HABER 610 (Variación de existencias)   → mismo importe

    Args:
        ano: int, año a regularizar

    Returns:
        str con el resultado de la operación
    """
    from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable
    from apps.accounting.views import generar_numero_asiento
    from apps.vehicles.models import Vehiculo
    from apps.accounts.models import User

    with transaction.atomic():
        # Obtener vehículos no vendidos comprados en o antes del año dado
        stock_no_vendido = Vehiculo.objects.filter(
            vendido=False,
            fecha_adquisicion__year__lte=ano,
        )

        valor_inventario = stock_no_vendido.aggregate(
            total=Decimal('0') if not stock_no_vendido.exists() else None
        )

        # Calcular valor total del inventario usando coste_inicial
        valor_total = Decimal('0')
        for vehiculo in stock_no_vendido:
            valor_total += vehiculo.coste_inicial

        if valor_total == 0:
            return (
                f'Regularización {ano}: sin stock no vendido, '
                f'se omite el asiento.'
            )

        # Verificar cuentas
        try:
            cuenta_300 = CuentaContable.objects.get(codigo='300')
            cuenta_610 = CuentaContable.objects.get(codigo='610')
        except CuentaContable.DoesNotExist as e:
            return (
                f'Error: falta la cuenta contable {e} en el plan. '
                f'Inicialice el plan en Contabilidad > Cuentas > Inicializar.'
            )

        # Buscar si ya existe un asiento de regularización para este año
        asiento_existente = AsientoContable.objects.filter(
            tipo_documento='RegularizacionExistencias',
            documento_id=ano,
        ).first()

        if asiento_existente:
            return (
                f'Regularización {ano}: ya existe el asiento '
                f'{asiento_existente.numero}. Se omite.'
            )

        # Obtener usuario admin
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            return 'Error: no hay usuario superuser disponible.'

        # Crear asiento
        asiento = AsientoContable.objects.create(
            numero=generar_numero_asiento(),
            fecha=date(ano, 12, 31),
            concepto=(
                f'Regularización existencias {ano} - '
                f'Stock no vendido: {format_euros(valor_total)} '
                f'({stock_no_vendido.count()} vehículos)'
            ),
            estado='BORRADOR',
            tipo_documento='RegularizacionExistencias',
            documento_id=ano,
            created_by=admin_user,
        )

        MovimientoContable.objects.create(
            asiento=asiento, cuenta=cuenta_300,
            debe=valor_total, haber=Decimal('0'),
            descripcion=f'Stock no vendido a 31/12/{ano}',
        )

        MovimientoContable.objects.create(
            asiento=asiento, cuenta=cuenta_610,
            debe=Decimal('0'), haber=valor_total,
            descripcion=f'Variación de existencias {ano}',
        )

        return (
            f'Regularización {ano}: asiento {asiento.numero} creado. '
            f'DEBE 300 / HABER 610 por {format_euros(valor_total)} '
            f'({stock_no_vendido.count()} vehículos en stock).'
        )
