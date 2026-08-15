from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0003_add_pgc_accounts_bank'),
        ('workshop', '0005_alter_compramaterial_tipo_inventario'),
    ]

    operations = [
        migrations.AddField(
            model_name='compramaterial',
            name='forma_pago',
            field=models.ForeignKey(
                blank=True,
                help_text='Vacío o 410 = crédito (acreedores). 572 = contado banco (genera EGRESO). 570 = contado caja.',
                limit_choices_to={'codigo__in': ['410', '570', '572']},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='compras_material_forma_pago',
                to='accounting.cuentacontable',
                verbose_name='forma de pago',
            ),
        ),
    ]
