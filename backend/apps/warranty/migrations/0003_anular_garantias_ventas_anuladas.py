"""Marca como anuladas las garantías de ventas ya anuladas."""
from django.db import migrations


def anular_garantias(apps, schema_editor):
    GarantiaVehiculo = apps.get_model('warranty', 'GarantiaVehiculo')
    for garantia in GarantiaVehiculo.objects.select_related('venta'):
        if garantia.venta.anulada and not garantia.anulada:
            garantia.anulada = True
            garantia.fecha_anulacion = garantia.venta.fecha_anulacion
            garantia.motivo_anulacion = 'Venta anulada'
            garantia.save(update_fields=[
                'anulada', 'fecha_anulacion', 'motivo_anulacion',
            ])


class Migration(migrations.Migration):

    dependencies = [
        ('warranty', '0002_garantia_anulada'),
        ('sales', '0010_ventavehiculo_vehiculo_fk'),
    ]

    operations = [
        migrations.RunPython(anular_garantias, migrations.RunPython.noop),
    ]
