from django.db import models
from django.conf import settings
from decimal import Decimal


class VentaVehiculo(models.Model):
    """Modelo de venta de vehículo."""
    
    METODOS_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('FINANCIADO', 'Financiado'),
        ('MIXTO', 'Mixto'),
    ]
    
    TIPOS_CLIENTE = [
        ('PARTICULAR', 'Particular (B2C)'),
        ('EMPRESA', 'Empresa/Autónomo (B2B)'),
    ]
    
    vehiculo = models.OneToOneField(
        'vehicles.Vehiculo', 
        on_delete=models.PROTECT,
        related_name='venta',
        verbose_name='vehículo'
    )
    
    # Datos del cliente
    tipo_cliente = models.CharField(
        max_length=15, 
        choices=TIPOS_CLIENTE,
        verbose_name='tipo de cliente'
    )
    cliente_nombre = models.CharField(max_length=200, verbose_name='nombre del cliente')
    cliente_dni = models.CharField(max_length=9, verbose_name='DNI/NIE')
    cliente_direccion = models.TextField(verbose_name='dirección')
    cliente_poblacion = models.CharField(max_length=100, verbose_name='población')
    cliente_provincia = models.CharField(max_length=100, verbose_name='provincia')
    cliente_cp = models.CharField(max_length=5, verbose_name='código postal')
    cliente_telefono = models.CharField(max_length=15, verbose_name='teléfono')
    cliente_email = models.EmailField(verbose_name='email')
    
    # Datos de la venta
    fecha_venta = models.DateField(verbose_name='fecha de venta')
    metodo_pago = models.CharField(
        max_length=20, 
        choices=METODOS_PAGO,
        verbose_name='método de pago'
    )
    
    # Precios
    precio_venta = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name='precio de venta'
    )
    coste_total = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name='coste total del vehículo'
    )
    margen_porcentaje = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=15.00,
        verbose_name='margen de ganancia %'
    )
    
    # IVA REBU
    base_imponible = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        verbose_name='base imponible (margen)'
    )
    cuota_iva = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        verbose_name='cuota IVA REBU'
    )
    
    # PDFs generados
    contrato_pdf = models.FileField(
        upload_to='contratos/', 
        blank=True,
        verbose_name='contrato de compraventa'
    )
    mandato_pdf = models.FileField(
        upload_to='mandatos/', 
        blank=True,
        verbose_name='mandato de gestoría'
    )
    
    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT,
        related_name='ventas_creadas',
        verbose_name='creado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Contabilidad
    asiento_contable = models.OneToOneField(
        'accounting.AsientoContable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='venta',
        verbose_name='asiento contable'
    )
    
    class Meta:
        verbose_name = 'venta de vehículo'
        verbose_name_plural = 'ventas de vehículos'
        ordering = ['-fecha_venta']
    
    def __str__(self):
        return f"Venta {self.vehiculo} a {self.cliente_nombre}"
    
    def save(self, *args, **kwargs):
        # REBU: precio_venta incluye IVA. Base = margen / 1.21
        coste = self.coste_total or Decimal('0')
        margen = self.precio_venta - coste
        if margen > 0:
            self.base_imponible = (margen / Decimal('1.21')).quantize(Decimal('0.01'))
            self.cuota_iva = (self.base_imponible * Decimal('0.21')).quantize(Decimal('0.01'))
        else:
            self.base_imponible = Decimal('0')
            self.cuota_iva = Decimal('0')

        super().save(*args, **kwargs)
    
    @property
    def beneficio(self):
        """Beneficio de la venta (margen bruto)."""
        return self.precio_venta - self.coste_total
    
    @property
    def precio_final_cliente(self):
        """Precio que paga el cliente (con IVA REBU incluido)."""
        return self.precio_venta
    
    def crear_asiento_contable(self):
        """Genera asiento contable automático para esta venta REBU."""
        from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable
        
        cuenta_banco = CuentaContable.objects.get(codigo='572')
        cuenta_ventas = CuentaContable.objects.get(codigo='700')
        cuenta_iva = CuentaContable.objects.get(codigo='471')
        cuenta_compras = CuentaContable.objects.get(codigo='600')
        cuenta_mercancias = CuentaContable.objects.get(codigo='310')
        
        asiento = AsientoContable.objects.create(
            fecha=self.fecha_venta,
            concepto=f"Venta vehículo {self.vehiculo} a {self.cliente_nombre}",
            estado='BORRADOR',
            tipo_documento='VentaVehiculo',
            documento_id=self.pk,
            created_by=self.created_by,
        )
        
        MovimientoContable.objects.create(
            asiento=asiento, cuenta=cuenta_banco,
            debe=self.precio_venta, haber=Decimal('0'),
            descripcion=f"Cobro cliente {self.cliente_nombre}",
        )
        
        MovimientoContable.objects.create(
            asiento=asiento, cuenta=cuenta_compras,
            debe=self.coste_total, haber=Decimal('0'),
            descripcion=f"Coste adquisición {self.vehiculo}",
        )
        
        MovimientoContable.objects.create(
            asiento=asiento, cuenta=cuenta_ventas,
            debe=Decimal('0'), haber=self.base_imponible,
            descripcion="Ingresos por venta (margen REBU)",
        )
        
        MovimientoContable.objects.create(
            asiento=asiento, cuenta=cuenta_iva,
            debe=Decimal('0'), haber=self.cuota_iva,
            descripcion="IVA REBU 21% sobre margen",
        )
        
        MovimientoContable.objects.create(
            asiento=asiento, cuenta=cuenta_mercancias,
            debe=Decimal('0'), haber=self.coste_total,
            descripcion=f"Baja inventario {self.vehiculo}",
        )
        
        self.asiento_contable = asiento
        self.save(update_fields=['asiento_contable'])
        
        return asiento
