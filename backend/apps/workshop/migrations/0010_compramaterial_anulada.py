"""Anulación de compras de material (abono): stock, contra-asiento y banco."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workshop', '0009_compramaterial_fecha_vencimiento'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='compramaterial',
            name='anulada',
            field=models.BooleanField(default=False, verbose_name='anulada'),
        ),
        migrations.AddField(
            model_name='compramaterial',
            name='fecha_anulacion',
            field=models.DateField(blank=True, null=True,
                                   verbose_name='fecha de anulación'),
        ),
        migrations.AddField(
            model_name='compramaterial',
            name='anulada_por',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='compras_material_anuladas',
                to=settings.AUTH_USER_MODEL,
                verbose_name='anulada por',
            ),
        ),
    ]
