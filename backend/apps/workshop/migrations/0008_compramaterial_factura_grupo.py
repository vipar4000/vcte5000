"""Agrupa las líneas de compra por factura (``factura_grupo``).

Se generó a mano con contenido compatible con Django 4.2.8 (versión fijada en
``requirements.txt``), porque el entorno local tenía otra versión instalada y
no conviene que un ``makemigrations`` más nuevo introduzca cambios que el
runtime de producción no entienda.
"""
import uuid

import apps.workshop.models
from django.db import migrations, models


def agrupar_facturas_existentes(apps, schema_editor):
    """Las compras ya guardadas con el mismo número de factura pasan a un grupo.

    Antes de este campo, la factura se identificaba por ``numero_factura``
    (a veces vacío). Aquí se agrupan las que sí lo tienen, para que el
    historial y la corrección las traten como una sola factura. Las que no
    tienen número se quedan como factura individual (su propio uuid).
    """
    CompraMaterial = apps.get_model('workshop', 'CompraMaterial')

    claves = (
        CompraMaterial.objects.exclude(numero_factura='')
        .values('numero_factura', 'proveedor', 'cif_nif', 'fecha_compra')
        .order_by()
    )
    for clave in claves:
        filas = CompraMaterial.objects.filter(**clave)
        if filas.count() < 2:
            continue
        filas.update(factura_grupo=uuid.uuid4().hex)


def sin_reversion(apps, schema_editor):
    """No se toca: al eliminar el campo se pierden los grupos de todos modos."""


class Migration(migrations.Migration):

    dependencies = [
        ('workshop', '0007_compramaterial_pago'),
    ]

    operations = [
        migrations.AddField(
            model_name='compramaterial',
            name='factura_grupo',
            field=models.CharField(
                db_index=True,
                default=apps.workshop.models.nuevo_grupo_factura,
                editable=False,
                help_text='Identifica las líneas que pertenecen a la misma factura.',
                max_length=36,
                verbose_name='grupo de factura',
            ),
        ),
        migrations.RunPython(agrupar_facturas_existentes, sin_reversion),
    ]
