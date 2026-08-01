"""
Servicios del módulo bancario.
Lógica de creación automatizada de movimientos y conciliación.
"""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from difflib import SequenceMatcher
import logging

from apps.core.formatting import format_euros

logger = logging.getLogger(__name__)


@transaction.atomic
def crear_movimiento_banco(banco_cuenta, fecha, concepto, tipo, importe,
                            asiento=None, vehiculo=None, notas=''):
    """
    Crea un movimiento bancario y lo vincula a un asiento contable.
    Prohibido insertar movimientos de banco manuales — solo vía servicios.
    """
    from .models import BancoMovimiento

    if tipo == 'EGRESO':
        disponible = banco_cuenta.saldo_pendiente
        if importe > disponible:
            raise ValidationError(
                f'Saldo insuficiente en {banco_cuenta.nombre}. '
                f'Disponible: {format_euros(disponible)}, solicitado: {format_euros(importe)}'
            )

    movimiento = BancoMovimiento.objects.create(
        banco_cuenta=banco_cuenta,
        fecha=fecha,
        concepto=concepto,
        tipo=tipo,
        importe=abs(importe),
        asiento_asociado=asiento,
        vehiculo_asociado=vehiculo,
        notas=notas,
    )
    logger.info(
        f'Movimiento bancario creado: {movimiento} '
        f'(cuenta={banco_cuenta}, asiento={asiento})'
    )
    return movimiento


def obtener_cuenta_banco_default():
    """Obtiene la cuenta bancaria activa por defecto."""
    from .models import BancoCuenta
    return BancoCuenta.objects.filter(activa=True).first()


def conciliar_extracto(banco_cuenta, rows):
    """
    Busca emparejamientos automáticos entre líneas del extracto bancario
    y movimientos del ERP.

    Algoritmo:
    1. Rango de fechas: ±2 días respecto a la fecha del banco.
    2. Dirección y monto: coincidencia exacta en tipo e importe.
    3. Mapeo de conceptos: scoring por similitud de texto.

    Args:
        banco_cuenta: BancoCuenta instance
        rows: list of dicts con keys [fecha, concepto, tipo, importe]

    Returns:
        list of dict: [
            {
                'bank_row': dict,
                'erp_match': BancoMovimiento or None,
                'confidence': float (0-1),
                'candidates': list of BancoMovimiento
            }
        ]
    """
    from datetime import timedelta
    from .models import BancoMovimiento

    resultados = []

    for row in rows:
        bank_fecha = row['fecha']
        bank_tipo = row['tipo'].upper()
        bank_importe = abs(Decimal(str(row['importe'])))
        bank_concepto = str(row.get('concepto', ''))

        # Buscar candidatos: mismo tipo, mismo importe, fecha ±2 días
        fecha_min = bank_fecha - timedelta(days=2)
        fecha_max = bank_fecha + timedelta(days=2)

        candidatos = BancoMovimiento.objects.filter(
            banco_cuenta=banco_cuenta,
            tipo=bank_tipo,
            importe=bank_importe,
            fecha__gte=fecha_min,
            fecha__lte=fecha_max,
            conciliado=False,
        )

        mejor_match = None
        mejor_score = 0.0

        for candidato in candidatos:
            score = _calcular_score_concepto(bank_concepto, candidato.concepto)
            if score > mejor_score:
                mejor_score = score
                mejor_match = candidato

        resultados.append({
            'bank_row': {
                'fecha': bank_fecha,
                'concepto': bank_concepto,
                'tipo': bank_tipo,
                'importe': bank_importe,
            },
            'erp_match': mejor_match,
            'confidence': mejor_score,
            'candidates': list(candidatos),
        })

    return resultados


def _calcular_score_concepto(concepto_banco, concepto_erp):
    """
    Calcula similitud entre conceptos de banco y ERP.
    Returns float entre 0 y 1.
    """
    if not concepto_banco or not concepto_erp:
        return 0.0

    # Normalizar: minúsculas, sin espacios extra
    b = concepto_banco.lower().strip()
    e = concepto_erp.lower().strip()

    # Coinidencia exacta
    if b == e:
        return 1.0

    # Uno contiene al otro
    if b in e or e in b:
        return 0.9

    # Ratio de secuencia
    return SequenceMatcher(None, b, e).ratio()


def conciliacion_bancaria_sugerencias(banco_cuenta, fecha_desde=None, fecha_hasta=None):
    """
    Genera sugerencias de conciliación para movimientos no conciliados.
    Útil para el dashboard de conciliación.
    """
    from .models import BancoMovimiento

    qs = BancoMovimiento.objects.filter(
        banco_cuenta=banco_cuenta,
        conciliado=False,
    )

    if fecha_desde:
        qs = qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__lte=fecha_hasta)

    return qs.order_by('fecha')


@transaction.atomic
def marcar_conciliado(movimiento_id, asiento=None):
    """Marca un movimiento como conciliado."""
    from .models import BancoMovimiento

    movimiento = BancoMovimiento.objects.select_for_update().get(pk=movimiento_id)
    movimiento.conciliado = True
    if asiento:
        movimiento.asiento_asociado = asiento
    movimiento.save(update_fields=['conciliado', 'asiento_asociado'])
    return movimiento


@transaction.atomic
def conciliacion_batch(movimientos_ids):
    """Concilia varios movimientos de una vez."""
    from .models import BancoMovimiento

    movimientos = BancoMovimiento.objects.filter(pk__in=movimientos_ids)
    count = movimientos.update(conciliado=True)
    logger.info(f'Conciliación batch: {count} movimientos marcados como conciliados')
    return count
