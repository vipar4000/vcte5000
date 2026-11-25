"""Un asiento puede tener varios movimientos de tesorería (traspasos)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bank', '0011_bancocuenta_caja'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bancomovimiento',
            name='asiento_asociado',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='movimientos_banco',
                to='accounting.asientocontable',
                verbose_name='asiento contable',
            ),
        ),
    ]
