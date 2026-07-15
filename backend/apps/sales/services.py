"""
Servicio de generación de PDFs para R Car Rogil ERP.
Utiliza WeasyPrint para generar contratos, mandatos y facturas.
"""
from django.template.loader import render_to_string
from django.conf import settings
from weasyprint import HTML
from decimal import Decimal
import os


def generar_contrato_compraventa(venta):
    """
    Genera el contrato de compraventa de vehículo de ocasión.
    
    Args:
        venta: Instancia de VentaVehiculo
    
    Returns:
        Archivo PDF generado
    """
    context = {
        'venta': venta,
        'vehiculo': venta.vehiculo,
        'cliente': {
            'nombre': venta.cliente_nombre,
            'dni': venta.cliente_dni,
            'direccion': venta.cliente_direccion,
            'poblacion': venta.cliente_poblacion,
            'provincia': venta.cliente_provincia,
            'cp': venta.cliente_cp,
            'telefono': venta.cliente_telefono,
            'email': venta.cliente_email,
        },
        'empresa': {
            'nombre': 'R Car Rogil',
            'cif': 'B26729731',
            'direccion': 'Calle Brasil 9',
            'poblacion': 'Alcalá de Henares',
            'provincia': 'Madrid',
            'cp': '28806',
            'telefono': '+34 722 81 7617',
            'email': settings.DEFAULT_FROM_EMAIL,
        }
    }
    
    html_string = render_to_string('sales/contrato_compraventa.html', context)
    
    # Generar PDF
    pdf_path = os.path.join(settings.MEDIA_ROOT, 'contratos', f'contrato_{venta.pk}.pdf')
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    
    HTML(string=html_string).write_pdf(pdf_path)
    
    # Guardar ruta en la venta
    venta.contrato_pdf = f'contratos/contrato_{venta.pk}.pdf'
    venta.save(update_fields=['contrato_pdf'])
    
    return pdf_path


def generar_mandato_gestoria(venta):
    """
    Genera el mandato de gestoría para cambio de titularidad DGT.
    
    Args:
        venta: Instancia de VentaVehiculo
    
    Returns:
        Archivo PDF generado
    """
    context = {
        'venta': venta,
        'vehiculo': venta.vehiculo,
        'cliente': {
            'nombre': venta.cliente_nombre,
            'dni': venta.cliente_dni,
            'direccion': venta.cliente_direccion,
            'poblacion': venta.cliente_poblacion,
            'provincia': venta.cliente_provincia,
            'cp': venta.cliente_cp,
        },
        'empresa': {
            'nombre': 'R Car Rogil',
            'cif': 'B26729731',
            'direccion': 'Calle Brasil 9',
            'poblacion': 'Alcalá de Henares',
            'provincia': 'Madrid',
            'cp': '28806',
        }
    }
    
    html_string = render_to_string('sales/mandato_gestoria.html', context)
    
    # Generar PDF
    pdf_path = os.path.join(settings.MEDIA_ROOT, 'mandatos', f'mandato_{venta.pk}.pdf')
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    
    HTML(string=html_string).write_pdf(pdf_path)
    
    # Guardar ruta en la venta
    venta.mandato_pdf = f'mandatos/mandato_{venta.pk}.pdf'
    venta.save(update_fields=['mandato_pdf'])
    
    return pdf_path


# =============================================================================
# FACTURAS REBU
# =============================================================================

EMPRESA = {
    'nombre': 'R Car Rogil',
    'cif': 'B26729731',
    'direccion': 'Calle Brasil 9',
    'poblacion': 'Alcalá de Henares',
    'provincia': 'Madrid',
    'cp': '28806',
    'telefono': '+34 722 81 7617',
    'email': settings.DEFAULT_FROM_EMAIL,
}


def crear_factura_venta(venta, usuario):
    """
    Crea FacturaVenta + DetalleRebu a partir de una VentaVehiculo.
    
    Args:
        venta: VentaVehiculo ya guardada en BD
        usuario: User que genera la factura
    
    Returns:
        FacturaVenta creada
    """
    from .models import FacturaVenta, DetalleRebu
    from decimal import Decimal
    
    codigo = FacturaVenta.generar_siguiente_codigo()
    
    factura = FacturaVenta.objects.create(
        codigo_factura=codigo,
        tipo_factura='F1',
        venta=venta,
        fecha_operacion=venta.fecha_venta,
        cliente_nif=venta.cliente_dni,
        cliente_nombre=venta.cliente_nombre,
        precio_venta_total=venta.precio_venta,
        base_imponible_rebu=venta.base_imponible,
        iva_repercutido=venta.cuota_iva,
    )
    
    DetalleRebu.objects.create(
        factura=factura,
        vehiculo=venta.vehiculo,
        precio_adquisicion=venta.coste_total,
        precio_venta_final=venta.precio_venta,
    )
    
    return factura


def generar_pdf_factura(factura):
    """
    Genera el PDF de una factura REBU.
    
    Args:
        factura: FacturaVenta
    
    Returns:
        Archivo PDF generado
    """
    venta = factura.venta
    vehiculo = venta.vehiculo
    
    context = {
        'factura': factura,
        'venta': venta,
        'vehiculo': vehiculo,
        'empresa': EMPRESA,
    }
    
    html_string = render_to_string('sales/factura_rebu.html', context)
    
    pdf_dir = os.path.join(settings.MEDIA_ROOT, 'facturas')
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f'{factura.codigo_factura}.pdf')
    
    HTML(string=html_string).write_pdf(pdf_path)
    
    return pdf_path


def crear_factura_rectificativa(factura_original, tipo, motivo, usuario):
    """
    Crea una factura rectificativa (R1 o R4) referenciando una factura original.
    
    Args:
        factura_original: FacturaVenta original
        tipo: 'R1' (error) o 'R4' (devolución)
        motivo: Descripción del motivo
        usuario: User que genera la rectificativa
    
    Returns:
        FacturaVenta rectificativa creada
    """
    from .models import FacturaVenta, DetalleRebu
    from django.utils import timezone
    
    year = timezone.now().year
    ultima = FacturaVenta.objects.filter(
        tipo_factura__in=['R1', 'R4'],
        codigo_factura__startswith=f'R-{year}'
    ).order_by('-codigo_factura').first()
    
    if ultima:
        try:
            numero = int(ultima.codigo_factura.split('-')[-1]) + 1
        except (ValueError, IndexError):
            numero = 1
    else:
        numero = 1
    
    codigo = f'R-{year}-{numero:04d}'
    
    factura_rect = FacturaVenta.objects.create(
        codigo_factura=codigo,
        tipo_factura=tipo,
        factura_rectificada=factura_original,
        fecha_operacion=timezone.now().date(),
        cliente_nif=factura_original.cliente_nif,
        cliente_nombre=factura_original.cliente_nombre,
        precio_venta_total=factura_original.precio_venta_total,
        base_imponible_rebu=factura_original.base_imponible_rebu,
        iva_repercutido=factura_original.iva_repercutido,
    )
    
    DetalleRebu.objects.create(
        factura=factura_rect,
        vehiculo=factura_original.venta.vehiculo,
        precio_adquisicion=factura_original.detalles_rebu.first().precio_adquisicion if factura_original.detalles_rebu.exists() else Decimal('0'),
        precio_venta_final=factura_original.precio_venta_total,
    )
    
    return factura_rect


def generar_pdf_factura_rectificativa(factura):
    """
    Genera el PDF de una factura rectificativa.
    
    Args:
        factura: FacturaVenta rectificativa
    
    Returns:
        Archivo PDF generado
    """
    venta = factura.venta
    vehiculo = venta.vehiculo
    
    context = {
        'factura': factura,
        'venta': venta,
        'vehiculo': vehiculo,
        'empresa': EMPRESA,
    }
    
    html_string = render_to_string('sales/factura_rectificativa.html', context)
    
    pdf_dir = os.path.join(settings.MEDIA_ROOT, 'facturas')
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f'{factura.codigo_factura}.pdf')
    
    HTML(string=html_string).write_pdf(pdf_path)
    
    return pdf_path
