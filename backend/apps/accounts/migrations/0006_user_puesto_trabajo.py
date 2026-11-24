"""Puesto de trabajo del empleado (aparece en el recibo de nómina)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_ficha_laboral'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='puesto_trabajo',
            field=models.CharField(
                blank=True, max_length=100,
                help_text='Aparece en el recibo de nómina (ej.: Mecánico, Gerente).',
                verbose_name='puesto de trabajo',
            ),
        ),
    ]
