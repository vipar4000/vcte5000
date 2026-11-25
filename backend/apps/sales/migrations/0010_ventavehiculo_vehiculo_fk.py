"""Un vehículo puede tener varias ventas (histórico y reventa tras anular)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0009_detallerebu_vehiculo_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ventavehiculo',
            name='vehiculo',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='ventas',
                to='vehicles.vehiculo',
                verbose_name='vehículo',
            ),
        ),
        migrations.AddConstraint(
            model_name='ventavehiculo',
            constraint=models.UniqueConstraint(
                condition=models.Q(anulada=False),
                fields=('vehiculo',),
                name='venta_activa_unica_por_vehiculo',
            ),
        ),
    ]
