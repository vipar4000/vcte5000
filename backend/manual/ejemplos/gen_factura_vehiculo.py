# Genera un PDF mínimo para la factura de compra del vehículo (Paso 2.1)
path = r'C:\eurocar\backend\manual\ejemplos\factura_vehiculo_golf.pdf'

objects = []

# Objeto 1 - Catalog
objects.append(b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')

# Objeto 2 - Pages
objects.append(b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n')

# Objeto 3 - Page
objects.append(b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n')

# Objeto 4 - Stream con texto
stream_data = (
    b'BT /F1 14 Tf 50 730 Td (FACTURA DE COMPRA) Tj\n'
    b'BT /F1 10 Tf 50 690 Td (Proveedor: Subastas Online S.A.) Tj\n'
    b'BT /F1 10 Tf 50 670 Td (CIF: B12345678) Tj\n'
    b'BT /F1 10 Tf 50 650 Td (Factura: FC-2026-001 / Fecha: 01/07/2026) Tj\n'
    b'BT /F1 10 Tf 50 620 Td (Vehiculo: Volkswagen Golf 1.6 TDI) Tj\n'
    b'BT /F1 10 Tf 50 600 Td (Bastidor: VW000001 / Matricula: 1234ABC) Tj\n'
    b'BT /F1 10 Tf 50 570 Td (Precio subasta: ......................... 7.500,00 EUR) Tj\n'
    b'BT /F1 10 Tf 50 550 Td (Tasas sala: ........................... 400,00 EUR) Tj\n'
    b'BT /F1 10 Tf 50 530 Td (Logistica/grua: ....................... 250,00 EUR) Tj\n'
    b'BT /F1 10 Tf 50 500 Td (Base imponible: ...................... 8.150,00 EUR) Tj\n'
    b'BT /F1 10 Tf 50 480 Td (IVA 21% (s/tasas+logistica): .......... 136,50 EUR) Tj\n'
    b'BT /F1 10 Tf 50 450 Td (---) Tj\n'
    b'BT /F1 12 Tf 50 420 Td (TOTAL: ................................ 8.286,50 EUR) Tj\n'
    b'BT /F1 9 Tf 50 380 Td (Forma de pago: Transferencia bancaria - Banco Santander (572)) Tj\n'
    b'BT /F1 9 Tf 50 360 Td (Vencimiento: Pago inmediato) Tj\n'
)
obj4 = b'4 0 obj\n<< /Length ' + str(len(stream_data)).encode() + b' >>\nstream\n' + stream_data + b'endstream\nendobj\n'
objects.append(obj4)

# Objeto 5 - Font
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

import os
size = os.path.getsize(path)
print(f'PDF creado: {path}')
print(f'Tamano: {size} bytes')
