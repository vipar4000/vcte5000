from django.db import models
from dateutil.relativedelta import relativedelta


class GarantiaVehiculo(models.Model):
    """Garantía de vehículo vendido - Real Decreto-ley 7/2021."""
    
    TIPOS_CLIENTE = [
        ('PARTICULAR', 'Particular (B2C) - 12 meses'),
        ('EMPRESA', 'Empresa/Autónomo (B2B) - 6 meses'),
    ]
    
    venta = models.OneToOneField(
        'sales.VentaVehiculo', 
        on_delete=models.CASCADE,
        related_name='garantia',
        verbose_name='venta'
    )
    tipo_cliente = models.CharField(
        max_length=15, 
        choices=TIPOS_CLIENTE,
        verbose_name='tipo de cliente'
    )
    fecha_inicio = models.DateField(verbose_name='fecha de inicio')
    fecha_fin = models.DateField(verbose_name='fecha de fin')
    # Al anular la venta, su garantía deja de estar vigente (aunque la fecha
    # de fin sea futura). No se borra: queda como histórico ANULADA.
    anulada = models.BooleanField(default=False, verbose_name='anulada')
    fecha_anulacion = models.DateField(
        null=True, blank=True, verbose_name='fecha de anulación'
    )
    motivo_anulacion = models.CharField(
        max_length=200, blank=True, verbose_name='motivo de la anulación'
    )
    
    class Meta:
        verbose_name = 'garantía de vehículo'
        verbose_name_plural = 'garantías de vehículos'
    
    def __str__(self):
        return f"Garantía {self.venta.vehiculo} - {self.get_tipo_cliente_display()}"
    
    def save(self, *args, **kwargs):
        if not self.fecha_fin:
            meses = 12 if self.tipo_cliente == 'PARTICULAR' else 6
            self.fecha_fin = self.fecha_inicio + relativedelta(months=meses)
        super().save(*args, **kwargs)
    
    @property
    def esta_vigente(self):
        """Verifica si la garantía está vigente (ni anulada ni caducada)."""
        from django.utils import timezone
        if self.anulada:
            return False
        return timezone.now().date() <= self.fecha_fin

    @property
    def estado_mostrado(self):
        """Texto corto del estado para la ficha y el listado."""
        if self.anulada:
            return 'ANULADA'
        from django.utils import timezone
        if timezone.now().date() <= self.fecha_fin:
            return 'VIGENTE'
        return 'CADUCADA'

    def anular(self, motivo='', fecha=None):
        """Marca la garantía como anulada (por anulación de la venta)."""
        from django.utils import timezone

        if self.anulada:
            return
        self.anulada = True
        self.fecha_anulacion = fecha or timezone.localdate()
        self.motivo_anulacion = (motivo or '')[:200]
        self.save(update_fields=['anulada', 'fecha_anulacion', 'motivo_anulacion'])
    
    @property
    def meses_restantes(self):
        """Meses restantes de garantía."""
        from django.utils import timezone
        hoy = timezone.now().date()
        if self.anulada or hoy > self.fecha_fin:
            return 0
        delta = relativedelta(self.fecha_fin, hoy)
        return delta.months + (delta.years * 12)


class HistorialReparacionGarantia(models.Model):
    """Historial de reparaciones en garantía."""
    
    ESTADOS = [
        ('ESTUDIO', 'En Evaluación'),
        ('PROCESO', 'En Reparación'),
        ('CERRADO', 'Entregado'),
    ]
    
    garantia = models.ForeignKey(
        GarantiaVehiculo, 
        on_delete=models.CASCADE,
        related_name='reparaciones',
        verbose_name='garantía'
    )
    fecha_ingreso_taller = models.DateField(verbose_name='fecha de ingreso')
    descripcion_averia = models.TextField(verbose_name='descripción de la avería')
    estado = models.CharField(
        max_length=15, 
        choices=ESTADOS, 
        default='ESTUDIO',
        verbose_name='estado'
    )
    
    # Costes internos (NO incrementan el valor del vehículo original)
    costo_repuestos_interno = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name='coste repuestos (interno)'
    )
    costo_mano_obra_interno = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name='coste mano de obra (interno)'
    )
    total_costo_reparacion = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name='coste total reparación'
    )
    
    fecha_resolucion = models.DateField(
        null=True, 
        blank=True,
        verbose_name='fecha de resolución'
    )
    
    class Meta:
        verbose_name = 'reparación en garantía'
        verbose_name_plural = 'reparaciones en garantía'
        ordering = ['-fecha_ingreso_taller']
    
    def __str__(self):
        return f"Reparación {self.garantia} - {self.get_estado_display()}"
    
    def save(self, *args, **kwargs):
        # Calcular total
        self.total_costo_reparacion = (
            self.costo_repuestos_interno + 
            self.costo_mano_obra_interno
        )
        super().save(*args, **kwargs)
