"""
Vistas de exportación fiscal.
Descarga de archivos BOE, CSV, SII.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from datetime import date


@login_required
def exportar_modelo_390(request):
    """Genera y descarga el fichero plano del Modelo 390."""
    anio = int(request.GET.get('anio', date.today().year))
    
    try:
        from .exports import generar_modelo_390
        contenido = generar_modelo_390(anio)
        
        response = HttpResponse(contenido, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="Modelo390_{anio}.txt"'
        return response
    except Exception as e:
        messages.error(request, f'Error al generar Modelo 390: {str(e)}')
        return redirect('accounting:informes')


@login_required
def exportar_csv_303(request):
    """Genera y descarga el CSV para pre-declaración Modelo 303."""
    anio = int(request.GET.get('anio', date.today().year))
    trimestre = int(request.GET.get('trimestre', (date.today().month - 1) // 3 + 1))
    
    try:
        from .exports import generar_csv_pre303
        contenido = generar_csv_pre303(anio, trimestre)
        
        response = HttpResponse(contenido, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="Modelo303_T{trimestre}_{anio}.csv"'
        return response
    except Exception as e:
        messages.error(request, f'Error al generar CSV 303: {str(e)}')
        return redirect('accounting:iva')


@login_required
def exportar_sii_xml(request):
    """Genera y descarga el XML del SII."""
    anio = int(request.GET.get('anio', date.today().year))
    trimestre = int(request.GET.get('trimestre', (date.today().month - 1) // 3 + 1))
    
    try:
        from .exports import generar_sii_xml
        contenido = generar_sii_xml(anio, trimestre)
        
        response = HttpResponse(contenido, content_type='application/xml; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="SII_{anio}T{trimestre}.xml"'
        return response
    except Exception as e:
        messages.error(request, f'Error al generar SII: {str(e)}')
        return redirect('accounting:informes')


@login_required
def tareas_programadas(request):
    """Panel de tareas Celery Beat programadas."""
    from django_celery_beat.models import PeriodicTask
    
    tareas = PeriodicTask.objects.all()
    
    context = {
        'tareas': tareas,
    }
    return render(request, 'accounting/tareas_programadas.html', context)


@login_required
def crear_tareas_por_defecto(request):
    """Crea las tareas periódicas por defecto."""
    if not request.user.is_admin:
        messages.error(request, 'Solo los administradores pueden crear tareas programadas.')
        return redirect('accounting:tareas')
    
    from django_celery_beat.models import PeriodicTask, ClockedSchedule, CrontabSchedule
    
    tareas_creadas = []
    
    # Liquidación IVA trimestral (día 20 de enero, abril, julio, octubre)
    cron_iva, _ = CrontabSchedule.objects.get_or_create(
        minute='0', hour='8', day_of_month='20',
        month_of_year='1,4,7,10', day_of_week='*'
    )
    task_iva, created = PeriodicTask.objects.get_or_create(
        name='Liquidación IVA Trimestral',
        defaults={
            'task': 'accounting.liquidar_iva_trimestral',
            'crontab': cron_iva,
            'enabled': True,
        }
    )
    if created:
        tareas_creadas.append('Liquidación IVA Trimestral')
    
    # Cierre anual (31 diciembre)
    cron_cierre, _ = CrontabSchedule.objects.get_or_create(
        minute='0', hour='23', day_of_month='31',
        month_of_year='12', day_of_week='*'
    )
    task_cierre, created = PeriodicTask.objects.get_or_create(
        name='Cierre Anual',
        defaults={
            'task': 'accounting.cierre_anual',
            'crontab': cron_cierre,
            'enabled': True,
        }
    )
    if created:
        tareas_creadas.append('Cierre Anual')
    
    # Archivos fiscales (día 5 de cada mes)
    cron_fiscal, _ = CrontabSchedule.objects.get_or_create(
        minute='0', hour='9', day_of_month='5',
        month_of_year='*', day_of_week='*'
    )
    task_fiscal, created = PeriodicTask.objects.get_or_create(
        name='Archivos Fiscales Mensuales',
        defaults={
            'task': 'accounting.generar_archivos_fiscales',
            'crontab': cron_fiscal,
            'enabled': True,
        }
    )
    if created:
        tareas_creadas.append('Archivos Fiscales Mensuales')
    
    # SII trimestral (día 1 del mes siguiente al trimestre)
    cron_sii, _ = CrontabSchedule.objects.get_or_create(
        minute='0', hour='8', day_of_month='1',
        month_of_year='4,7,10,1', day_of_week='*'
    )
    task_sii, created = PeriodicTask.objects.get_or_create(
        name='SII Trimestral',
        defaults={
            'task': 'accounting.generar_sii',
            'crontab': cron_sii,
            'enabled': True,
        }
    )
    if created:
        tareas_creadas.append('SII Trimestral')
    
    # Cuota SS mensual (día 1 de cada mes)
    cron_ss, _ = CrontabSchedule.objects.get_or_create(
        minute='0', hour='8', day_of_month='1',
        month_of_year='*', day_of_week='*'
    )
    task_ss, created = PeriodicTask.objects.get_or_create(
        name='Cuota Seguridad Social Mensual',
        defaults={
            'task': 'accounting.generar_cuotas_seguridad_social',
            'crontab': cron_ss,
            'enabled': True,
        }
    )
    if created:
        tareas_creadas.append('Cuota Seguridad Social Mensual')
    
    if tareas_creadas:
        messages.success(
            request,
            f'Tareas creadas: {", ".join(tareas_creadas)}'
        )
    else:
        messages.info(request, 'Las tareas ya existen.')
    
    return redirect('accounting:tareas')
