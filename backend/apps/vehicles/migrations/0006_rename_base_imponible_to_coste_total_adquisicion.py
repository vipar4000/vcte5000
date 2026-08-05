from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0005_iva_soportado_monto'),
    ]

    operations = [
        migrations.RenameField(
            model_name='vehiculo',
            old_name='base_imponible',
            new_name='coste_total_adquisicion',
        ),
    ]
