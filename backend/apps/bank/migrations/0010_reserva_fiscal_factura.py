"""Datos fiscales del comprador en la reserva y factura de entrega a cuenta.

La reserva pasa a guardar los mismos datos fiscales que la venta (necesarios
para emitir la factura del anticipo) y se crea `FacturaReserva` con numeración
correlativa por año (A-AAAA-NNNN).
"""
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bank', '0002_bancocuenta_soporte_deposito_bancomovimiento_notas_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='tipo_cliente',
            field=models.CharField(
                choices=[('PARTICULAR', 'Particular (B2C)'),
                         ('EMPRESA', 'Empresa/Autónomo (B2B)')],
                default='PARTICULAR', max_length=15,
                verbose_name='tipo de cliente',
            ),
        ),
        migrations.AddField(
            model_name='reserva',
            name='cliente_direccion',
            field=models.CharField(blank=True, max_length=200,
                                   verbose_name='dirección fiscal'),
        ),
        migrations.AddField(
            model_name='reserva',
            name='cliente_poblacion',
            field=models.CharField(blank=True, max_length=100,
                                   verbose_name='población'),
        ),
        migrations.AddField(
            model_name='reserva',
            name='cliente_provincia',
            field=models.CharField(blank=True, max_length=100,
                                   verbose_name='provincia'),
        ),
        migrations.AddField(
            model_name='reserva',
            name='cliente_cp',
            field=models.CharField(blank=True, max_length=5,
                                   verbose_name='código postal'),
        ),
        migrations.AddField(
            model_name='reserva',
            name='cliente_telefono',
            field=models.CharField(blank=True, max_length=15,
                                   verbose_name='teléfono'),
        ),
        migrations.AddField(
            model_name='reserva',
            name='cliente_email',
            field=models.EmailField(blank=True, max_length=254,
                                    verbose_name='email'),
        ),
        migrations.AddField(
            model_name='reserva',
            name='metodo_pago',
            field=models.CharField(
                choices=[('TRANSFERENCIA', 'Transferencia bancaria'),
                         ('EFECTIVO', 'Efectivo'), ('TARJETA', 'Tarjeta')],
                default='TRANSFERENCIA', max_length=20,
                verbose_name='método de pago',
            ),
        ),
        migrations.AlterField(
            model_name='reserva',
            name='cliente_nombre',
            field=models.CharField(max_length=200,
                                   verbose_name='nombre completo / razón social'),
        ),
        migrations.AlterField(
            model_name='reserva',
            name='cliente_dni',
            field=models.CharField(max_length=9, verbose_name='DNI/NIE/CIF'),
        ),
        migrations.CreateModel(
            name='FacturaReserva',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=20, unique=True,
                                            verbose_name='código')),
                ('fecha_emision', models.DateTimeField(auto_now_add=True,
                                                       verbose_name='fecha de emisión')),
                ('fecha_operacion', models.DateField(verbose_name='fecha de la operación')),
                ('importe', models.DecimalField(decimal_places=2, max_digits=10,
                                                verbose_name='importe recibido')),
                ('metodo_pago', models.CharField(
                    choices=[('TRANSFERENCIA', 'Transferencia bancaria'),
                             ('EFECTIVO', 'Efectivo'), ('TARJETA', 'Tarjeta')],
                    default='TRANSFERENCIA', max_length=20,
                    verbose_name='método de pago')),
                ('concepto', models.CharField(max_length=255, verbose_name='concepto')),
                ('pdf', models.FileField(blank=True, upload_to='reservas/facturas/',
                                         verbose_name='PDF')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='facturas_reserva_creadas',
                    to=settings.AUTH_USER_MODEL, verbose_name='creado por')),
                ('reserva', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='factura', to='bank.reserva',
                    verbose_name='reserva')),
            ],
            options={
                'verbose_name': 'factura de reserva',
                'verbose_name_plural': 'facturas de reserva',
                'ordering': ['-fecha_emision'],
            },
        ),
    ]
