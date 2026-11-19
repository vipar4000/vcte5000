"""Fecha de vencimiento de la factura de compra (compras a crédito).

Contenido compatible con Django 4.2.8 (versión fijada en requirements.txt);
el entorno local tenía otra versión instalada y no se quiere introducir nada
que el runtime de producción no entienda.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workshop', '0008_compramaterial_factura_grupo'),
    ]

    operations = [
        migrations.AddField(
            model_name='compramaterial',
            name='fecha_vencimiento',
            field=models.DateField(
                blank=True,
                help_text='Solo para compras a crédito: día en que vence la factura.',
                null=True,
                verbose_name='fecha de vencimiento',
            ),
        ),
    ]
