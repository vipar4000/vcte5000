"""DetalleRebu: un registro por factura y vehículo (no OneToOne con el vehículo).

Antes el vehículo era único, así que una rectificativa (o una segunda venta del
mismo coche tras anular la primera) fallaba con
`sales_detallerebu_vehiculo_id_key`.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0008_facturaventa_venta_opcional'),
    ]

    operations = [
        migrations.AlterField(
            model_name='detallerebu',
            name='vehiculo',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='detalles_rebu',
                to='vehicles.vehiculo',
                verbose_name='vehículo',
            ),
        ),
        migrations.AddConstraint(
            model_name='detallerebu',
            constraint=models.UniqueConstraint(
                fields=('factura', 'vehiculo'),
                name='detallerebu_unico_por_factura',
            ),
        ),
    ]
