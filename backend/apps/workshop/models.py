from django.db import models
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP


class OrdenTrabajo(models.Model):
    """Orden de trabajo para reparación de vehículos."""
    
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROGRESO', 'En Progreso'),
        ('COMPLETADA', 'Completada'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    vehiculo = models.ForeignKey(
        'vehicles.Vehiculo', 
        on_delete=models.PROTECT,
        related_name='ordenes_trabajo',
        verbose_name='vehículo'
    )
    operario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT,
        related_name='ordenes_trabajo',
        verbose_name='operario'
    )
    titulo = models.CharField(max_length=200, verbose_name='título')
    descripcion = models.TextField(verbose_name='descripción')
    estado = models.CharField(
        max_length=20, 
        choices=ESTADOS, 
        default='PENDIENTE',
        verbose_name='estado'
    )
    
    # Tiempo
    horas_estimadas = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        verbose_name='horas estimadas'
    )
    horas_reales = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        verbose_name='horas reales'
    )
    
    # Fechas
    fecha_inicio = models.DateField(
        null=True, 
        blank=True,
        verbose_name='fecha de inicio'
    )
    fecha_fin = models.DateField(
        null=True, 
        blank=True,
        verbose_name='fecha de fin'
    )
    
    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT,
        related_name='ots_creadas',
        verbose_name='creado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'orden de trabajo'
        verbose_name_plural = 'órdenes de trabajo'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OT-{self.pk}: {self.titulo} ({self.vehiculo})"
    
    @property
    def coste_mano_obra(self):
        """Calcula el coste de mano de obra."""
        if self.operario and self.operario.salario_base_mensual:
            return (self.horas_reales * self.operario.coste_hora).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        return Decimal('0')
    
    @property
    def coste_materiales(self):
        """Calcula el coste total de materiales."""
        total = sum(mo.subtotal for mo in self.materiales_usados.all())
        return Decimal(total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @property
    def coste_total(self):
        """Coste total de la OT."""
        return (self.coste_mano_obra + self.coste_materiales).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    def crear_asiento_contable(self):
        """Capitaliza el coste de reparación en inventario al completar la OT.

        DEBE  310 Mercaderías  = coste_total (mano de obra + materiales)
        HABER 300 Compras      = coste_materiales (consumo de inventario)
        HABER 611 Variación de existencias = coste_mano_obra
        """
        from django.db import transaction
        from apps.accounting.models import (
            AsientoContable, MovimientoContable, CuentaContable,
        )
        from apps.accounting.views import generar_numero_asiento

        if self.coste_total <= 0:
            return None
        if AsientoContable.objects.filter(
            tipo_documento='OrdenTrabajo', documento_id=self.pk
        ).exists():
            return None

        with transaction.atomic():
            cuenta_mercancias = CuentaContable.objects.get(codigo='310')
            cuenta_compras = CuentaContable.objects.get(codigo='300')
            cuenta_variacion = CuentaContable.objects.get(codigo='611')

            asiento = AsientoContable.objects.create(
                numero=generar_numero_asiento(),
                fecha=self.fecha_fin or self.updated_at.date(),
                concepto=f"Capitalización reparación OT-{self.pk}: {self.titulo}",
                estado='BORRADOR',
                tipo_documento='OrdenTrabajo',
                documento_id=self.pk,
                created_by=self.created_by,
            )

            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_mercancias,
                debe=self.coste_total, haber=Decimal('0'),
                descripcion=f"Coste reparación {self.vehiculo}",
            )

            if self.coste_materiales > 0:
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_compras,
                    debe=Decimal('0'), haber=self.coste_materiales,
                    descripcion=f"Materiales consumidos OT-{self.pk}",
                )

            if self.coste_mano_obra > 0:
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_variacion,
                    debe=Decimal('0'), haber=self.coste_mano_obra,
                    descripcion=f"Mano de obra OT-{self.pk}",
                )

            if asiento.esta_cuadrado:
                asiento.estado = 'POSTEADO'
                asiento.save(update_fields=['estado'])

            return asiento


class Material(models.Model):
    """Material/insumo del taller."""
    
    nombre = models.CharField(max_length=100, verbose_name='nombre')
    descripcion = models.TextField(blank=True, verbose_name='descripción')
    unidad = models.CharField(max_length=20, verbose_name='unidad de medida')
    
    stock_actual = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name='stock actual'
    )
    stock_minimo = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name='stock mínimo de seguridad'
    )
    
    precio_unitario = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=0,
        verbose_name='precio unitario'
    )
    
    alerta_stock = models.BooleanField(
        default=False,
        verbose_name='alerta de stock bajo'
    )
    
    class Meta:
        verbose_name = 'material'
        verbose_name_plural = 'materiales'
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.stock_actual} {self.unidad})"
    
    def save(self, *args, **kwargs):
        # Actualizar alerta de stock
        self.alerta_stock = self.stock_actual <= self.stock_minimo
        super().save(*args, **kwargs)
    
    def decrementar_stock(self, cantidad):
        """Decrementa el stock y actualiza la alerta."""
        self.stock_actual -= cantidad
        self.alerta_stock = self.stock_actual <= self.stock_minimo
        self.save(update_fields=['stock_actual', 'alerta_stock'])


class MaterialUsado(models.Model):
    """Material utilizado en una orden de trabajo."""
    
    orden_trabajo = models.ForeignKey(
        OrdenTrabajo, 
        on_delete=models.CASCADE,
        related_name='materiales_usados',
        verbose_name='orden de trabajo'
    )
    material = models.ForeignKey(
        Material, 
        on_delete=models.PROTECT,
        related_name='usos',
        verbose_name='material'
    )
    cantidad = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        verbose_name='cantidad'
    )
    
    class Meta:
        verbose_name = 'material usado'
        verbose_name_plural = 'materiales usados'
        unique_together = ['orden_trabajo', 'material']
    
    def __str__(self):
        return f"{self.material.nombre} x{self.cantidad}"
    
    @property
    def subtotal(self):
        """Subtotal del material usado."""
        return self.cantidad * self.material.precio_unitario
    
    def save(self, *args, **kwargs):
        # Decrementar stock del material
        if not self.pk:  # Solo al crear, no al editar
            self.material.decrementar_stock(self.cantidad)
        super().save(*args, **kwargs)


class CompraMaterial(models.Model):
    """Compra de material de inventario de taller con factura y asiento contable."""

    TIPOS_INVENTARIO = [
        ('300', 'Compras (Grupo 3)'),
        ('310', 'Mercaderías (A)'),
        ('320', 'Materias primas (A)'),
        ('330', 'Otros aprovisionamientos (A)'),
    ]

    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='compras',
        verbose_name='material',
    )
    cantidad = models.DecimalField(
        max_digits=8, decimal_places=2, verbose_name='cantidad'
    )
    precio_unitario = models.DecimalField(
        max_digits=8, decimal_places=2, verbose_name='precio unitario'
    )
    fecha_compra = models.DateField(verbose_name='fecha de compra')
    proveedor = models.CharField(max_length=150, verbose_name='proveedor')
    cif_nif = models.CharField(max_length=15, verbose_name='CIF/NIF')
    numero_factura = models.CharField(
        max_length=50, blank=True, verbose_name='número de factura',
        help_text='Permite agrupar varias compras (materiales) de la misma factura de proveedor.',
    )
    tipo_inventario = models.CharField(
        max_length=3, choices=TIPOS_INVENTARIO, default='300',
        verbose_name='cuenta de inventario',
    )
    base_imponible = models.DecimalField(
        max_digits=12, decimal_places=2, editable=False, default=Decimal('0'),
        verbose_name='base imponible',
    )
    tipo_iva = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('21.00'),
        verbose_name='tipo de IVA (%)',
    )
    cuota_iva = models.DecimalField(
        max_digits=12, decimal_places=2, editable=False, default=Decimal('0'),
        verbose_name='cuota IVA',
    )
    documento_pdf = models.FileField(
        upload_to='facturas_gastos/', null=True, blank=True,
        verbose_name='factura PDF',
    )
    asiento_contable = models.OneToOneField(
        'accounting.AsientoContable',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='compra_material',
        verbose_name='asiento contable',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='compras_material_creadas',
        verbose_name='creado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'compra de material'
        verbose_name_plural = 'compras de material'
        ordering = ['-fecha_compra', '-created_at']

    def __str__(self):
        return f"Compra {self.material} x{self.cantidad} - {self.proveedor}"

    def save(self, *args, **kwargs):
        from decimal import Decimal
        self.base_imponible = (self.cantidad * self.precio_unitario).quantize(
            Decimal('0.01')
        )
        self.cuota_iva = (self.base_imponible * (self.tipo_iva / Decimal('100'))).quantize(
            Decimal('0.01')
        )
        # Entrada a inventario: incrementar stock solo al crear
        if not self.pk:
            from django.db import transaction
            with transaction.atomic():
                super().save(*args, **kwargs)
                material = Material.objects.select_for_update().get(pk=self.material.pk)
                material.stock_actual += self.cantidad
                material.alerta_stock = (
                    material.stock_actual <= material.stock_minimo
                )
                material.save(
                    update_fields=['stock_actual', 'alerta_stock']
                )
        else:
            super().save(*args, **kwargs)

    def crear_asiento_contable(self):
        """Genera el asiento de entrada a inventario (Grupo 3) + IVA + Proveedor."""
        from django.db import transaction
        from apps.accounting.models import (
            AsientoContable, MovimientoContable, CuentaContable,
        )
        from apps.accounting.views import generar_numero_asiento

        with transaction.atomic():
            codigos_requeridos = [self.tipo_inventario, '472', '410']
            for codigo in codigos_requeridos:
                if not CuentaContable.objects.filter(codigo=codigo).exists():
                    raise ValueError(
                        f'Falta la cuenta contable {codigo} en el plan contable. '
                        f'Inicialice el plan en Contabilidad > Cuentas > Inicializar.'
                    )

            cuenta_inventario = CuentaContable.objects.get(codigo=self.tipo_inventario)
            cuenta_iva = CuentaContable.objects.get(codigo='472')
            cuenta_proveedor = CuentaContable.objects.get(codigo='410')

            numero = generar_numero_asiento()

            asiento = AsientoContable.objects.create(
                numero=numero,
                fecha=self.fecha_compra,
                concepto=f"Compra inventario: {self.material.nombre} - {self.proveedor}",
                estado='BORRADOR',
                tipo_documento='CompraMaterial',
                documento_id=self.pk,
                created_by=self.created_by,
            )

            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_inventario,
                debe=self.base_imponible, haber=Decimal('0'),
                descripcion=f"Entrada inventario {self.material.nombre}",
            )
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_iva,
                debe=self.cuota_iva, haber=Decimal('0'),
                descripcion=f"IVA soportado {self.tipo_iva}%",
            )
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_proveedor,
                debe=Decimal('0'), haber=self.base_imponible + self.cuota_iva,
                descripcion=f"Proveedor: {self.proveedor}",
            )

            self.asiento_contable = asiento
            self.save(update_fields=['asiento_contable'])

            if asiento.esta_cuadrado:
                asiento.estado = 'POSTEADO'
                asiento.save(update_fields=['estado'])

            return asiento
