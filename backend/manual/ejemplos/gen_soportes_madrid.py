# -*- coding: utf-8 -*-
"""Genera los soportes contables de la Prueba del Sistema (Capitulo 20).

Crea en <repo>/soportes madrid/:
  - 6 facturas PDF que reproducen EXACTAMENTE proveedores, CIFs, numeros,
    fechas e importes del capitulo 20 del manual (incluido el Paso 8.6).
  - 1 extracto bancario CSV para la conciliacion (Banco > Conciliacion).

Uso:  python gen_soportes_madrid.py
No requiere dependencias (PDF artesanal, mismo patron que gen_pdf.py).
"""
import csv
import os

BASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'soportes madrid'
)


def _escribir_pdf(path, objects):
    """Serializa los objetos PDF con su tabla xref y lo guarda en path."""
    with open(path, 'wb') as f:
        f.write(b'%PDF-1.4\n')
        xref_offsets = []
        for obj in objects:
            xref_offsets.append(f.tell())
            f.write(obj)
        xref_offset = f.tell()
        num_objects = len(objects) + 1
        f.write(b'xref\n')
        f.write(b'0 ' + str(num_objects).encode() + b'\n')
        f.write(b'0000000000 65535 f \n')
        for offset in xref_offsets:
            f.write(f'{offset:010d} 00000 n \n'.encode())
        f.write(b'trailer\n')
        f.write(b'<< /Size ' + str(num_objects).encode() + b' /Root 1 0 R >>\n')
        f.write(b'startxref\n')
        f.write(str(xref_offset).encode() + b'\n')
        f.write(b'%%EOF\n')

    print(f'PDF creado: {os.path.basename(path)} ({os.path.getsize(path)} bytes)')


def _pdf_str(s):
    """Codifica y escapa un string para un literal de texto PDF (latin-1)."""
    enc = s.encode('latin-1', 'replace')
    return enc.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')


def generar_pdf(path, titulo, lineas):
    """Genera un PDF mínimo con Helvetica.

    - titulo: línea destacada (14pt) en la parte superior
    - lineas: lista de strings (10pt) dibujados de arriba abajo
    """
    objects = []

    objects.append(b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
    objects.append(b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n')
    objects.append(b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n')

    y = 730
    stream = b'BT /F1 14 Tf 50 ' + str(y).encode() + b' Td (' + _pdf_str(titulo) + b') Tj ET\n'
    y -= 30
    for linea in lineas:
        if linea.startswith('**'):  # línea destacada (total)
            stream += b'BT /F1 12 Tf 50 ' + str(y).encode() + b' Td (' + _pdf_str(linea[2:]) + b') Tj ET\n'
        else:
            stream += b'BT /F1 10 Tf 50 ' + str(y).encode() + b' Td (' + _pdf_str(linea) + b') Tj ET\n'
        y -= 20

    objects.append(b'4 0 obj\n<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'endstream\nendobj\n')
    objects.append(b'5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n')

    _escribir_pdf(path, objects)


def generar_factura_filtro(path):
    """Factura hipotetica realista de la compra del filtro (Paso 3.2, CM-003).

    Importes exactos del capitulo 20: 5 ud x 12,00 = 60,00 base; IVA 21% = 12,60;
    TOTAL = 72,60 EUR. Pago a credito comercial (cuenta 410).
    """
    enc = _pdf_str

    def txt(font, size, x, y, s):
        return (b'BT /' + font.encode('ascii') + b' ' + str(size).encode() + b' Tf '
                + str(x).encode() + b' ' + str(y).encode() + b' Td ('
                + enc(s) + b') Tj ET\n')

    def linea(x1, y1, x2, y2):
        return (b'1 w ' + str(x1).encode() + b' ' + str(y1).encode() + b' m '
                + str(x2).encode() + b' ' + str(y2).encode() + b' l S\n')

    def recuadro(x, y, w, h):
        return (b'1 w ' + str(x).encode() + b' ' + str(y).encode() + b' '
                + str(w).encode() + b' ' + str(h).encode() + b' re S\n')

    def recuadro_gris(x, y, w, h):
        return (b'0.85 g ' + str(x).encode() + b' ' + str(y).encode() + b' '
                + str(w).encode() + b' ' + str(h).encode() + b' re f\n0 g\n')

    stream = b''
    # Cabecera
    stream += txt('F2', 16, 50, 748, 'FACTURA')
    stream += txt('F1', 10, 50, 728, 'Filtros Madrid S.L. - Filtros para automocion')
    stream += txt('F1', 10, 380, 748, 'N. Factura: CM-003')
    stream += txt('F1', 10, 380, 730, 'Fecha emision: 02/07/2026')
    stream += txt('F1', 10, 380, 712, 'Vencimiento: 02/08/2026')
    stream += linea(50, 700, 562, 700)

    # Bloque proveedor
    stream += txt('F2', 9, 50, 678, 'PROVEEDOR')
    stream += txt('F1', 11, 50, 660, 'Filtros Madrid S.L.')
    stream += txt('F1', 9, 50, 643, 'CIF: E12345678')
    stream += txt('F1', 9, 50, 626, 'C/ del Filtro 12, Pol. Ind. Las Mercedes')
    stream += txt('F1', 9, 50, 609, '28022 Madrid')
    stream += txt('F1', 9, 50, 592, 'Tel.: 911 234 567')

    # Bloque cliente
    stream += txt('F2', 9, 380, 678, 'CLIENTE')
    stream += txt('F1', 11, 380, 660, 'R Car Rogil S.L.')
    stream += txt('F1', 9, 380, 643, 'CIF: B86123456')
    stream += txt('F1', 9, 380, 626, 'Avda. de America 34')
    stream += txt('F1', 9, 380, 609, '28028 Madrid')

    # Tabla de lineas
    stream += recuadro(50, 460, 512, 100)
    stream += recuadro_gris(50, 537, 512, 23)
    stream += txt('F2', 9, 60, 545, 'Concepto')
    stream += txt('F2', 9, 335, 545, 'Cant.')
    stream += txt('F2', 9, 415, 545, 'P. Unit.')
    stream += txt('F2', 9, 495, 545, 'Importe')
    stream += linea(330, 460, 330, 560)
    stream += linea(405, 460, 405, 560)
    stream += linea(485, 460, 485, 560)
    stream += txt('F1', 10, 60, 515, 'Filtro de aire')
    stream += txt('F1', 9, 60, 498, '(ref. FA-334, papel de celulosa)')
    stream += txt('F1', 10, 335, 515, '5 ud')
    stream += txt('F1', 10, 415, 515, '12,00')
    stream += txt('F1', 10, 495, 515, '60,00')
    stream += linea(50, 490, 562, 490)

    # Totales
    stream += txt('F1', 10, 360, 425, 'Base imponible')
    stream += txt('F1', 10, 495, 425, '60,00 EUR')
    stream += txt('F1', 10, 360, 405, 'IVA (21%)')
    stream += txt('F1', 10, 495, 405, '12,60 EUR')
    stream += recuadro_gris(350, 352, 212, 34)
    stream += txt('F2', 12, 365, 364, 'TOTAL')
    stream += txt('F2', 12, 495, 364, '72,60 EUR')

    # Pie
    stream += linea(50, 330, 562, 330)
    stream += txt('F1', 9, 50, 312,
                  'Forma de pago: Credito comercial (proveedores, cuenta 410) - vencimiento 02/08/2026')
    stream += txt('F1', 9, 50, 295,
                  'Documento de prueba: factura hipotetica sin validez fiscal (capitulo 20 del manual).')

    objects = [
        b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n'
        b'   /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>\nendobj\n',
        b'4 0 obj\n<< /Length ' + str(len(stream)).encode()
        + b' >>\nstream\n' + stream + b'endstream\nendobj\n',
        b'5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
        b'6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n',
    ]

    _escribir_pdf(path, objects)


def main():
    os.makedirs(BASE, exist_ok=True)

    # --- Paso 1.2: Factura inversion inicial (Split Billing) ---
    generar_pdf(
        os.path.join(BASE, '01_INV-2026-001_factura_inversion_taller.pdf'),
        'FACTURA - INV-2026-001',
        [
            'Taller Equipamiento S.L.  |  CIF: B87654321',
            'Fecha de emision: 01/07/2026',
            'Cliente: R Car Rogil S.L. - Madrid',
            '',
            'LINEAS DE LA FACTURA:',
            'Compresor industrial 500L (Herramientas) ....... 1.200,00 EUR',
            'Escaner diagnostico OBD2 (Herramientas) ........   850,00 EUR',
            '--------------------------------------------------',
            'Base imponible ............................. 2.050,00 EUR',
            'IVA 21% (252,00 + 178,50) ..................   430,50 EUR',
            '**TOTAL FACTURA ............................ 2.480,50 EUR',
            '',
            'Forma de pago: Transferencia bancaria - Banco Santander (572)',
        ],
    )

    # --- Paso 2.1: Factura compra del vehiculo ---
    generar_pdf(
        os.path.join(BASE, '02_FC-2026-001_factura_compra_vehiculo.pdf'),
        'FACTURA - FC-2026-001',
        [
            'Subastas Online S.A.  |  CIF: B12345678',
            'Fecha de emision: 01/07/2026',
            'Cliente: R Car Rogil S.L. - Madrid',
            '',
            'Vehiculo: Volkswagen Golf 1.6 TDI (2018)',
            'Matricula: 1234ABC  |  Bastidor: VW000020000000000',
            'Plataforma: BCA  |  Km: 95.000  |  Dano: ACCIDENTAL',
            '',
            'Precio subasta .............................. 7.500,00 EUR',
            'Tasas de sala ................................. 400,00 EUR',
            'Logistica/grua ................................ 250,00 EUR',
            '--------------------------------------------------',
            'Base imponible ............................. 8.150,00 EUR',
            'IVA 21% s/ tasas+logistica (650,00) ........   136,50 EUR',
            '**TOTAL FACTURA ............................ 8.286,50 EUR',
            '',
            'Forma de pago: Transferencia bancaria - Banco Santander (572)',
        ],
    )

    # --- Paso 3.2 (compra #1): Factura aceite ---
    generar_pdf(
        os.path.join(BASE, '03_CM-001_factura_aceite.pdf'),
        'FACTURA - CM-001',
        [
            'Distribuciones Auto S.L.  |  CIF: C12345678',
            'Fecha de emision: 02/07/2026',
            'Cliente: R Car Rogil S.L. - Madrid',
            '',
            'Aceite motor 5W30   20 litros x 8,50 ........ 170,00 EUR',
            '--------------------------------------------------',
            'Base imponible ............................... 170,00 EUR',
            'IVA 21% .......................................  35,70 EUR',
            '**TOTAL FACTURA .............................. 205,70 EUR',
            '',
            'Forma de pago: Credito comercial (proveedores, cuenta 410)',
        ],
    )

    # --- Paso 3.2 (compra #2): Factura pastillas ---
    generar_pdf(
        os.path.join(BASE, '04_CM-002_factura_pastillas.pdf'),
        'FACTURA - CM-002',
        [
            'Recambios Martinez S.L.  |  CIF: D12345678',
            'Fecha de emision: 02/07/2026',
            'Cliente: R Car Rogil S.L. - Madrid',
            '',
            'Pastillas de freno   3 juegos x 35,00 ....... 105,00 EUR',
            '--------------------------------------------------',
            'Base imponible ............................... 105,00 EUR',
            'IVA 21% .......................................  22,05 EUR',
            '**TOTAL FACTURA .............................. 127,05 EUR',
            '',
            'Forma de pago: Credito comercial (proveedores, cuenta 410)',
        ],
    )

    # --- Paso 3.2 (compra #3): Factura hipotetica filtro de aire ---
    generar_factura_filtro(os.path.join(BASE, '05_CM-003_factura_filtro.pdf'))

    # --- Paso 8.6: Factura alquiler del galpon (con retencion IRPF) ---
    generar_pdf(
        os.path.join(BASE, '06_ALQ-2026-07_factura_alquiler_galpon.pdf'),
        'FACTURA - ALQ-2026-07',
        [
            'Propietario Galpon S.L.  |  CIF: B87654321',
            'Fecha de emision: 20/07/2026',
            'Cliente: R Car Rogil S.L. - Madrid',
            'Concepto: Alquiler del galpon - mensualidad julio 2026',
            '',
            'Base imponible ............................. 2.000,00 EUR',
            'IVA 21% ......................................   420,00 EUR',
            'Retencion IRPF 19% (arrendamiento) .........  -380,00 EUR',
            '--------------------------------------------------',
            '**TOTAL A PAGAR ............................ 2.040,00 EUR',
            '',
            'Categoria del gasto: ARRENDAMIENTO (cuenta PGC 621)',
            'Pendiente de pago (proveedores, cuenta 410)',
        ],
    )

    # --- Paso 1.3 / 9.5.5: Extracto bancario para la conciliacion ---
    # 4 lineas = los 4 movimientos que genera el ERP durante el capitulo 20.
    # El alquiler (Paso 8.6) NO aparece: queda pendiente en la cuenta 410.
    # La fecha del deposito es la del dia de la prueba (05/08/2026);
    # el matcher admite +/-2 dias si se ejecuta en otra fecha.
    csv_path = os.path.join(BASE, '07_extracto_bancario_santander.csv')
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['fecha', 'concepto', 'tipo', 'importe'])
        writer.writerow(['05/08/2026', 'Deposito inicial', 'INGRESO', '50.000,00'])
        writer.writerow(['01/07/2026', 'Inversión inicial INV-2026-001: Taller Equipamiento S.L.', 'EGRESO', '2.480,50'])
        writer.writerow(['01/07/2026', 'Compra vehículo Volkswagen Golf 1.6 TDI (1234ABC)', 'EGRESO', '8.286,50'])
        writer.writerow(['15/07/2026', 'Cobro venta Volkswagen Golf 1.6 TDI (1234ABC) - Antonio Perez Martin', 'INGRESO', '11.900,00'])
    print(f'CSV creado: {os.path.basename(csv_path)} ({os.path.getsize(csv_path)} bytes)')

    print(f'\nCarpeta destino: {os.path.abspath(BASE)}')


if __name__ == '__main__':
    main()
