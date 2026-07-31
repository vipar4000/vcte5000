import os

def generar_pdf(path, titulo, lineas):
    """
    Genera un PDF mínimo con Helvetica.
    - titulo: línea en negrita (12pt) en la parte superior
    - lineas: lista de strings (10pt) que se dibujan de arriba abajo
    """
    objects = []

    objects.append(b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
    objects.append(b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n')
    objects.append(b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n')

    # Construir stream con todas las líneas
    y = 700
    stream = b'BT /F1 12 Tf 50 ' + str(y).encode() + b' Td (' + titulo.encode('latin-1', 'replace') + b') Tj\n'
    y -= 30
    for linea in lineas:
        stream += b'BT /F1 10 Tf 50 ' + str(y).encode() + b' Td (' + linea.encode('latin-1', 'replace') + b') Tj\n'
        y -= 22

    stream += b'ET\n'
    objects.append(b'4 0 obj\n<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'endstream\nendobj\n')
    objects.append(b'5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n')

    header = b'%PDF-1.4\n'
    with open(path, 'wb') as f:
        f.write(header)
        xref_offsets = []
        for obj in objects:
            xref_offsets.append(f.tell())
            f.write(obj)
        xref_offset = f.tell()
        num_objects = len(objects) + 1
        f.write(b'xref\n')
        f.write(str(num_objects).encode() + b'\n')
        f.write(b'0000000000 65535 f \n')
        for offset in xref_offsets:
            f.write(f'{offset:010d} 00000 n \n'.encode())
        f.write(b'trailer\n')
        f.write(b'<< /Size ' + str(num_objects).encode() + b' /Root 1 0 R >>\n')
        f.write(b'startxref\n')
        f.write(str(xref_offset).encode() + b'\n')
        f.write(b'%%EOF\n')

    size = os.path.getsize(path)
    print(f'PDF creado: {path} ({size} bytes)')


base = r'C:\eurocar\backend\manual\ejemplos'

# --- Factura inversión inicial ---
generar_pdf(
    os.path.join(base, 'factura_compresor_escaner.pdf'),
    'Factura de inversion inicial',
    [
        'Taller Equipamiento S.L.  |  CIF: B87654321',
        'Factura: INV-2026-001  |  Fecha: 30/07/2026',
        '',
        'Compresor ...................... 1.200,00 EUR',
        'Escaner  ......................   850,00 EUR',
        '---------------------------------------',
        'Base imponible ............... 2.050,00 EUR',
        'IVA 21%  ....................... 430,50 EUR',
        'TOTAL  ....................... 2.480,50 EUR',
    ],
)

# --- Factura compra de materiales ---
generar_pdf(
    os.path.join(base, 'factura_materiales.pdf'),
    'Factura de compra de materiales',
    [
        'Distribuciones Auto S.L.  |  CIF: B87654321',
        'Factura: FAC-PRUEBA-001  |  Fecha: 30/07/2026',
        '',
        'Aceite motor 5W30 (20L x 4,50) ....... 90,00 EUR',
        'Pastillas de freno (3ud x 18,00) ..... 54,00 EUR',
        '---------------------------------------',
        'Base imponible ............... 144,00 EUR',
        'IVA 21%  ....................... 30,24 EUR',
        'TOTAL  ....................... 174,24 EUR',
    ],
)

# --- Factura compra de vehiculo ---
generar_pdf(
    os.path.join(base, 'factura_vehiculo.pdf'),
    'Factura de compra de vehiculo',
    [
        'Concesionario AutoVenta S.A.  |  CIF: B12345678',
        'Factura: VHC-2026-001  |  Fecha: 30/07/2026',
        '',
        'VW Golf 1.4 TSI  (1234ABC) .... 7.500,00 EUR',
        'Tasas de sala  .................. 400,00 EUR',
        'Logistica/grua  ................. 250,00 EUR',
        '---------------------------------------',
        'Base imponible ............... 8.150,00 EUR',
        'IVA 21%  ...................... 1.711,50 EUR',
        'TOTAL  ....................... 9.861,50 EUR',
    ],
)
