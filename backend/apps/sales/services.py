"""
Servicio de generación de PDFs para R Car Rogil ERP.
Genera contratos, mandatos y facturas.

Los PDFs se guardan a través del almacenamiento configurado (MEDIA_ROOT local
en desarrollo, S3/R2 en producción) para que los enlaces de descarga sigan
funcionando después de un despliegue.

Motor de renderizado: WeasyPrint si sus librerías de sistema (Pango/Cairo)
están disponibles; si no —por ejemplo en el runtime nativo de Render, que no
instala paquetes del sistema— se usa xhtml2pdf, que es Python puro.
"""
from io import BytesIO

from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.template.loader import render_to_string


class PDFGenerationError(RuntimeError):
    """No se pudo generar el PDF con ninguno de los motores disponibles."""


def _render_pdf(html_string):
    """Devuelve los bytes del PDF usando el primer motor disponible."""
    try:
        from weasyprint import HTML
    except Exception:
        # ImportError o librerías de sistema ausentes: se intenta xhtml2pdf.
        HTML = None

    if HTML is not None:
        try:
            return HTML(string=html_string).write_pdf()
        except Exception as exc:
            raise PDFGenerationError(
                f'WeasyPrint no pudo generar el PDF: {exc}'
            ) from exc

    try:
        from xhtml2pdf import pisa
    except Exception as exc:
        raise PDFGenerationError(
            'No hay motor de PDF disponible. Instale WeasyPrint con sus '
            'librerías de sistema (Pango/Cairo) o xhtml2pdf (pip install xhtml2pdf).'
        ) from exc

    buffer = BytesIO()
    resultado = pisa.CreatePDF(src=html_string, dest=buffer)
    if resultado.err:
        raise PDFGenerationError(
            f'xhtml2pdf devolvió {resultado.err} error(es) al generar el PDF.'
        )
    return buffer.getvalue()


def _guardar_en_campo(campo, nombre, pdf_bytes):
    """Guarda el PDF en un FileField usando el almacenamiento configurado.

    Se borra el archivo anterior para conservar un nombre estable (sin sufijos
    aleatorios de colisión) y se persiste el modelo.
    """
    campo.delete(save=False)
    campo.save(nombre, ContentFile(pdf_bytes), save=True)
    return campo.name


def _guardar_en_storage(ruta, pdf_bytes):
    """Guarda los bytes en el almacenamiento por defecto conservando la ruta."""
    if default_storage.exists(ruta):
        default_storage.delete(ruta)
    return default_storage.save(ruta, ContentFile(pdf_bytes))


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
    
    # Generar el PDF y guardarlo en el almacenamiento configurado
    # (MEDIA_ROOT en desarrollo, S3/R2 en producción).
    pdf_bytes = _render_pdf(html_string)
    _guardar_en_campo(venta.contrato_pdf, f'contrato_{venta.pk}.pdf', pdf_bytes)
    
    return venta.contrato_pdf.name


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
    
    # Generar el PDF y guardarlo en el almacenamiento configurado.
    pdf_bytes = _render_pdf(html_string)
    _guardar_en_campo(venta.mandato_pdf, f'mandato_{venta.pk}.pdf', pdf_bytes)
    
    return venta.mandato_pdf.name


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
    
    ruta = f'facturas/{factura.codigo_factura}.pdf'
    return _guardar_en_storage(ruta, _render_pdf(html_string))


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
    original = factura.factura_rectificada or factura
    venta = original.venta
    vehiculo = venta.vehiculo if venta else None
    
    context = {
        'factura': factura,
        'venta': venta,
        'vehiculo': vehiculo,
        'empresa': EMPRESA,
    }
    
    html_string = render_to_string('sales/factura_rectificativa.html', context)
    
    ruta = f'facturas/{factura.codigo_factura}.pdf'
    return _guardar_en_storage(ruta, _render_pdf(html_string))
