"""La venta de una factura rectificativa es opcional (se vincula a la original)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0007_ventavehiculo_anulada'),
    ]

    operations = [
        migrations.AlterField(
            model_name='facturaventa',
            name='venta',
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='factura', to='sales.ventavehiculo',
                verbose_name='venta',
                help_text='Vacío en las facturas rectificativas (se vinculan a la '
                          'factura original, no a una venta nueva).',
            ),
        ),
    ]
