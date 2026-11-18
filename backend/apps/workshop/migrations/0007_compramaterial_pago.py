from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0003_add_pgc_accounts_bank'),
        ('workshop', '0006_compramaterial_forma_pago'),
    ]

    operations = [
        migrations.AddField(
            model_name='compramaterial',
            name='pagado',
            field=models.BooleanField(default=False, verbose_name='pagado'),
        ),
        migrations.AddField(
            model_name='compramaterial',
            name='fecha_pago',
            field=models.DateField(blank=True, null=True, verbose_name='fecha de pago'),
        ),
        migrations.AddField(
            model_name='compramaterial',
            name='cuenta_pago',
            field=models.ForeignKey(
                blank=True,
                help_text='Solo aplica a compras a crédito (410): cuenta desde la que se pagará. Vacío = 572.',
                limit_choices_to={'codigo__in': ['570', '572']},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='compras_material_cuenta_pago',
                to='accounting.cuentacontable',
                verbose_name='cuenta de pago (banco/caja)',
            ),
        ),
    ]
