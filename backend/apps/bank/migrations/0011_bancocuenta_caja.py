"""Caja de efectivo: cuenta 570 sin IBAN en el módulo de tesorería."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bank', '0010_reserva_fiscal_factura'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bancocuenta',
            name='cuenta_contable',
            field=models.ForeignKey(
                limit_choices_to={'codigo__in': ['570', '572']},
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cuentas_bancarias',
                to='accounting.cuentacontable',
                verbose_name='cuenta contable (570 caja / 572 banco)',
            ),
        ),
        migrations.AlterField(
            model_name='bancocuenta',
            name='iban',
            field=models.CharField(
                blank=True, max_length=34, null=True, unique=True,
                verbose_name='IBAN',
                help_text='Obligatorio en cuentas bancarias. La caja de efectivo '
                          '(570) no tiene IBAN: déjelo vacío.',
            ),
        ),
    ]
