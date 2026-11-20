"""Cálculo de nóminas proporcionales a la periodicidad del trabajador.

La ficha laboral (Usuario) guarda el salario base **mensual** y los porcentajes
de SS patronal, SS obrera e IRPF. Aquí se reparte el salario según su
periodicidad:

    Mensual   → 30 días (importe íntegro)
    Quincenal → 15 días (la mitad)
    Semanal   →  7 días (7/30 del mes)

Los porcentajes se aplican sobre el bruto del periodo, de forma que la suma de
los pagos del mes coincide con el bruto mensual.
"""
from decimal import Decimal

from django.utils import timezone

DIAS_PERIODO = {'MENSUAL': 30, 'QUINCENAL': 15, 'SEMANAL': 7}

CERO = Decimal('0')


def _pct(base, porcentaje):
    # Tolerante a float/str (fixtures, importaciones)
    porcentaje = Decimal(str(porcentaje if porcentaje is not None else 0))
    return (base * porcentaje / Decimal('100')).quantize(Decimal('0.01'))


def importes_para_periodo(empleado, periodo=None):
    """Devuelve los importes de una nómina del periodo indicado.

    Args:
        empleado: User con la ficha laboral (salario y porcentajes).
        periodo: 'MENSUAL' | 'QUINCENAL' | 'SEMANAL'. Si no se indica, se usa
                 la periodicidad de pago del trabajador.

    Returns:
        dict con salario_bruto, ss_patronal, ss_obrera, retencion_irpf,
        liquido y periodo.
    """
    periodo = periodo or getattr(empleado, 'periodicidad_pago', None) or 'MENSUAL'
    if periodo not in DIAS_PERIODO:
        periodo = 'MENSUAL'

    dias = Decimal(DIAS_PERIODO[periodo])
    factor = dias / Decimal('30')

    mensual = Decimal(str(empleado.salario_base_mensual or 0))
    bruto = (mensual * factor).quantize(Decimal('0.01'))

    ss_patronal = _pct(bruto, empleado.porcentaje_ss_patronal)
    ss_obrera = _pct(bruto, getattr(empleado, 'porcentaje_ss_obrera', CERO))
    irpf = _pct(bruto, getattr(empleado, 'porcentaje_irpf', CERO))
    liquido = (bruto - ss_obrera - irpf).quantize(Decimal('0.01'))

    return {
        'periodo': periodo,
        'salario_bruto': bruto,
        'ss_patronal': ss_patronal,
        'ss_obrera': ss_obrera,
        'retencion_irpf': irpf,
        'liquido': liquido,
    }


def _ya_generada(empleado, fecha, periodo):
    """¿Existe ya la nómina de este trabajador para ese periodo concreto?"""
    from apps.payroll.models import NominaEstructura

    nominas = NominaEstructura.objects.filter(
        empleado=empleado,
        periodo=periodo,
        fecha_nomina__year=fecha.year,
        fecha_nomina__month=fecha.month,
    )
    if periodo == 'QUINCENAL':
        # Primera quincena: días 1-15; segunda: 16 en adelante
        primera = fecha.day <= 15
        nominas = nominas.filter(fecha_nomina__day__lte=15) if primera else \
            nominas.filter(fecha_nomina__day__gt=15)
    elif periodo == 'SEMANAL':
        anio_iso, semana_iso, _ = fecha.isocalendar()
        nominas = nominas.filter(
            fecha_nomina__iso_year=anio_iso,
            fecha_nomina__week=semana_iso,
        )
    return nominas.exists()


def generar_nominas_del_periodo(fecha=None):
    """Genera una nómina por trabajador activo, según su periodicidad.

    Incluye las fichas sin acceso (obreros, limpieza, auxiliares). No duplica:
    si ese trabajador ya tiene la nómina del periodo, se salta.
    """
    from apps.accounts.models import User
    from apps.payroll.models import NominaEstructura

    fecha = fecha or timezone.localdate()

    admin = User.objects.filter(rol='ADMIN', is_active=True).first()
    if not admin:
        return {'status': 'error', 'error': 'No hay usuario administrador configurado'}

    trabajadores = User.objects.filter(
        is_active=True, salario_base_mensual__gt=0,
    ).order_by('first_name', 'last_name')

    generadas, saltadas, errores = [], [], []

    for trabajador in trabajadores:
        periodo = trabajador.periodicidad_pago or 'MENSUAL'
        if _ya_generada(trabajador, fecha, periodo):
            saltadas.append(trabajador.pk)
            continue

        importes = importes_para_periodo(trabajador, periodo)
        if importes['salario_bruto'] <= 0:
            continue

        nomina = NominaEstructura.objects.create(
            empleado=trabajador,
            fecha_nomina=fecha,
            periodo=periodo,
            salario_bruto=importes['salario_bruto'],
            ss_patronal=importes['ss_patronal'],
            retencion_irpf=importes['retencion_irpf'],
            ss_obrera=importes['ss_obrera'],
            created_by=admin,
        )

        try:
            asiento = nomina.crear_asiento_contable()
            generadas.append({
                'nomina': nomina.pk,
                'empleado': str(trabajador),
                'periodo': periodo,
                'asiento': asiento.numero,
            })
        except Exception as error:  # pragma: no cover - defensivo
            errores.append({'nomina': nomina.pk, 'empleado': str(trabajador), 'error': str(error)})

    return {
        'status': 'ok',
        'generadas': len(generadas),
        'saltadas': len(saltadas),
        'errores': errores,
        'detalle': generadas,
    }


def generar_nomina_mensual():
    """Compatibilidad: genera las nóminas del periodo actual."""
    return generar_nominas_del_periodo()
