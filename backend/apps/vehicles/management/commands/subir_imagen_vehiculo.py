import os

from django.core.management.base import BaseCommand, CommandError

from apps.vehicles.images import ImagenInvalida, nombre_para, procesar_imagen
from apps.vehicles.models import Vehiculo, ImagenVehiculo


class Command(BaseCommand):
    help = (
        'Sube una o varias imagenes a un vehiculo existente. El vehiculo debe '
        'estar en estado EN_VENTA (las imagenes se descartan en cualquier otro '
        'estado). Cada foto se reduce a 2560 px y se recomprime en JPEG, y se '
        'guarda en su carpeta por matricula. Uso: '
        'python manage.py subir_imagen_vehiculo --matricula 1234ABC '
        '--imagen C:/fotos/golf.jpg [--imagen C:/fotos/lateral.jpg ...] '
        '[--principal]'
    )

    def add_arguments(self, parser):
        grupo = parser.add_mutually_exclusive_group(required=True)
        grupo.add_argument('--matricula', type=str, help='Matricula del vehiculo (7 chars)')
        grupo.add_argument('--pk', type=int, help='ID (pk) del vehiculo')

        parser.add_argument(
            '--imagen',
            action='append',
            required=True,
            dest='imagenes',
            metavar='RUTA',
            help='Ruta local del archivo a subir. Repetible para varias imagenes.',
        )
        parser.add_argument(
            '--principal',
            action='store_true',
            help='Marca la PRIMERA imagen como imagen principal del vehiculo.',
        )

    def handle(self, *args, **options):
        if options['pk']:
            vehiculo = Vehiculo.objects.filter(pk=options['pk']).first()
        else:
            vehiculo = Vehiculo.objects.filter(matricula=options['matricula'].upper()).first()

        if not vehiculo:
            raise CommandError('Vehiculo no encontrado.')

        if vehiculo.estado != 'EN_VENTA':
            raise CommandError(
                f'El vehiculo esta en estado "{vehiculo.estado}". Las imagenes solo '
                f'se suben en estado EN_VENTA. Cambie el estado y reintente.'
            )

        rutas = options['imagenes']
        principal = options['principal']
        ya_tiene = vehiculo.imagenes.count()

        for i, ruta in enumerate(rutas):
            # Nombre legible a partir del archivo original (1234ABC-01-frente.jpg)
            etiqueta = os.path.splitext(os.path.basename(ruta))[0]
            try:
                with open(ruta, 'rb') as f:
                    contenido = procesar_imagen(
                        f, nombre_para(vehiculo.matricula, etiqueta)
                    )
            except OSError as e:
                raise CommandError(f'No se pudo abrir el archivo "{ruta}": {e}')
            except ImagenInvalida as e:
                raise CommandError(f'"{ruta}": {e}')

            if i == 0 and principal:
                if vehiculo.imagen_principal:
                    vehiculo.imagen_principal.delete(save=False)
                vehiculo.imagen_principal.save(contenido.name, contenido, save=True)
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] Imagen principal subida: {vehiculo.imagen_principal.url}'
                ))
            else:
                extra = ImagenVehiculo.objects.create(
                    vehiculo=vehiculo,
                    imagen=contenido,
                    orden=ya_tiene + i + 1,
                )
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] Imagen adicional subida: {extra.imagen.url}'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'--- Vehiculo {vehiculo.matricula} ({vehiculo.estado}) ---'
        ))
        self.stdout.write(f'  Principal: {vehiculo.imagen_principal.url if vehiculo.imagen_principal else "(sin imagen principal)"}')
        self.stdout.write(f'  Galeria  : {vehiculo.imagenes.count()} imagen(es) adicional(es)')
