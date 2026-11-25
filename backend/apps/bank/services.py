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
def validar_saldo_egreso(banco_cuenta, fecha, importe):
    """Impide pagar con dinero que la cuenta aún no tenía en esa fecha.

    Raises:
        ValidationError: con el texto que se muestra en rojo al usuario.
    """
    from apps.core.formatting import format_euros

    disponible = banco_cuenta.saldo_a_fecha(fecha)
    if importe > disponible:
        raise ValidationError(
            'Saldo insuficiente en la cuenta bancaria en la fecha indicada '
            f'(Saldo disponible: {format_euros(disponible)}). '
            'Registre primero el ingreso/depósito. '
            f'Cuenta: {banco_cuenta.nombre}, fecha {fecha:%d/%m/%Y}.'
        )


def obtener_cuenta_tesoreria(codigo):
    """Cuenta de tesorería activa para un código contable: 570 caja o 572 banco."""
    from .models import BancoCuenta

    return (
        BancoCuenta.objects.filter(
            activa=True, cuenta_contable__codigo__startswith=codigo
        )
        .select_related('cuenta_contable')
        .first()
    )


def cuenta_banco_para_pago(cuenta_contable=None):
    """Cuenta de tesorería con la que se paga: la de la forma de pago o la de defecto.

    Si la forma de pago es la caja (570), devuelve la caja; si no existe, None
    (no se cae a una cuenta bancaria: el dinero sale del cajón, no del banco).
    """
    from .models import BancoCuenta

    if cuenta_contable is not None:
        if cuenta_contable.codigo.startswith('570'):
            return obtener_cuenta_tesoreria('570')
        cuenta = BancoCuenta.objects.filter(
            cuenta_contable=cuenta_contable
        ).first()
        return cuenta or obtener_cuenta_banco_default()

    return obtener_cuenta_banco_default()


@transaction.atomic
def crear_movimiento_banco(banco_cuenta, fecha, concepto, tipo, importe,
                            asiento=None, vehiculo=None, notas=''):
    """
    Crea un movimiento bancario y lo vincula a un asiento contable.

    Prohibido insertar movimientos de banco manuales — solo vía servicios.

    La función abre **su propia transacción**: el `select_for_update()` de la
    cuenta necesita estar dentro de una (en PostgreSQL, fuera de una
    transacción lanza `TransactionManagementError`, que era el 500 al crear
    una cuenta bancaria con depósito inicial desde una vista sin atomic).
    """
    from .models import BancoMovimiento, BancoCuenta

    banco_cuenta = BancoCuenta.objects.select_for_update().get(pk=banco_cuenta.pk)

    if tipo == 'EGRESO':
        validar_saldo_egreso(banco_cuenta, fecha, importe)

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
    """Cuenta de tesorería por defecto: primero banco (572), luego caja (570)."""
    from .models import BancoCuenta

    return (
        BancoCuenta.objects.filter(
            activa=True, cuenta_contable__codigo__startswith='572'
        ).first()
        or BancoCuenta.objects.filter(activa=True).first()
    )


# Margen de días para emparejar una línea del extracto con el movimiento del
# ERP: el banco puede reflejar una transferencia 1-3 días hábiles después.
DIAS_TOLERANCIA_CONCILIACION = 3


def conciliar_extracto(banco_cuenta, rows):
    """
    Busca emparejamientos automáticos entre líneas del extracto bancario
    y movimientos del ERP.

    Algoritmo:
    1. Rango de fechas: ±3 días respecto a la fecha del banco (una
       transferencia puede aparecer en el extracto 1-3 días hábiles después).
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

        # Buscar candidatos: mismo tipo e importe exacto, fecha ±3 días
        fecha_min = bank_fecha - timedelta(days=DIAS_TOLERANCIA_CONCILIACION)
        fecha_max = bank_fecha + timedelta(days=DIAS_TOLERANCIA_CONCILIACION)

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


def generar_pdf_factura_reserva(factura):
    """Genera el PDF de la factura de entrega a cuenta y lo guarda.

    Reutiliza el motor de PDF del ERP (WeasyPrint o xhtml2pdf) y el
    almacenamiento configurado (disco local o S3/R2), igual que las facturas
    REBU de venta.
    """
    from django.template.loader import render_to_string

    from apps.sales.services import EMPRESA, _guardar_en_storage, _render_pdf

    contexto = {
        'factura': factura,
        'reserva': factura.reserva,
        'vehiculo': factura.reserva.vehiculo,
        'empresa': EMPRESA,
    }
    html = render_to_string('bank/factura_reserva.html', contexto)
    pdf_bytes = _render_pdf(html)

    ruta = f'reservas/facturas/{factura.codigo}.pdf'
    _guardar_en_storage(ruta, pdf_bytes)
    if factura.pdf.name != ruta:
        factura.pdf.name = ruta
        factura.save(update_fields=['pdf'])

    return pdf_bytes


@transaction.atomic
def crear_traspaso_tesoreria(origen, destino, fecha, importe, concepto='',
                             soporte=None, user=None):
    """Traspaso real de efectivo entre dos cuentas de tesorería.

    - Asiento único: DEBE cuenta destino / HABER cuenta origen.
    - EGRESO en la cuenta de origen (validando su saldo) e INGRESO en la de
      destino, ambos vinculados al asiento.
    - El soporte (resguardo de retirada) se adjunta a los dos movimientos.
    """
    from datetime import date

    from django.core.files.uploadedfile import UploadedFile

    from apps.accounting.models import (
        AsientoContable, MovimientoContable,
    )
    from apps.accounting.views import generar_numero_asiento

    from .models import BancoMovimiento

    if origen.pk == destino.pk:
        raise ValueError('La cuenta de origen y la de destino deben ser distintas.')

    importe = Decimal(str(importe)).quantize(Decimal('0.01'))
    if importe <= 0:
        raise ValueError('El importe del traspaso debe ser mayor que cero.')

    fecha = fecha or date.today()
    concepto = (concepto or 'Traspaso de tesorería').strip()
    texto = f'{concepto}: {origen.nombre} → {destino.nombre}'

    asiento = AsientoContable.objects.create(
        numero=generar_numero_asiento(),
        fecha=fecha,
        concepto=texto,
        estado='BORRADOR',
        tipo_documento='TraspasoTesoreria',
        created_by=user,
    )
    MovimientoContable.objects.create(
        asiento=asiento, cuenta=destino.cuenta_contable,
        debe=importe, haber=Decimal('0'),
        descripcion=f'Entrada de efectivo desde {origen.nombre}',
    )
    MovimientoContable.objects.create(
        asiento=asiento, cuenta=origen.cuenta_contable,
        debe=Decimal('0'), haber=importe,
        descripcion=f'Salida de efectivo hacia {destino.nombre}',
    )
    if asiento.esta_cuadrado:
        asiento.estado = 'POSTEADO'
        asiento.save(update_fields=['estado'])

    salida = crear_movimiento_banco(
        banco_cuenta=origen,
        fecha=fecha,
        concepto=texto,
        tipo='EGRESO',
        importe=importe,
        asiento=asiento,
        notas='Traspaso de tesorería (salida)',
    )
    entrada = crear_movimiento_banco(
        banco_cuenta=destino,
        fecha=fecha,
        concepto=texto,
        tipo='INGRESO',
        importe=importe,
        asiento=asiento,
        notas='Traspaso de tesorería (entrada)',
    )

    if soporte is not None:
        for movimiento in (salida, entrada):
            if isinstance(soporte, UploadedFile):
                movimiento.soporte.save(soporte.name, soporte, save=True)
            else:
                movimiento.soporte = soporte
                movimiento.save(update_fields=['soporte'])

    return asiento
