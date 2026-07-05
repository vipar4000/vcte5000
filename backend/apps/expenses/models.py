from django.db import models
from decimal import Decimal


class GastoEstructura(models.Model):
    """Gastos generales del ejercicio no imputables al inventario de vehículos (Cuenta 300 PGC)."""

    CATEGORIAS_GASTO = [
        ('ARRENDAMIENTO', 'Alquiler del Galpón (Cuenta PGC 621)'),
        ('SUMINISTROS', 'Luz, Agua, Conectividad (Cuenta PGC 628)'),
        ('LIMPIEZA_PROD', 'Productos de Limpieza e Insumos Globales (Cuenta PGC 602)'),
        ('LIMPIEZA_SERV', 'Servicios de Empresa de Limpieza Externa (Cuenta PGC 629)'),
        ('NOMINAS_ESTR', 'Salarios Personal Limpieza/Admin (Cuenta PGC 640)'),
        ('SEG_SOCIAL_ESTR', 'Aportes Patronales Personal Estructura (Cuenta PGC 642)'),
        ('IMPUESTOS_ESTR', 'IBI, Tasas Municipales, Vados (Cuenta PGC 631)'),
        ('OTROS', 'Otros gastos no especificados'),
    ]

    MAPPINGS_CATEGORIA_CUENTA = {
        'ARRENDAMIENTO': '621',
        'SUMINISTROS': '628',
        'LIMPIEZA_PROD': '602',
        'LIMPIEZA_SERV': '629',
        'NOMINAS_ESTR': '640',
        'SEG_SOCIAL_ESTR': '642',
        'IMPUESTOS_ESTR': '631',
        'OTROS': '620',
    }

    fecha_factura = models.DateField(verbose_name='fecha de factura')
    proveedor_acreedor = models.CharField(max_length=150, verbose_name='proveedor/acreedor')
    cif_nif = models.CharField(max_length=15, verbose_name='CIF/NIF')
    categoria = models.CharField(max_length=20, choices=CATEGORIAS_GASTO, verbose_name='categoría')
    base_imponible = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='base imponible')
    tipo_iva = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('21.00'), verbose_name='tipo de IVA (%)')
    cuota_iva = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=Decimal('0'), verbose_name='cuota IVA')
    retencion_irpf = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.00'), verbose_name='retención IRPF (%)')
    cuota_retencion = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), editable=False, verbose_name='cuota retención')
    total_factura = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=Decimal('0'), verbose_name='total factura')
    documento_pdf = models.FileField(upload_to='facturas_gastos/', null=True, blank=True, verbose_name='factura PDF')
    pagado = models.BooleanField(default=False, verbose_name='pagado')
    fecha_pago = models.DateField(null=True, blank=True, verbose_name='fecha de pago')

    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='gastos_creados',
        verbose_name='creado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'gasto de estructura'
        verbose_name_plural = 'gastos de estructura'
        ordering = ['-fecha_factura', '-created_at']

    def __str__(self):
        return f"{self.get_categoria_display()} - {self.proveedor_acreedor} ({self.total_factura} EUR)"

    def save(self, *args, **kwargs):
        from decimal import Decimal
        self.cuota_iva = (self.base_imponible * (self.tipo_iva / Decimal('100'))).quantize(Decimal('0.01'))
        self.cuota_retencion = (self.base_imponible * (self.retencion_irpf / Decimal('100'))).quantize(Decimal('0.01'))
        self.total_factura = self.base_imponible + self.cuota_iva - self.cuota_retencion
        super().save(*args, **kwargs)

    @property
    def tiene_retencion(self):
        return self.retencion_irpf > 0

    def crear_asiento_contable(self):
        """Genera el asiento contable PGC automático para este gasto."""
        from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable

        cuenta_gasto_codigo = self.MAPPINGS_CATEGORIA_CUENTA.get(self.categoria, '620')
        cuenta_gasto = CuentaContable.objects.get(codigo=cuenta_gasto_codigo)
        cuenta_iva = CuentaContable.objects.get(codigo='472')
        cuenta_proveedor = CuentaContable.objects.get(codigo='410')

        asiento = AsientoContable.objects.create(
            fecha=self.fecha_factura,
            concepto=f"Gasto {self.get_categoria_display()}: {self.proveedor_acreedor} - Factura {self.cif_nif}",
            estado='BORRADOR',
            tipo_documento='GastoEstructura',
            documento_id=self.pk,
            created_by=self.created_by,
        )

        MovimientoContable.objects.create(
            asiento=asiento,
            cuenta=cuenta_gasto,
            debe=self.base_imponible,
            haber=Decimal('0'),
            descripcion=f"Base imponible - {self.proveedor_acreedor}",
        )

        MovimientoContable.objects.create(
            asiento=asiento,
            cuenta=cuenta_iva,
            debe=self.cuota_iva,
            haber=Decimal('0'),
            descripcion=f"IVA soportado {self.tipo_iva}%",
        )

        if self.tiene_retencion:
            cuenta_retencion = CuentaContable.objects.get(codigo='4751.115')
            MovimientoContable.objects.create(
                asiento=asiento,
                cuenta=cuenta_retencion,
                debe=Decimal('0'),
                haber=self.cuota_retencion,
                descripcion=f"Retención IRPF {self.retencion_irpf}%",
            )
            importe_proveedor = self.total_factura
        else:
            importe_proveedor = self.total_factura

        MovimientoContable.objects.create(
            asiento=asiento,
            cuenta=cuenta_proveedor,
            debe=Decimal('0'),
            haber=importe_proveedor,
            descripcion=f"Proveedor: {self.proveedor_acreedor}",
        )

        return asiento
