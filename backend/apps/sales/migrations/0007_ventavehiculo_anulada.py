"""Anulación de ventas (abono/rectificativa) sin borrar el histórico."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0006_ventavehiculo_pagada_ventavehiculo_total_cobrado_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ventavehiculo',
            name='anulada',
            field=models.BooleanField(default=False, verbose_name='anulada'),
        ),
        migrations.AddField(
            model_name='ventavehiculo',
            name='fecha_anulacion',
            field=models.DateField(blank=True, null=True,
                                   verbose_name='fecha de anulación'),
        ),
        migrations.AddField(
            model_name='ventavehiculo',
            name='motivo_anulacion',
            field=models.CharField(blank=True, max_length=255,
                                   verbose_name='motivo de anulación'),
        ),
        migrations.AddField(
            model_name='ventavehiculo',
            name='anulada_por',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ventas_anuladas',
                to=settings.AUTH_USER_MODEL,
                verbose_name='anulada por',
            ),
        ),
    ]
