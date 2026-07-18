from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from apps.expenses.models import GastoEstructura


class Command(BaseCommand):
    help = (
        'Adjunta un PDF de factura de proveedor a un gasto de estructura '
        'existente y lo sube al almacenamiento (local media/facturas_gastos/ '
        'o Cloudflare R2 en produccion). Uso: python manage.py '
        'subir_factura_gasto --pk 12 --pdf "C:/facturas/alquiler.pdf"'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--pk',
            type=int,
            required=True,
            help='ID (pk) del gasto de estructura ya creado',
        )
        parser.add_argument(
            '--pdf',
            type=str,
            required=True,
            dest='pdf',
            metavar='RUTA',
            help='Ruta local del archivo PDF a adjuntar',
        )

    def handle(self, *args, **options):
        gasto = GastoEstructura.objects.filter(pk=options['pk']).first()
        if not gasto:
            raise CommandError(f'No existe un gasto con pk={options["pk"]}.')

        ruta = options['pdf']
        try:
            f = open(ruta, 'rb')
        except OSError as e:
            raise CommandError(f'No se pudo abrir el archivo "{ruta}": {e}')

        with f:
            nombre = f.name.split('/')[-1].split('\\')[-1]
            gasto.documento_pdf = File(f, name=nombre)
            gasto.save(update_fields=['documento_pdf'])

        self.stdout.write(self.style.SUCCESS(
            f'[OK] Factura PDF adjuntada al gasto pk={gasto.pk} '
            f'({gasto.proveedor_acreedor})'
        ))
        self.stdout.write(f'  URL: {gasto.documento_pdf.url}')
