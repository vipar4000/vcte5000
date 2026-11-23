"""Fecha en que el vehículo se vendió (visible 30 días en la web)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0008_vehiculo_fecha_publicacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehiculo',
            name='fecha_vendido',
            field=models.DateField(
                blank=True, null=True,
                help_text='Día en que pasó a VENDIDO (se muestra 30 días en la web).',
                verbose_name='fecha de venta',
            ),
        ),
    ]
