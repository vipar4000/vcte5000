"""
Procesado y nombrado de las fotos de vehículos.

Centraliza lo que antes se hacía a mano en cada punto de subida (formulario
del ERP, admin de Django y comando `subir_imagen_vehiculo`):

* **Reduce y recomprime** la foto a un tamaño razonable, para que el catálogo
  público no sirva imágenes de 6 MB salidas del móvil.
* **La guarda en una carpeta por matrícula** (`vehiculos/1234abc/...`), lo que
  permite localizar y exportar el lote de fotos de un vehículo concreto.
* **Descarta los metadatos EXIF** al recomprimir, incluida la geolocalización
  (una foto hecha en casa no debe publicar dónde está esa casa).

Los originales no se conservan: si más adelante se necesita más resolución
para un portal, hay que partir del archivo original del móvil/ordenador.
"""
import re
import unicodedata
import uuid
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

# Lado mayor del archivo que se guarda (2560 px cubre la ficha a 2x y el zoom).
LADO_MAXIMO = 2560
# Calidad JPEG: 85 es el punto donde no se aprecia pérdida y el peso baja mucho.
CALIDAD_JPEG = 85
# Tope de subida, coherente con `client_max_body_size 20M` de nginx en producción.
PESO_MAXIMO_BYTES = 20 * 1024 * 1024


class ImagenInvalida(Exception):
    """La foto no se puede procesar (demasiado grande, formato no soportado...)."""


def _slug(texto):
    """Convierte '1234-ABC ñ' en '1234-abc' para usarlo en nombres de archivo."""
    normalizado = unicodedata.normalize('NFKD', str(texto or ''))
    ascii_texto = normalizado.encode('ascii', 'ignore').decode('ascii')
    limpio = re.sub(r'[^a-zA-Z0-9]+', '-', ascii_texto).strip('-').lower()
    return limpio or 'sin-matricula'


def nombre_para(matricula, etiqueta):
    """Devuelve la ruta relativa dentro de la carpeta de vehículos.

    El resultado se combina con `upload_to='vehiculos/'` del campo, así que una
    foto principal de 1234ABC queda en `vehiculos/1234abc/portada-ab12cd34.jpg`.
    """
    sufijo = uuid.uuid4().hex[:8]
    return f'{_slug(matricula)}/{_slug(etiqueta)}-{sufijo}.jpg'


def procesar_imagen(archivo, nombre):
    """Reorienta, reduce y recomprime la foto. Devuelve un `ContentFile` JPEG.

    Args:
        archivo: objeto con `.read()` y `.size` (UploadedFile o fichero abierto).
        nombre: ruta relativa que tendrá el archivo (ver `nombre_para`).

    Raises:
        ImagenInvalida: si el archivo excede el tope o no es una imagen legible.
    """
    tamano = getattr(archivo, 'size', None)
    if tamano is not None and tamano > PESO_MAXIMO_BYTES:
        raise ImagenInvalida(
            f'La imagen pesa {tamano / (1024 * 1024):.1f} MB y el máximo son '
            f'{PESO_MAXIMO_BYTES // (1024 * 1024)} MB. Redúzcala antes de subirla.'
        )

    try:
        imagen = Image.open(archivo)
        imagen.load()
    except Exception as exc:
        raise ImagenInvalida(
            'El archivo no es una imagen que el sistema pueda leer '
            '(se admiten JPEG, PNG y WebP).'
        ) from exc

    # Corrige la orientación según EXIF y aplica la rotación antes de descartar
    # los metadatos; si no, las fotos verticales de móvil quedan tumbadas.
    imagen = ImageOps.exif_transpose(imagen)

    if imagen.mode in ('RGBA', 'LA', 'P'):
        # JPEG no tiene transparencia: se compone sobre blanco.
        fondo = Image.new('RGB', imagen.size, (255, 255, 255))
        convertida = imagen.convert('RGBA')
        fondo.paste(convertida, mask=convertida.split()[-1])
        imagen = fondo
    elif imagen.mode != 'RGB':
        imagen = imagen.convert('RGB')

    imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)

    buffer = BytesIO()
    imagen.save(
        buffer,
        format='JPEG',
        quality=CALIDAD_JPEG,
        optimize=True,
        progressive=True,
    )
    return ContentFile(buffer.getvalue(), name=nombre)
