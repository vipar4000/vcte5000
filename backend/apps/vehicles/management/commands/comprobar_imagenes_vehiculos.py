"""Detecta fotos de vehículos cuyo archivo ya no está en el almacenamiento.

En staging el disco es efímero: cada redeploy borra los archivos subidos. Las
filas de la base de datos (`Vehiculo.imagen_principal`, `ImagenVehiculo`) siguen
ahí, pero las URLs devuelven 404 y la web muestra las imágenes rotas.

Este comando:
  - Lista los vehículos con fotos cuya ruta ya no existe.
  - Con `--borrar-huerfanas`, limpia esas referencias (así la galería no enseña
    huecos rotos). Los archivos que sí existen no se tocan.

Uso:
    python manage.py comprobar_imagenes_vehiculos
    python manage.py comprobar_imagenes_vehiculos --borrar-huerfanas
"""
from collections import defaultdict

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from apps.vehicles.models import ImagenVehiculo, Vehiculo


class Command(BaseCommand):
    help = 'Comprueba que los archivos de las fotos de vehículos existan.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--borrar-huerfanas', action='store_true',
            help='Quita las referencias cuyos archivos ya no existen.',
        )

    def handle(self, *args, **opciones):
        faltantes = defaultdict(lambda: {'portada': None, 'galeria': []})
        total_portadas = 0
        total_galeria = 0

        for vehiculo in Vehiculo.objects.exclude(imagen_principal=''):
            total_portadas += 1
            if not default_storage.exists(vehiculo.imagen_principal.name):
                faltantes[vehiculo.matricula]['portada'] = vehiculo

        for foto in ImagenVehiculo.objects.select_related('vehiculo'):
            total_galeria += 1
            if not default_storage.exists(foto.imagen.name):
                faltantes[foto.vehiculo.matricula]['galeria'].append(foto)

        self.stdout.write(
            f'Fotos revisadas: {total_portadas} portada(s) y '
            f'{total_galeria} de galería.'
        )

        if not faltantes:
            self.stdout.write(self.style.SUCCESS(
                'Todas las fotos tienen su archivo en el almacenamiento.'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'\nVehículos con archivos perdidos: {len(faltantes)}'
        ))
        for matricula, datos in sorted(faltantes.items()):
            self.stdout.write(f'  {matricula}:')
            if datos['portada']:
                self.stdout.write(
                    f"    portada: {datos['portada'].imagen_principal.name}"
                )
            for foto in datos['galeria']:
                self.stdout.write(f'    galería: {foto.imagen.name}')

        if not opciones['borrar_huerfanas']:
            self.stdout.write(
                '\nNo se ha cambiado nada. Para limpiar las referencias rotas: '
                'repita con --borrar-huerfanas (después vuelva a subir las fotos).'
            )
            return

        borradas = 0
        for datos in faltantes.values():
            portada = datos['portada']
            if portada is not None:
                Vehiculo.objects.filter(pk=portada.pk).update(imagen_principal='')
            for foto in datos['galeria']:
                foto.delete()
                borradas += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nReferencias limpiadas: {borradas} foto(s) de galería y '
            f'{len([d for d in faltantes.values() if d["portada"]])} portada(s). '
            f'Vuelva a subir las fotos desde 📢 Publicar.'
        ))
