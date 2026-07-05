#!/usr/bin/env python
"""Genera el PDF del manual usando xhtml2pdf (fallback por WeasyPrint)."""
import os
import re
from xhtml2pdf import pisa

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
manual_dir = os.path.join(BASE_DIR, 'manual')
html_file = os.path.join(manual_dir, 'manual.html')
css_file = os.path.join(manual_dir, 'manual_styles.css')
output_dir = os.path.join(BASE_DIR, 'media')
output_file = os.path.join(output_dir, 'manual_eurocar_erp.pdf')

os.makedirs(output_dir, exist_ok=True)

with open(html_file, 'r', encoding='utf-8') as f:
    html_content = f.read()

with open(css_file, 'r', encoding='utf-8') as f:
    css_content = f.read()

css_content = re.sub(r'@page\s*(:\w+)?\s*\{(?:[^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', '', css_content)

html_content = html_content.replace(
    '<link rel="stylesheet" href="manual_styles.css">',
    '<style>\n' + css_content + '\n</style>'
)

with open(output_file, 'wb') as f:
    status = pisa.CreatePDF(html_content, dest=f, encoding='utf-8')

if status.err:
    print(f'ERROR: {status.err} errores')
else:
    size_kb = os.path.getsize(output_file) / 1024
    print(f'PDF generado: {output_file} ({size_kb:.1f} KB)')
