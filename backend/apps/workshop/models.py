from django.db import models
from django.conf import settings
from decimal import Decimal


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
            return self.horas_reales * self.operario.coste_hora
        return Decimal('0')
    
    @property
    def coste_materiales(self):
        """Calcula el coste total de materiales."""
        return sum(mo.subtotal for mo in self.materiales_usados.all())
    
    @property
    def coste_total(self):
        """Coste total de la OT."""
        return self.coste_mano_obra + self.coste_materiales


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
