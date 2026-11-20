"""Ficha laboral sin acceso web y datos de pago.

Permite dar de alta trabajadores (obreros, limpieza, auxiliares) que cobran y
fichan con PIN pero no tienen credenciales de acceso al ERP, y configurar su
periodicidad de pago y porcentajes de IRPF y SS obrera.
"""
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_user_rol'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='sin_acceso',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Ficha laboral sin credenciales: aparece en nóminas y puede '
                    'fichar con su PIN, pero no entra al ERP.'
                ),
                verbose_name='trabajador sin acceso web',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='periodicidad_pago',
            field=models.CharField(
                choices=[('MENSUAL', 'Mensual'), ('QUINCENAL', 'Quincenal'),
                         ('SEMANAL', 'Semanal')],
                default='MENSUAL',
                help_text='Mensual, quincenal (2 pagos) o semanal (4 pagos al mes).',
                max_length=10,
                verbose_name='periodicidad de pago',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='porcentaje_irpf',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('6.00'),
                max_digits=5, verbose_name='% IRPF',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='porcentaje_ss_obrera',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('6.35'),
                max_digits=5, verbose_name='% SS obrera',
            ),
        ),
    ]
