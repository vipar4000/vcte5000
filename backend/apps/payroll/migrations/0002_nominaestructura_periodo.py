"""Periodicidad de la nómina (mensual, quincenal o semanal)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='nominaestructura',
            name='periodo',
            field=models.CharField(
                choices=[('MENSUAL', 'Mensual'), ('QUINCENAL', 'Quincenal'),
                         ('SEMANAL', 'Semanal')],
                default='MENSUAL',
                help_text='Mensual, quincenal o semanal: define qué parte del salario se paga.',
                max_length=10,
                verbose_name='periodicidad',
            ),
        ),
    ]
