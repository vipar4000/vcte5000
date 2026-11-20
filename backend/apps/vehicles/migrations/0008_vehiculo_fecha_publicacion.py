"""Fecha desde la que el vehículo está publicado a la venta.

Contenido compatible con Django 4.2.8 (versión fijada en requirements.txt).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0007_alter_vehiculo_coste_total_adquisicion'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehiculo',
            name='fecha_publicacion',
            field=models.DateField(
                blank=True,
                help_text='Día desde el que el vehículo está expuesto a la venta.',
                null=True,
                verbose_name='fecha de publicación',
            ),
        ),
    ]
