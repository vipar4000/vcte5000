"""Genera las fotos de prueba de los vehículos del protocolo E2E.

Mismo diseño que las imágenes del Golf 1234ABC: cabecera azul con
«FOTO DE PRUEBA - MATRÍCULA - NN VISTA», ilustración plana del coche en el
color del vehículo, y pie «ERP R Car Rogil - material de prueba».

Uso:
    python gen_imagenes_prueba.py                    # los tres coches del protocolo
    python gen_imagenes_prueba.py --destino <carpeta>

Genera 4 vistas por coche: frente, trasero, lateral e interior.
"""
import argparse
import os
from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 2400, 1800
AZUL = (31, 78, 120)
FONDO = (238, 241, 246)
CRISTAL = (191, 228, 247)
FARO = (231, 223, 138)
NEGRO = (17, 17, 17)
GRIS_LLANTA = (166, 169, 173)
ROJO_PILOTO = (198, 40, 40)
BLANCO = (255, 255, 255)
GRIS_TEXTO = (107, 114, 128)

DESTINO_POR_DEFECTO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', '..', '..', 'euro', 'prueba_madrid', 'imagenes',
)

VEHICULOS = [
    {'matricula': '5678DEF', 'modelo': 'SEAT León 2.0 TDI',
     'color': (176, 32, 38), 'contorno': None},
    {'matricula': '9012GHI', 'modelo': 'Renault Mégane 1.5 dCi',
     'color': (228, 230, 233), 'contorno': (140, 145, 152)},
]

VISTAS = [
    ('01', 'frente', 'Vista frontal'),
    ('02', 'trasero', 'Vista trasera'),
    ('03', 'lateral', 'Vista lateral'),
    ('04', 'interior', 'Vista interior'),
]

# Nombres para el paquete de documentos: 01_FRENTE, 02_LATERAL, 03_TRASERA...
VISTAS_DOCUMENTOS = [
    ('01', 'frente', 'Vista frontal', 'FRENTE'),
    ('02', 'lateral', 'Vista lateral', 'LATERAL'),
    ('03', 'trasero', 'Vista trasera', 'TRASERA'),
    ('04', 'interior', 'Vista interior', 'INTERIOR'),
]


def _fuente(nombre, tam):
    rutas = [
        os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', nombre),
        os.path.join('/usr/share/fonts/truetype/dejavu', nombre),
    ]
    for ruta in rutas:
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, tam)
    return ImageFont.load_default()


def cabecera(dibujo, matricula, numero, nombre_vista):
    dibujo.rectangle([0, 0, ANCHO, 150], fill=AZUL)
    texto = f'FOTO DE PRUEBA  -  {matricula}  -  {numero} {nombre_vista.upper()}'
    dibujo.text((70, 45), texto, font=_fuente('arialbd.ttf', 62), fill=BLANCO)


def pie(dibujo, extra=''):
    dibujo.rectangle([0, ALTO - 110, ANCHO, ALTO], fill=AZUL)
    texto = 'ERP R Car Rogil  -  material de prueba (no es un vehículo real)'
    if extra:
        texto += f'  -  {extra}'
    dibujo.text((70, ALTO - 82), texto, font=_fuente('arial.ttf', 34), fill=BLANCO)


def rueda(dibujo, x, y, radio):
    dibujo.ellipse([x - radio, y - radio, x + radio, y + radio], fill=NEGRO)
    r = int(radio * 0.45)
    dibujo.ellipse([x - r, y - r, x + r, y + r], fill=GRIS_LLANTA)


def vista_frente(dibujo, color, contorno=None):
    # techo y parabrisas
    dibujo.polygon([(760, 610), (1640, 610), (1880, 940), (520, 940)],
                   fill=color, outline=contorno)
    dibujo.polygon([(900, 680), (1500, 680), (1660, 900), (740, 900)], fill=CRISTAL)
    # carrocería
    dibujo.rounded_rectangle([300, 900, 2100, 1450], radius=45, fill=color,
                             outline=contorno, width=4)
    # faros
    dibujo.rounded_rectangle([380, 1020, 700, 1140], radius=14, fill=FARO)
    dibujo.rounded_rectangle([1700, 1020, 2020, 1140], radius=14, fill=FARO)
    # parrilla y matrícula
    dibujo.rounded_rectangle([940, 1180, 1460, 1330], radius=16, fill=NEGRO)
    dibujo.rounded_rectangle([1040, 1360, 1360, 1430], radius=8, fill=NEGRO)
    # ruedas
    rueda(dibujo, 620, 1470, 185)
    rueda(dibujo, 1780, 1470, 185)


def vista_trasero(dibujo, color, contorno=None):
    dibujo.polygon([(780, 600), (1620, 600), (1860, 930), (540, 930)],
                   fill=color, outline=contorno)
    dibujo.polygon([(920, 670), (1480, 670), (1640, 890), (760, 890)], fill=CRISTAL)
    dibujo.rounded_rectangle([300, 920, 2100, 1450], radius=45, fill=color,
                             outline=contorno, width=4)
    # pilotos rojos (con borde claro para que se vean sobre carrocería oscura)
    dibujo.rounded_rectangle([350, 1000, 720, 1140], radius=14,
                             fill=ROJO_PILOTO, outline=BLANCO, width=5)
    dibujo.rounded_rectangle([1680, 1000, 2050, 1140], radius=14,
                             fill=ROJO_PILOTO, outline=BLANCO, width=5)
    # portón y matrícula
    dibujo.rounded_rectangle([950, 1150, 1450, 1320], radius=16, fill=NEGRO)
    dibujo.rounded_rectangle([1060, 1350, 1340, 1420], radius=8, fill=NEGRO)
    rueda(dibujo, 620, 1470, 185)
    rueda(dibujo, 1780, 1470, 185)


def vista_lateral(dibujo, color, contorno=None):
    # perfil: cuerpo bajo + cabina
    cuerpo = [(300, 1120), (2080, 1120), (2080, 1420), (300, 1420)]
    cabina = [(700, 1120), (830, 880), (1580, 880), (1780, 1120)]
    dibujo.polygon(cuerpo, fill=color, outline=contorno)
    dibujo.polygon(cabina, fill=color, outline=contorno)

    # ventanillas (dos, separadas por el pilar B)
    dibujo.polygon([(760, 1080), (870, 930), (1150, 930), (1150, 1080)],
                   fill=CRISTAL)
    dibujo.polygon([(1200, 1080), (1200, 930), (1520, 930), (1660, 1080)],
                   fill=CRISTAL)

    # faro delantero y piloto trasero
    dibujo.rounded_rectangle([300, 1150, 400, 1220], radius=10, fill=FARO)
    dibujo.rounded_rectangle([1980, 1140, 2080, 1220], radius=10,
                             fill=ROJO_PILOTO)

    # ruedas
    rueda(dibujo, 720, 1380, 175)
    rueda(dibujo, 1720, 1380, 175)

    # línea de puerta y tirador
    dibujo.line([(1180, 1120), (1180, 1400)], fill=contorno or AZUL, width=5)
    dibujo.rounded_rectangle([1230, 1180, 1310, 1200], radius=5,
                             fill=contorno or AZUL)


def vista_interior(dibujo, color_volante=(45, 45, 45)):
    # salpicadero
    dibujo.rounded_rectangle([280, 620, 2120, 1400], radius=60, fill=(58, 62, 70))
    # consola central
    dibujo.rounded_rectangle([1000, 900, 1400, 1400], radius=40, fill=(40, 43, 50))
    # pantalla
    dibujo.rounded_rectangle([1080, 960, 1320, 1160], radius=14, fill=(120, 170, 210))
    # volante
    cx, cy, r = 760, 1050, 270
    dibujo.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color_volante, width=52)
    dibujo.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], fill=color_volante)
    dibujo.line([(cx - r, cy), (cx - 70, cy)], fill=color_volante, width=34)
    dibujo.line([(cx + 70, cy), (cx + r, cy)], fill=color_volante, width=34)
    dibujo.line([(cx, cy + 70), (cx, cy + r)], fill=color_volante, width=34)
    # asientos delanteros (insinuación)
    dibujo.rounded_rectangle([380, 1300, 700, 1600], radius=40, fill=(40, 43, 50))
    dibujo.rounded_rectangle([1700, 1300, 2020, 1600], radius=40, fill=(40, 43, 50))
    # aireadores
    for x in (980, 1420):
        dibujo.rounded_rectangle([x - 70, 760, x + 70, 860], radius=18,
                                 fill=(90, 94, 102))


def generar(carpeta, matricula, color, modelo, contorno=None, documentos=False):
    os.makedirs(carpeta, exist_ok=True)
    generadas = []
    vistas = VISTAS_DOCUMENTOS if documentos else VISTAS
    for numero, nombre, pie_vista, *_ in vistas:
        imagen = Image.new('RGB', (ANCHO, ALTO), FONDO)
        dibujo = ImageDraw.Draw(imagen)

        cabecera(dibujo, matricula, numero, nombre)
        if nombre == 'frente':
            vista_frente(dibujo, color, contorno)
        elif nombre == 'trasero':
            vista_trasero(dibujo, color, contorno)
        elif nombre == 'lateral':
            vista_lateral(dibujo, color, contorno)
        else:
            vista_interior(dibujo)
        dibujo.text((70, 1580), pie_vista, font=_fuente('arial.ttf', 40),
                    fill=GRIS_TEXTO)
        pie(dibujo, modelo)

        if documentos:
            nombre_archivo = f'{matricula}-{numero}_{nombre.upper()}.jpg'
        else:
            nombre_archivo = f'{matricula}-{numero}-{nombre}.jpg'
        ruta = os.path.join(carpeta, nombre_archivo)
        imagen.save(ruta, 'JPEG', quality=88, optimize=True)
        generadas.append(ruta)
    return generadas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destino', default=DESTINO_POR_DEFECTO)
    parser.add_argument(
        '--documentos', action='store_true',
        help='Nombres 01_FRENTE, 02_LATERAL, 03_TRASERA, 04_INTERIOR.',
    )
    parser.add_argument(
        '--matriculas', default='',
        help='Matrículas separadas por comas (por defecto, todas).',
    )
    opciones = parser.parse_args()

    carpeta = os.path.abspath(opciones.destino)
    filtro = {
        m.strip().upper()
        for m in opciones.matriculas.split(',') if m.strip()
    }
    for vehiculo in VEHICULOS:
        if filtro and vehiculo['matricula'] not in filtro:
            continue
        rutas = generar(
            carpeta, vehiculo['matricula'], vehiculo['color'],
            vehiculo['modelo'], vehiculo.get('contorno'),
            documentos=opciones.documentos,
        )
        for ruta in rutas:
            print('generada:', ruta)


if __name__ == '__main__':
    main()
