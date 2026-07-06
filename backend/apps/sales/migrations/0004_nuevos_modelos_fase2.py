import django.conf
import django.db.models.deletion
from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0003_trigger_inmutabilidad_facturas'),
        ('vehicles', '0001_initial'),
        ('accounting', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FacturaVenta',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo_factura', models.CharField(max_length=30, unique=True, verbose_name='código de factura')),
                ('tipo_factura', models.CharField(choices=[('F1', 'Factura ordinaria'), ('F2', 'Factura simplificada'), ('R1', 'Factura rectificativa (error)'), ('R4', 'Factura rectificativa (devolución)')], default='F1', max_length=2, verbose_name='tipo de factura')),
                ('fecha_emision', models.DateTimeField(auto_now_add=True, verbose_name='fecha de emisión')),
                ('fecha_operacion', models.DateField(verbose_name='fecha de operación')),
                ('cliente_nif', models.CharField(max_length=9, verbose_name='NIF cliente')),
                ('cliente_nombre', models.CharField(max_length=200, verbose_name='nombre cliente')),
                ('precio_venta_total', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='total facturado')),
                ('base_imponible_rebu', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='base imponible REBU')),
                ('iva_repercutido', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='IVA repercutido')),
                ('hash_verifactu', models.CharField(blank=True, max_length=64, verbose_name='hash SHA-256 VeriFactu')),
                ('qr_code', models.ImageField(blank=True, upload_to='verifactu/qr/', verbose_name='código QR VeriFactu')),
                ('contabilizada', models.BooleanField(default=False, verbose_name='contabilizada')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('factura_rectificada', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rectificativas', to='sales.facturaventa', verbose_name='factura rectificada')),
                ('venta', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='factura', to='sales.ventavehiculo', verbose_name='venta')),
            ],
            options={
                'verbose_name': 'factura de venta',
                'verbose_name_plural': 'facturas de venta',
                'ordering': ['-fecha_operacion', '-codigo_factura'],
            },
        ),
        migrations.CreateModel(
            name='DetalleRebu',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('precio_adquisicion', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='coste total adquisición')),
                ('precio_venta_final', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='precio de venta')),
                ('factura', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles_rebu', to='sales.facturaventa', verbose_name='factura')),
                ('vehiculo', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='detalle_rebu', to='vehicles.vehiculo', verbose_name='vehículo')),
            ],
            options={
                'verbose_name': 'detalle REBU',
                'verbose_name_plural': 'detalles REBU',
            },
        ),
        migrations.CreateModel(
            name='CostoAcondicionamiento',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(verbose_name='fecha del gasto')),
                ('proveedor', models.CharField(max_length=150, verbose_name='proveedor')),
                ('cif_nif', models.CharField(max_length=9, verbose_name='CIF/NIF proveedor')),
                ('numero_factura', models.CharField(max_length=50, verbose_name='nº factura proveedor')),
                ('categoria', models.CharField(choices=[('PINTURA', 'Pintura'), ('MECANICA', 'Mecánica'), ('ELECTRICIDAD', 'Electricidad'), ('CARROCERIA', 'Carrocería'), ('DOCUMENTACION', 'Documentación y homologación'), ('LIMPIEZA', 'Limpieza y detallado'), ('OTROS', 'Otros gastos de acondicionamiento')], max_length=20, verbose_name='categoría')),
                ('descripcion', models.TextField(verbose_name='descripción')),
                ('base_imponible', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='base imponible')),
                ('tipo_iva', models.DecimalField(decimal_places=2, default=Decimal('21.00'), max_digits=4, verbose_name='tipo IVA (%)')),
                ('cuota_iva', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='cuota IVA (no deducible)')),
                ('total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='total (suma al coste del vehículo)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('asiento_contable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='costos_acondicionamiento', to='accounting.asientocontable', verbose_name='asiento contable')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='costos_acondicionamiento_creados', to=django.conf.settings.AUTH_USER_MODEL, verbose_name='creado por')),
                ('vehiculo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='costos_acondicionamiento', to='vehicles.vehiculo', verbose_name='vehículo')),
            ],
            options={
                'verbose_name': 'costo de acondicionamiento',
                'verbose_name_plural': 'costos de acondicionamiento',
                'ordering': ['-fecha'],
            },
        ),
    ]
