"""
Servicio de generación de PDFs para R Car Rogil ERP.
Utiliza WeasyPrint para generar contratos y mandatos.
"""
from django.template.loader import render_to_string
from django.conf import settings
from weasyprint import HTML
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
            'email': 'info@rcarrogil.com',
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
