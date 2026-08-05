from decimal import Decimal
from django.db.models import Sum


def generar_nomina_mensual():
    """Genera una nómina mensual para cada operario con ConfiguracionNomina activa.
    
    Calcula salario bruto, SS patronal, SS obrera (~4.7%), retención IRPF estimada,
    y líquido a percibir. Crea un registro NominaEstructura por empleado y su
    correspondiente asiento contable.
    """
    from apps.attendance.models import ConfiguracionNomina
    from apps.payroll.models import NominaEstructura
    from apps.accounts.models import User
    from django.utils import timezone

    nominas_config = ConfiguracionNomina.objects.select_related('operario').all()
    hoy = timezone.now().date()

    admin_user = User.objects.filter(is_admin=True).first()
    if not admin_user:
        return {'status': 'error', 'error': 'No hay usuario administrador configurado'}

    resultados = []

    for config in nominas_config:
        operario = config.operario
        salario_bruto = config.salario_base_mensual

        if not salario_bruto or salario_bruto <= 0:
            continue

        ss_patronal = (salario_bruto * (config.porcentaje_ss_patronal / Decimal('100'))).quantize(Decimal('0.01'))
        ss_obrera = (salario_bruto * Decimal('0.047')).quantize(Decimal('0.01'))
        retencion_irpf = (salario_bruto * Decimal('0.06')).quantize(Decimal('0.01'))

        nomina = NominaEstructura.objects.create(
            empleado=operario,
            fecha_nomina=hoy,
            salario_bruto=salario_bruto,
            ss_patronal=ss_patronal,
            retencion_irpf=retencion_irpf,
            ss_obrera=ss_obrera,
            created_by=admin_user,
        )

        try:
            asiento = nomina.crear_asiento_contable()
            resultados.append({'nomina': nomina.pk, 'empleado': str(operario), 'asiento': asiento.numero})
        except Exception as e:
            resultados.append({'nomina': nomina.pk, 'empleado': str(operario), 'error': str(e)})

    return {'status': 'ok', 'generadas': len(resultados), 'detalle': resultados}
