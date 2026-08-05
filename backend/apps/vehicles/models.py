from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


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
    
    # Datos de factura de compra
    proveedor = models.CharField(
        max_length=150, blank=True,
        verbose_name='proveedor / subasta',
        help_text='Nombre del proveedor o casa de subastas',
    )
    cif_nif = models.CharField(
        max_length=15, blank=True,
        verbose_name='CIF/NIF proveedor',
    )
    numero_factura = models.CharField(
        max_length=50, blank=True,
        verbose_name='nº factura de compra',
    )
    factura_compra_pdf = models.FileField(
        upload_to='facturas_compra/',
        blank=True,
        verbose_name='factura de compra (PDF)',
    )
    
    # IVA de compra
    tipo_iva = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='IVA soportado (€)',
        help_text='Importe del IVA facturado. 0 si no factura IVA',
    )
    coste_total_adquisicion = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='coste total de adquisición',
    )
    cuota_iva = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='cuota IVA',
    )
    
    # Pago y contabilidad
    forma_pago = models.ForeignKey(
        'accounting.CuentaContable',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='vehiculos_pago',
        verbose_name='forma de pago (cuenta bancaria 572)',
        limit_choices_to={'codigo__startswith': '572'},
    )
    asiento_contable = models.OneToOneField(
        'accounting.AsientoContable',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vehiculo_compra',
        verbose_name='asiento contable',
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
        self.coste_inicial = (
            self.precio_subasta + 
            self.tasas_sala + 
            self.logistica_grua
        )
        self.coste_total_adquisicion = self.precio_subasta + self.tasas_sala + self.logistica_grua
        self.cuota_iva = self.tipo_iva
        super().save(*args, **kwargs)
    
    def crear_asiento_contable(self):
        """Genera el asiento contable de compra del vehículo.
        
        DEBE  310 Mercaderías  = coste_inicial
        DEBE  472 IVA Soportado = cuota_iva  (si > 0)
        HABER 572 Banco         = total      (si pago inmediato)
        HABER 410 Proveedores   = total      (si compra a crédito)
        """
        from django.db import transaction
        from apps.accounting.models import (
            AsientoContable, MovimientoContable, CuentaContable,
        )
        from apps.accounting.views import generar_numero_asiento

        if self.asiento_contable:
            return self.asiento_contable

        total = self.coste_inicial + self.cuota_iva

        with transaction.atomic():
            for codigo in ['310', '472']:
                if not CuentaContable.objects.filter(codigo=codigo).exists():
                    raise ValueError(
                        f'Falta la cuenta contable {codigo}. '
                        f'Inicialice el plan en Contabilidad > Cuentas > Inicializar.'
                    )

            cuenta_mercancias = CuentaContable.objects.get(codigo='310')
            cuenta_iva = CuentaContable.objects.get(codigo='472')

            numero = generar_numero_asiento()

            asiento = AsientoContable.objects.create(
                numero=numero,
                fecha=self.fecha_adquisicion,
                concepto=f"Compra vehículo {self.marca} {self.modelo} ({self.matricula})",
                estado='BORRADOR',
                tipo_documento='CompraVehiculo',
                documento_id=self.pk,
                created_by=self.created_by,
            )

            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_mercancias,
                debe=self.coste_inicial, haber=Decimal('0'),
                descripcion=f"Entrada inventario {self.marca} {self.modelo}",
            )

            if self.cuota_iva > 0:
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_iva,
                    debe=self.cuota_iva, haber=Decimal('0'),
                    descripcion=f"IVA soportado {self.tipo_iva}%",
                )

            if self.forma_pago:
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=self.forma_pago,
                    debe=Decimal('0'), haber=total,
                    descripcion=f"Pago banco: {self.proveedor or 'Subasta'}",
                )
            else:
                if not CuentaContable.objects.filter(codigo='410').exists():
                    raise ValueError('Falta la cuenta contable 410 (Proveedores).')
                cuenta_proveedor = CuentaContable.objects.get(codigo='410')
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_proveedor,
                    debe=Decimal('0'), haber=total,
                    descripcion=f"Proveedor: {self.proveedor or 'Subasta'}",
                )

            self.asiento_contable = asiento
            self.save(update_fields=['asiento_contable'])

            if asiento.esta_cuadrado:
                asiento.estado = 'POSTEADO'
                asiento.save(update_fields=['estado'])

        return asiento
    
    def registrar_movimiento_banco(self, asiento=None):
        """Registra el egreso bancario de la compra del vehículo."""
        from apps.bank.models import BancoCuenta
        from apps.bank.services import crear_movimiento_banco, obtener_cuenta_banco_default

        cuenta = None
        if self.forma_pago:
            cuenta = BancoCuenta.objects.filter(
                cuenta_contable=self.forma_pago
            ).first()
        if not cuenta:
            cuenta = obtener_cuenta_banco_default()
        if not cuenta:
            logger.warning('No hay cuenta bancaria para registrar movimiento de compra.')
            return None

        total = self.coste_inicial + self.cuota_iva
        return crear_movimiento_banco(
            banco_cuenta=cuenta,
            fecha=self.fecha_adquisicion,
            concepto=f"Compra vehículo {self.marca} {self.modelo} ({self.matricula})",
            tipo='EGRESO',
            importe=total,
            vehiculo=self,
            asiento=asiento or self.asiento_contable,
        )
    
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
