#!/usr/bin/env python
"""
Script para generar el Manual de Usuario en PDF del ERP R Car Rogil.
Uso: python generate_manual.py
Salida: ../media/manual_eurocar_erp.pdf
"""

import os
import sys

# Add backend to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

def generate_manual():
    """Genera el PDF del manual de usuario."""
    
    try:
        from weasyprint import HTML
    except ImportError:
        print("ERROR: WeasyPrint no esta instalado.")
        print("Instale con: pip install weasyprint")
        sys.exit(1)
    
    # Paths
    manual_dir = os.path.join(BASE_DIR, 'manual')
    html_file = os.path.join(manual_dir, 'manual.html')
    css_file = os.path.join(manual_dir, 'manual_styles.css')
    output_dir = os.path.join(BASE_DIR, 'media')
    output_file = os.path.join(output_dir, 'manual_eurocar_erp.pdf')
    
    # Verify files exist
    if not os.path.exists(html_file):
        print(f"ERROR: No se encontro {html_file}")
        sys.exit(1)
    
    if not os.path.exists(css_file):
        print(f"ERROR: No se encontro {css_file}")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 60)
    print("  GENERADOR DE MANUAL - R CAR ROGIL ERP")
    print("=" * 60)
    print()
    print(f"  HTML fuente:  {html_file}")
    print(f"  CSS fuente:   {css_file}")
    print(f"  PDF salida:   {output_file}")
    print()
    
    # Read HTML
    print("  Leyendo HTML...")
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Read CSS and embed it
    print("  Leyendo CSS...")
    with open(css_file, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    # Embed CSS into HTML (for WeasyPrint)
    # Replace the <link> tag with inline <style>
    html_content = html_content.replace(
        '<link rel="stylesheet" href="manual_styles.css">',
        f'<style>\n{css_content}\n</style>'
    )
    
    # Fix relative paths for WeasyPrint (CSS resources)
    # Make sure image paths work from the manual directory
    html_content = html_content.replace(
        'href="manual_styles.css"',
        f'href="file:///{css_file.replace(os.sep, "/")}"'
    )
    
    # Generate PDF
    print("  Generando PDF...")
    try:
        html_doc = HTML(string=html_content, base_url=manual_dir)
        html_doc.write_pdf(target=output_file)
        print()
        print(f"  PDF generado exitosamente!")
        print(f"  Tamano: {os.path.getsize(output_file) / 1024:.1f} KB")
        print()
        print(f"  Ubicacion: {output_file}")
        print()
        print("=" * 60)
        print("  COMPLETADO!")
        print("=" * 60)
    except Exception as e:
        print(f"  ERROR al generar PDF: {e}")
        print()
        print("  Posibles soluciones:")
        print("  1. Instale las dependencias de WeasyPrint:")
        print("     pip install weasyprint")
        print("  2. En Windows, instale GTK+ Runtime:")
        print("     https://github.com/nicfit/keyboard/issues/57#issuecomment-419793814")
        sys.exit(1)


if __name__ == '__main__':
    generate_manual()
