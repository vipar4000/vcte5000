"""
Tareas Celery Beat para contabilidad y fiscal.
Programadas via django-celery-beat.
"""
from celery import shared_task
from datetime import date, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@shared_task(name='accounting.liquidar_iva_trimestral')
def liquidar_iva_trimestral():
    """
    Ejecuta cada trimestre para calcular la liquidación de IVA.
    Genera el asiento de liquidación trimestral.
    """
    from apps.accounting.reports import calcular_libro_iva, calcular_trimestre
    from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable
    
    hoy = date.today()
    trimestre = (hoy.month - 1) // 3 + 1
    anio = hoy.year
    
    desde, hasta = calcular_trimestre(trimestre, anio)
    libro = calcular_libro_iva(desde, hasta)
    
    cuota = libro['cuota_liquidar']
    
    if cuota == 0:
        logger.info(f'IVA trimestre T{trimestre}/{anio}: cuota 0, sin asiento')
        return {'status': 'skip', 'cuota': 0}
    
    try:
        cuenta_iva_repercutido = CuentaContable.objects.get(codigo='471')
        cuenta_iva_soportado = CuentaContable.objects.get(codigo='472')
        cuenta_banco = CuentaContable.objects.get(codigo='572')
        
        from apps.accounting.views import generar_numero_asiento
        asiento = AsientoContable.objects.create(
            numero=generar_numero_asiento(),
            fecha=hoy,
            concepto=f'Liquidación IVA T{trimestre}/{anio} - Cuota: €{cuota}',
            estado='BORRADOR',
            tipo_documento='LiquidacionIVA',
            documento_id=trimestre,
            created_by_id=1,
        )
        
        if cuota > 0:
            # A pagar a Hacienda: DEBE 471, HABER 572
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_iva_repercutido,
                debe=cuota, haber=Decimal('0'),
                descripcion=f'Liquidación IVA T{trimestre}/{anio} - Pago Hacienda',
            )
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_banco,
                debe=Decimal('0'), haber=cuota,
                descripcion=f'Liquidación IVA T{trimestre}/{anio} - Pago Hacienda',
            )
        else:
            # A compensar: DEBE 572, HABER 472
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_banco,
                debe=abs(cuota), haber=Decimal('0'),
                descripcion=f'Liquidación IVA T{trimestre}/{anio} - Compensación',
            )
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_iva_soportado,
                debe=Decimal('0'), haber=abs(cuota),
                descripcion=f'Liquidación IVA T{trimestre}/{anio} - Compensación',
            )
        
        logger.info(f'IVA trimestre T{trimestre}/{anio}: asiento {asiento.numero} creado, cuota €{cuota}')
        return {'status': 'ok', 'asiento': asiento.numero, 'cuota': float(cuota)}
        
    except Exception as e:
        logger.error(f'Error liquidación IVA T{trimestre}/{anio}: {e}')
        return {'status': 'error', 'error': str(e)}


@shared_task(name='accounting.cierre_anual')
def cierre_anual():
    """
    Ejecuta el 31 de diciembre para cerrar el ejercicio contable.
    Traspasa resultado del ejercicio (129) a resultados no asignados (110).
    """
    from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable
    from apps.accounting.reports import calcular_pyg
    
    hoy = date.today()
    anio = hoy.year - 1  # Cerramos el año anterior
    
    pyg = calcular_pyg(date(anio, 1, 1), date(anio, 12, 31))
    resultado_neto = pyg['resultado_neto']
    
    if resultado_neto == 0:
        logger.info(f'Cierre {anio}: resultado 0, sin asiento')
        return {'status': 'skip', 'resultado': 0}
    
    try:
        cuenta_129 = CuentaContable.objects.get(codigo='129')
        cuenta_110 = CuentaContable.objects.get(codigo='110')
        
        from apps.accounting.views import generar_numero_asiento
        asiento = AsientoContable.objects.create(
            numero=generar_numero_asiento(),
            fecha=hoy,
            concepto=f'Cierre ejercicio {anio} - Resultado: €{resultado_neto}',
            estado='BORRADOR',
            tipo_documento='CierreAnual',
            documento_id=anio,
            created_by_id=1,
        )
        
        if resultado_neto > 0:
            # Beneficio: DEBE 129, HABER 110
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_129,
                debe=resultado_neto, haber=Decimal('0'),
                descripcion=f'Cierre ejercicio {anio} - Beneficio',
            )
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_110,
                debe=Decimal('0'), haber=resultado_neto,
                descripcion=f'Cierre ejercicio {anio} - Beneficio',
            )
        else:
            # Pérdida: DEBE 110, HABER 129
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_110,
                debe=abs(resultado_neto), haber=Decimal('0'),
                descripcion=f'Cierre ejercicio {anio} - Pérdida',
            )
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_129,
                debe=Decimal('0'), haber=abs(resultado_neto),
                descripcion=f'Cierre ejercicio {anio} - Pérdida',
            )
        
        logger.info(f'Cierre {anio}: asiento {asiento.numero}, resultado €{resultado_neto}')
        return {'status': 'ok', 'asiento': asiento.numero, 'resultado': float(resultado_neto)}
        
    except Exception as e:
        logger.error(f'Error cierre {anio}: {e}')
        return {'status': 'error', 'error': str(e)}


@shared_task(name='accounting.generar_archivos_fiscales')
def generar_archivos_fiscales():
    """
    Genera los archivos fiscales del mes para descarga.
    Ejecuta el día 5 de cada mes.
    """
    from apps.accounting.exports import generar_modelo_390, generar_csv_pre303
    from django.conf import settings
    import os
    
    hoy = date.today()
    anio = hoy.year
    trimestre = (hoy.month - 1) // 3 + 1
    
    output_dir = os.path.join(settings.MEDIA_ROOT, 'fiscal')
    os.makedirs(output_dir, exist_ok=True)
    
    archivos = []
    
    try:
        # Modelo 390
        contenido_390 = generar_modelo_390(anio)
        path_390 = os.path.join(output_dir, f'Modelo390_{anio}.txt')
        with open(path_390, 'w') as f:
            f.write(contenido_390)
        archivos.append(path_390)
        
        # CSV Pre-303
        contenido_303 = generar_csv_pre303(anio, trimestre)
        path_303 = os.path.join(output_dir, f'Modelo303_T{trimestre}_{anio}.csv')
        with open(path_303, 'w') as f:
            f.write(contenido_303)
        archivos.append(path_303)
        
        logger.info(f'Archivos fiscales generados: {archivos}')
        return {'status': 'ok', 'archivos': archivos}
        
    except Exception as e:
        logger.error(f'Error generando archivos fiscales: {e}')
        return {'status': 'error', 'error': str(e)}


@shared_task(name='accounting.generar_sii')
def generar_sii():
    """
    Genera el XML del SII para el trimestre actual.
    Ejecuta el día 1 de cada mes para el trimestre anterior.
    """
    from apps.accounting.exports import generar_sii_xml
    from django.conf import settings
    import os
    
    hoy = date.today()
    anio = hoy.year
    trimestre = (hoy.month - 1) // 3 + 1
    
    output_dir = os.path.join(settings.MEDIA_ROOT, 'fiscal')
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        xml_content = generar_sii_xml(anio, trimestre)
        path_sii = os.path.join(output_dir, f'SII_{anio}T{trimestre}.xml')
        with open(path_sii, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        logger.info(f'SII generado: {path_sii}')
        return {'status': 'ok', 'archivo': path_sii}
        
    except Exception as e:
        logger.error(f'Error generando SII: {e}')
        return {'status': 'error', 'error': str(e)}


@shared_task(name='accounting.generar_cuotas_seguridad_social')
def generar_cuotas_seguridad_social():
    """
    Genera el asiento de cuotas de Seguridad Social mensuales.
    Ejecuta el día 1 de cada mes.
    """
    from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable
    from datetime import date
    
    hoy = date.today()
    
    try:
        cuenta_ss = CuentaContable.objects.get(codigo='642')
        cuenta_banco = CuentaContable.objects.get(codigo='572')
        
        from apps.accounting.views import generar_numero_asiento
        asiento = AsientoContable.objects.create(
            numero=generar_numero_asiento(),
            fecha=hoy,
            concepto=f'Cuarto Seguridad Social {hoy.strftime("%m/%Y")} - Borrador para revisar',
            estado='BORRADOR',
            tipo_documento='SeguridadSocial',
            created_by_id=1,
        )
        
        MovimientoContable.objects.create(
            asiento=asiento, cuenta=cuenta_ss,
            debe=Decimal('0'), haber=Decimal('0'),
            descripcion=f'SS {hoy.strftime("%m/%Y")} - Pendiente importe',
        )
        
        logger.info(f'Asiento SS mensual creado: {asiento.numero} (borrador)')
        return {'status': 'ok', 'asiento': asiento.numero}
        
    except Exception as e:
        logger.error(f'Error asiento SS: {e}')
        return {'status': 'error', 'error': str(e)}
