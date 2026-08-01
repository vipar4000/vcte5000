from django.db import models
from django.conf import settings
from decimal import Decimal
import hashlib
import json


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

    # Cobros fraccionados
    total_cobrado = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        verbose_name='total cobrado',
        help_text='Actualizado automáticamente al recibir plazos',
    )
    pagada = models.BooleanField(
        default=False, verbose_name='pagada',
        help_text='True cuando total_cobrado >= precio_venta',
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

    def actualizar_estado_cobros(self):
        """Actualiza el estado de pago según cobros recibidos."""
        from django.db.models import Sum
        self.total_cobrado = self.cobros.filter(
            estado='RECIBIDO'
        ).aggregate(total=Sum('importe'))['total'] or Decimal('0')
        if self.total_cobrado >= self.precio_venta:
            self.pagada = True
        self.save(update_fields=['total_cobrado', 'pagada'])
    
    def crear_asiento_contable(self):
        """Genera asiento contable automático para esta venta REBU."""
        from django.db import transaction
        from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable
        from apps.accounting.views import generar_numero_asiento

        with transaction.atomic():
            cuenta_banco = CuentaContable.objects.get(codigo='572')
            cuenta_clientes = CuentaContable.objects.get(codigo='430')
            cuenta_ventas = CuentaContable.objects.get(codigo='700')
            cuenta_iva = CuentaContable.objects.get(codigo='471')
            cuenta_mercancias = CuentaContable.objects.get(codigo='310')

            asiento = AsientoContable.objects.create(
                numero=generar_numero_asiento(),
                fecha=self.fecha_venta,
                concepto=f"Venta vehículo {self.vehiculo} a {self.cliente_nombre}",
                estado='BORRADOR',
                tipo_documento='VentaVehiculo',
                documento_id=self.pk,
                created_by=self.created_by,
            )

            # Debe: según método de pago
            if self.metodo_pago in ('EFECTIVO', 'TRANSFERENCIA'):
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_banco,
                    debe=self.precio_venta, haber=Decimal('0'),
                    descripcion=f"Cobro cliente {self.cliente_nombre}",
                )
            elif self.metodo_pago == 'FINANCIADO':
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_clientes,
                    debe=self.precio_venta, haber=Decimal('0'),
                    descripcion=f"Cliente {self.cliente_nombre} (crédito)",
                )
            else:
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_banco,
                    debe=self.precio_venta, haber=Decimal('0'),
                    descripcion=f"Cobro cliente {self.cliente_nombre}",
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

            coste_inventario = self.vehiculo.coste_total
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_mercancias,
                debe=Decimal('0'), haber=coste_inventario,
                descripcion=f"Baja inventario {self.vehiculo}",
            )

            self.asiento_contable = asiento
            self.save(update_fields=['asiento_contable'])

            if asiento.esta_cuadrado:
                asiento.estado = 'POSTEADO'
                asiento.save(update_fields=['estado'])

            return asiento

    def registrar_movimiento_banco(self, asiento=None):
        """Registra el ingreso bancario del cobro de la venta."""
        from apps.bank.services import crear_movimiento_banco, obtener_cuenta_banco_default

        cuenta = obtener_cuenta_banco_default()
        if not cuenta:
            return None
        return crear_movimiento_banco(
            banco_cuenta=cuenta,
            fecha=self.fecha_venta,
            concepto=f"Cobro venta {self.vehiculo} - {self.cliente_nombre}",
            tipo='INGRESO',
            importe=self.precio_venta,
            vehiculo=self.vehiculo,
            asiento=asiento or self.asiento_contable,
        )


class FacturaVenta(models.Model):
    """Factura de venta - cumplimiento VeriFactu / REBU."""
    
    TIPOS_FACTURA = [
        ('F1', 'Factura ordinaria'),
        ('F2', 'Factura simplificada'),
        ('R1', 'Factura rectificativa (error)'),
        ('R4', 'Factura rectificativa (devolución)'),
    ]
    
    codigo_factura = models.CharField(
        max_length=30, unique=True, verbose_name='código de factura'
    )
    tipo_factura = models.CharField(
        max_length=2, choices=TIPOS_FACTURA, default='F1',
        verbose_name='tipo de factura'
    )
    
    venta = models.OneToOneField(
        VentaVehiculo, on_delete=models.PROTECT,
        related_name='factura', verbose_name='venta'
    )
    
    # Referencia a factura rectificada
    factura_rectificada = models.ForeignKey(
        'self', on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='rectificativas',
        verbose_name='factura rectificada'
    )
    
    # Fechas
    fecha_emision = models.DateTimeField(auto_now_add=True, verbose_name='fecha de emisión')
    fecha_operacion = models.DateField(verbose_name='fecha de operación')
    
    # Datos cliente (snapshot de la venta)
    cliente_nif = models.CharField(max_length=9, verbose_name='NIF cliente')
    cliente_nombre = models.CharField(max_length=200, verbose_name='nombre cliente')
    
    # Importes
    precio_venta_total = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='total facturado'
    )
    base_imponible_rebu = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='base imponible REBU'
    )
    iva_repercutido = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='IVA repercutido'
    )
    
    # VeriFactu
    hash_verifactu = models.CharField(
        max_length=64, blank=True, verbose_name='hash SHA-256 VeriFactu'
    )
    qr_code = models.ImageField(
        upload_to='verifactu/qr/', blank=True,
        verbose_name='código QR VeriFactu'
    )
    
    # Estado
    contabilizada = models.BooleanField(default=False, verbose_name='contabilizada')
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'factura de venta'
        verbose_name_plural = 'facturas de venta'
        ordering = ['-fecha_operacion', '-codigo_factura']
    
    def __str__(self):
        return f"{self.codigo_factura} - {self.cliente_nombre} (€{self.precio_venta_total})"
    
    def save(self, *args, **kwargs):
        if not self.hash_verifactu:
            self.hash_verifactu = self._calcular_hash()
        super().save(*args, **kwargs)
    
    def _calcular_hash(self):
        """Calcula hash SHA-256 para VeriFactu (encadenamiento criptográfico)."""
        datos = json.dumps({
            'codigo_factura': self.codigo_factura,
            'tipo_factura': self.tipo_factura,
            'fecha_operacion': str(self.fecha_operacion),
            'cliente_nif': self.cliente_nif,
            'precio_venta_total': str(self.precio_venta_total),
            'base_imponible_rebu': str(self.base_imponible_rebu),
            'iva_repercutido': str(self.iva_repercutido),
        }, sort_keys=True)
        
        # Encadenar con hash anterior si existe
        hash_anterior = FacturaVenta.objects.order_by('-pk').values_list(
            'hash_verifactu', flat=True
        ).first()
        
        payload = (hash_anterior or '') + datos
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    @classmethod
    def generar_siguiente_codigo(cls):
        """Genera el siguiente código de factura: FACT-YYYY-XXXX"""
        from django.utils import timezone
        year = timezone.now().year
        ultima = cls.objects.filter(
            codigo_factura__startswith=f'FACT-{year}'
        ).order_by('-codigo_factura').first()
        
        if ultima:
            try:
                numero = int(ultima.codigo_factura.split('-')[-1]) + 1
            except (ValueError, IndexError):
                numero = 1
        else:
            numero = 1
        
        return f'FACT-{year}-{numero:04d}'


class DetalleRebu(models.Model):
    """Detalle REBU - cálculo interno del margen por vehículo."""
    
    factura = models.ForeignKey(
        FacturaVenta, on_delete=models.CASCADE,
        related_name='detalles_rebu', verbose_name='factura'
    )
    vehiculo = models.OneToOneField(
        'vehicles.Vehiculo', on_delete=models.PROTECT,
        related_name='detalle_rebu', verbose_name='vehículo'
    )
    
    precio_adquisicion = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='coste total adquisición'
    )
    precio_venta_final = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='precio de venta'
    )
    
    class Meta:
        verbose_name = 'detalle REBU'
        verbose_name_plural = 'detalles REBU'
    
    def __str__(self):
        return f"REBU {self.vehiculo} - Margen: €{self.margen_bruto}"
    
    @property
    def margen_bruto(self):
        return self.precio_venta_final - self.precio_adquisicion
    
    @property
    def base_imponible_oculta(self):
        """Base imponible oculta: margen / 1.21"""
        if self.margen_bruto > 0:
            return (self.margen_bruto / Decimal('1.21')).quantize(Decimal('0.01'))
        return Decimal('0.00')
    
    @property
    def iva_repercutido_oculto(self):
        """IVA oculto REBU: base * 21%"""
        if self.margen_bruto > 0:
            return (self.base_imponible_oculta * Decimal('0.21')).quantize(Decimal('0.01'))
        return Decimal('0.00')


class CostoAcondicionamiento(models.Model):
    """Gastos de acondicionamiento de vehículo (IVA NO deducible REBU)."""
    
    CATEGORIAS = [
        ('PINTURA', 'Pintura'),
        ('MECANICA', 'Mecánica'),
        ('ELECTRICIDAD', 'Electricidad'),
        ('CARROCERIA', 'Carrocería'),
        ('DOCUMENTACION', 'Documentación y homologación'),
        ('LIMPIEZA', 'Limpieza y detallado'),
        ('OTROS', 'Otros gastos de acondicionamiento'),
    ]
    
    vehiculo = models.ForeignKey(
        'vehicles.Vehiculo', on_delete=models.PROTECT,
        related_name='costos_acondicionamiento',
        verbose_name='vehículo'
    )
    
    fecha = models.DateField(verbose_name='fecha del gasto')
    proveedor = models.CharField(max_length=150, verbose_name='proveedor')
    cif_nif = models.CharField(max_length=9, verbose_name='CIF/NIF proveedor')
    numero_factura = models.CharField(max_length=50, verbose_name='nº factura proveedor')
    categoria = models.CharField(
        max_length=20, choices=CATEGORIAS,
        verbose_name='categoría'
    )
    descripcion = models.TextField(verbose_name='descripción')
    
    # Importes (IVA no deducible - va al coste del vehículo)
    base_imponible = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='base imponible'
    )
    tipo_iva = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('21.00'),
        verbose_name='tipo IVA (%)'
    )
    cuota_iva = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='cuota IVA (no deducible)'
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='total (suma al coste del vehículo)'
    )
    
    # Contabilidad
    asiento_contable = models.ForeignKey(
        'accounting.AsientoContable', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='costos_acondicionamiento',
        verbose_name='asiento contable'
    )
    
    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='costos_acondicionamiento_creados',
        verbose_name='creado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'costo de acondicionamiento'
        verbose_name_plural = 'costos de acondicionamiento'
        ordering = ['-fecha']
    
    def __str__(self):
        return f"{self.get_categoria_display()} - {self.vehiculo} (€{self.total})"
    
    def save(self, *args, **kwargs):
        # IVA no deducible: se suma al total, NO va a cuenta 472
        self.cuota_iva = (self.base_imponible * (self.tipo_iva / Decimal('100'))).quantize(Decimal('0.01'))
        self.total = self.base_imponible + self.cuota_iva
        super().save(*args, **kwargs)
    
    @property
    def bloqueada(self):
        """No se pueden añadir gastos si el vehículo ya está vendido."""
        return self.vehiculo.estado == 'VENDIDO'
    
    def crear_asiento_contable(self):
        """Genera asiento: IVA va a cuenta de gasto (623), NO a 472."""
        from django.db import transaction
        from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable
        from apps.accounting.views import generar_numero_asiento

        with transaction.atomic():
            cuenta_gasto = CuentaContable.objects.get(codigo='623')
            cuenta_proveedor = CuentaContable.objects.get(codigo='410')

            asiento = AsientoContable.objects.create(
                numero=generar_numero_asiento(),
                fecha=self.fecha,
                concepto=f"Acondicionamiento {self.get_categoria_display()}: {self.vehiculo} - {self.proveedor}",
                estado='BORRADOR',
                tipo_documento='CostoAcondicionamiento',
                documento_id=self.pk,
                created_by=self.created_by,
            )

            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_gasto,
                debe=self.total, haber=Decimal('0'),
                descripcion=f"{self.descripcion[:100]} (IVA incluido, no deducible)",
            )

            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_proveedor,
                debe=Decimal('0'), haber=self.total,
                descripcion=f"Proveedor: {self.proveedor}",
            )

            self.asiento_contable = asiento
            self.save(update_fields=['asiento_contable'])

            return asiento


# =============================================================================
# COBROS FRACCIONADOS
# =============================================================================

class CobroFraccionado(models.Model):
    """Pagos fraccionados / plazos asociados a una venta."""

    TIPOS_FINANCIACION = [
        ('CONTADO', 'Contado'),
        ('DIRECTA', 'Financiación Directa S.L.'),
        ('EXTERNA', 'Financiación Bancaria Externa'),
    ]

    venta = models.ForeignKey(
        VentaVehiculo,
        on_delete=models.CASCADE,
        related_name='cobros',
        verbose_name='venta',
    )
    fecha_vencimiento = models.DateField(verbose_name='fecha de vencimiento')
    importe = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='importe del plazo'
    )
    estado = models.CharField(
        max_length=15,
        choices=[('PENDIENTE', 'Pendiente'), ('RECIBIDO', 'Recibido')],
        default='PENDIENTE',
        verbose_name='estado',
    )
    banco_movimiento = models.OneToOneField(
        'bank.BancoMovimiento',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cobro_fraccionado',
        verbose_name='movimiento bancario',
    )
    tipo_financiacion = models.CharField(
        max_length=10,
        choices=TIPOS_FINANCIACION,
        default='CONTADO',
        verbose_name='tipo de financiación',
    )
    comision_financiera = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'),
        verbose_name='comisión financiera',
    )
    numero_plazo = models.PositiveIntegerField(verbose_name='número de plazo')
    notas = models.TextField(blank=True, verbose_name='notas')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'cobro fraccionado'
        verbose_name_plural = 'cobros fraccionados'
        ordering = ['fecha_vencimiento']
        unique_together = ['venta', 'numero_plazo']

    def __str__(self):
        return f"Plazo {self.numero_plazo} - {self.venta} (€{self.importe})"

    def recibir(self, user):
        """
        Marca el plazo como recibido y crea el asiento contable correspondiente.
        """
        from django.db import transaction
        from apps.accounting.models import AsientoContable, MovimientoContable, CuentaContable
        from apps.accounting.views import generar_numero_asiento
        from apps.bank.services import crear_movimiento_banco, obtener_cuenta_banco_default

        with transaction.atomic():
            banco_cuenta = obtener_cuenta_banco_default()
            if not banco_cuenta:
                raise ValueError('No hay cuentas bancarias configuradas')

            # Crear movimiento bancario
            if self.tipo_financiacion == 'EXTERNA' and self.comision_financiera > 0:
                # Financiación externa: importe neto + comisión
                importe_neto = self.importe - self.comision_financiera
                movimiento = crear_movimiento_banco(
                    banco_cuenta=banco_cuenta,
                    fecha=self.fecha_vencimiento,
                    concepto=f"Cobro financiación externa - {self.venta.vehiculo} (plazo {self.numero_plazo})",
                    tipo='INGRESO',
                    importe=importe_neto,
                )
            else:
                movimiento = crear_movimiento_banco(
                    banco_cuenta=banco_cuenta,
                    fecha=self.fecha_vencimiento,
                    concepto=f"Cobro plazo {self.numero_plazo} - {self.venta.vehiculo}",
                    tipo='INGRESO',
                    importe=self.importe,
                )

            # Crear asiento contable
            cuenta_banco = CuentaContable.objects.get(codigo='572')
            cuenta_clientes = CuentaContable.objects.get(codigo='430')

            asiento = AsientoContable.objects.create(
                numero=generar_numero_asiento(),
                fecha=self.fecha_vencimiento,
                concepto=f"Cobro plazo {self.numero_plazo} - {self.venta.vehiculo} a {self.venta.cliente_nombre}",
                estado='BORRADOR',
                tipo_documento='CobroFraccionado',
                documento_id=self.pk,
                created_by=user,
            )

            if self.tipo_financiacion == 'EXTERNA' and self.comision_financiera > 0:
                # Financiación externa: DEBE banco + DEBE comisión, HABER clientes
                importe_neto = self.importe - self.comision_financiera
                cuenta_comision = CuentaContable.objects.get(codigo='626')

                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_banco,
                    debe=importe_neto, haber=Decimal('0'),
                    descripcion=f"Ingreso neto financiación",
                )
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_comision,
                    debe=self.comision_financiera, haber=Decimal('0'),
                    descripcion=f"Comisión financiera",
                )
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_clientes,
                    debe=Decimal('0'), haber=self.importe,
                    descripcion=f"Cliente {self.venta.cliente_nombre}",
                )
            else:
                # Financiación directa o contado: DEBE banco, HABER clientes
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_banco,
                    debe=self.importe, haber=Decimal('0'),
                    descripcion=f"Cobro plazo {self.numero_plazo}",
                )
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_clientes,
                    debe=Decimal('0'), haber=self.importe,
                    descripcion=f"Cliente {self.venta.cliente_nombre}",
                )

            # Actualizar estado
            self.estado = 'RECIBIDO'
            self.banco_movimiento = movimiento
            self.save(update_fields=['estado', 'banco_movimiento'])

            # Actualizar estado de la venta
            self.venta.actualizar_estado_cobros()

            return asiento

    @property
    def total_cobrado_venta(self):
        """Total cobrado de la venta hasta este plazo."""
        from django.db.models import Sum
        return CobroFraccionado.objects.filter(
            venta=self.venta, estado='RECIBIDO'
        ).aggregate(total=Sum('importe'))['total'] or Decimal('0')

