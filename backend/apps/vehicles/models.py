from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class Vehiculo(models.Model):
    """Modelo de vehículo para R Car Rogil."""
    
    ESTADOS = [
        ('ADQUIRIDO', 'Adquirido'),
        ('TALLER', 'En Taller'),
        ('ACONDICIONADO', 'Acondicionado'),
        ('EN_VENTA', 'En Venta'),
        ('VENDIDO', 'Vendido'),
    ]
    
    TIPOS_DANO = [
        ('ACCIDENTAL', 'Accidental'),
        ('INUNDACION', 'Daños por Inundación'),
        ('GRANIZO', 'Daños por Granizo'),
        ('INCENDIO', 'Daños por Incendio'),
        ('MECANICO', 'Daño Mecánico'),
        ('OTRO', 'Otro'),
    ]
    
    COMBUSTIBLES = [
        ('GASOLINA', 'Gasolina'),
        ('DIESEL', 'Diésel'),
        ('HIBRIDO', 'Híbrido'),
        ('ELECTRICO', 'Eléctrico'),
        ('GAS_LPG', 'Gas (LPG)'),
        ('GAS_CNG', 'Gas (CNG)'),
    ]
    
    ETIQUETAS_AMBIENTALES = [
        ('0', 'Cero emisiones (0)'),
        ('ECO', 'ECO'),
        ('B', 'B'),
        ('C', 'C'),
    ]
    
    PLATAFORMAS_SUBASTA = [
        ('', '---------'),
        ('BCA', 'BCA (British Car Auctions)'),
        ('COPART', 'Copart'),
        ('ADESA', 'ADESA'),
        ('KBC', 'KBC'),
        ('AUTOVIAS', 'Autovias'),
        ('SUBASTAS_RED', 'Subastas Red'),
        ('MANNHEIM', 'Mannheim'),
        ('EURODAM', 'Eurodam'),
        ('OTRO', 'Otro'),
    ]
    
    # Datos técnicos
    matricula = models.CharField(max_length=7, unique=True, verbose_name='matrícula')
    bastidor = models.CharField(max_length=17, unique=True, verbose_name='bastidor/VIN')
    marca = models.CharField(max_length=50, verbose_name='marca')
    modelo = models.CharField(max_length=100, verbose_name='modelo')
    anio = models.IntegerField(verbose_name='año')
    combustible = models.CharField(
        max_length=20, 
        choices=COMBUSTIBLES, 
        verbose_name='combustible'
    )
    kilometraje = models.IntegerField(verbose_name='kilometraje')
    tipo_dano = models.CharField(
        max_length=20, 
        choices=TIPOS_DANO, 
        verbose_name='tipo de daño'
    )
    estado = models.CharField(
        max_length=20, 
        choices=ESTADOS, 
        default='ADQUIRIDO',
        verbose_name='estado'
    )
    etiqueta_ambiental = models.CharField(
        max_length=5, 
        choices=ETIQUETAS_AMBIENTALES, 
        default='C',
        verbose_name='etiqueta ambiental'
    )
    
    # Datos de adquisición
    fecha_adquisicion = models.DateField(verbose_name='fecha de adquisición')
    plataforma_subasta = models.CharField(
        max_length=100, 
        blank=True,
        choices=PLATAFORMAS_SUBASTA,
        verbose_name='plataforma de subasta'
    )
    
    # Costes de adquisición
    precio_subasta = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name='precio de adjudicación'
    )
    tasas_sala = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name='tasas de la sala'
    )
    logistica_grua = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name='logística/grúa'
    )
    coste_inicial = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name='coste inicial total'
    )
    
    # Precio de venta
    precio_venta = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name='precio de venta'
    )
    
    # Descripción del daño
    descripcion_dano = models.TextField(
        blank=True,
        verbose_name='descripción del daño'
    )
    
    # Imagen principal
    imagen_principal = models.ImageField(
        upload_to='vehiculos/', 
        blank=True,
        verbose_name='imagen principal'
    )
    
    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT,
        related_name='vehiculos_creados',
        verbose_name='creado por'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='fecha de actualización')
    
    class Meta:
        verbose_name = 'vehículo'
        verbose_name_plural = 'vehículos'
        ordering = ['-fecha_adquisicion', '-created_at']
    
    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.matricula})"
    
    def save(self, *args, **kwargs):
        # Calcular coste inicial automáticamente
        self.coste_inicial = (
            self.precio_subasta + 
            self.tasas_sala + 
            self.logistica_grua
        )
        super().save(*args, **kwargs)
    
    @property
    def coste_reparacion(self):
        """Calcula el coste total de reparación sumando OTs."""
        from apps.workshop.models import OrdenTrabajo
        ots = OrdenTrabajo.objects.filter(vehiculo=self)
        total_mano_obra = sum(ot.coste_mano_obra for ot in ots)
        total_materiales = sum(ot.coste_materiales for ot in ots)
        return total_mano_obra + total_materiales
    
    @property
    def coste_total(self):
        """Coste total del vehículo (inicial + reparación + gastos fijos)."""
        return self.coste_inicial + self.coste_reparacion
    
    @property
    def dias_en_inventario(self):
        """Días desde la adquisición."""
        return (timezone.now().date() - self.fecha_adquisicion).days
    
    @property
    def disponible_para_venta(self):
        """Verifica si el vehículo está listo para la venta."""
        return self.estado == 'ACONDICIONADO'


class ImagenVehiculo(models.Model):
    """Imágenes adicionales del vehículo."""
    
    vehiculo = models.ForeignKey(
        Vehiculo, 
        on_delete=models.CASCADE,
        related_name='imagenes',
        verbose_name='vehículo'
    )
    imagen = models.ImageField(
        upload_to='vehiculos/', 
        verbose_name='imagen'
    )
    es_principal = models.BooleanField(
        default=False,
        verbose_name='es imagen principal'
    )
    orden = models.IntegerField(default=0, verbose_name='orden')
    
    class Meta:
        verbose_name = 'imagen de vehículo'
        verbose_name_plural = 'imágenes de vehículos'
        ordering = ['orden']
    
    def __str__(self):
        return f"Imagen de {self.vehiculo}"
