from django.db import models
from django.conf import settings
from decimal import Decimal
import uuid


class CuentaContable(models.Model):
    """Cuenta contable del Plan General de Contabilidad (PGC)."""
    
    TIPOS_CUENTA = [
        ('A', 'Activo'),
        ('P', 'Pasivo'),
        ('NP', 'Neto Patrimonio'),
        ('I', 'Ingresos'),
        ('G', 'Gastos'),
    ]
    
    codigo = models.CharField(max_length=20, unique=True, verbose_name='código')
    nombre = models.CharField(max_length=200, verbose_name='nombre')
    tipo = models.CharField(max_length=2, choices=TIPOS_CUENTA, verbose_name='tipo')
    padre = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE,
        null=True, 
        blank=True,
        related_name='subcuentas',
        verbose_name='cuenta padre'
    )
    saldo = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0,
        verbose_name='saldo'
    )
    activa = models.BooleanField(default=True, verbose_name='activa')
    
    class Meta:
        verbose_name = 'cuenta contable'
        verbose_name_plural = 'cuentas contables'
        ordering = ['codigo']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class AsientoContable(models.Model):
    """Asiento contable (journal entry)."""
    
    ESTADOS = [
        ('BORRADOR', 'Borrador'),
        ('POSTEADO', 'Posteado'),
        ('ANULADO', 'Anulado'),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    numero = models.CharField(max_length=20, unique=True, verbose_name='número')
    fecha = models.DateField(verbose_name='fecha del asiento')
    concepto = models.CharField(max_length=500, verbose_name='concepto')
    estado = models.CharField(
        max_length=10, 
        choices=ESTADOS, 
        default='BORRADOR',
        verbose_name='estado'
    )
    
    # Referencia al documento origen
    tipo_documento = models.CharField(
        max_length=50, 
        blank=True,
        verbose_name='tipo de documento'
    )
    documento_id = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name='ID del documento'
    )
    
    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT,
        related_name='asientos_contables',
        verbose_name='creado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'asiento contable'
        verbose_name_plural = 'asientos contables'
        ordering = ['-fecha', '-numero']
    
    def __str__(self):
        return f"Asiento {self.numero} - {self.concepto}"
    
    @property
    def total_debe(self):
        """Suma total del debe."""
        return sum(monto for monto in self.movimientos.values_list('debe', flat=True))
    
    @property
    def total_haber(self):
        """Suma total del haber."""
        return sum(monto for monto in self.movimientos.values_list('haber', flat=True))
    
    @property
    def esta_cuadrado(self):
        """Verifica si el asiento está cuadrado (debe = haber)."""
        return self.total_debe == self.total_haber


class MovimientoContable(models.Model):
    """Movimiento contable (débito/crédito)."""
    
    asiento = models.ForeignKey(
        AsientoContable, 
        on_delete=models.CASCADE,
        related_name='movimientos',
        verbose_name='asiento'
    )
    cuenta = models.ForeignKey(
        CuentaContable, 
        on_delete=models.PROTECT,
        related_name='movimientos',
        verbose_name='cuenta'
    )
    debe = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0,
        verbose_name='debe'
    )
    haber = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0,
        verbose_name='haber'
    )
    descripcion = models.CharField(
        max_length=500, 
        blank=True,
        verbose_name='descripción'
    )
    
    class Meta:
        verbose_name = 'movimiento contable'
        verbose_name_plural = 'movimientos contables'
    
    def __str__(self):
        return f"{self.cuenta} - Debe: {self.debe} / Haber: {self.haber}"
    
    def save(self, *args, **kwargs):
        # Validar que no sea ambas (debe y haber)
        if self.debe > 0 and self.haber > 0:
            raise ValueError("Un movimiento no puede tener debe y haber simultáneamente")
        if self.debe == 0 and self.haber == 0:
            raise ValueError("Un movimiento debe tener debe o haber")
        super().save(*args, **kwargs)


class PlanContableDefault(models.Model):
    """Plan contable por defecto del PGC español."""
    
    @staticmethod
    def crear_plan_base():
        """Crea el plan contable base del PGC."""
        cuentas = [
            # Grupo 1 - Financiación Básica
            ('100', 'Capital social', 'NP'),
            ('102', 'Reservas legales', 'NP'),
            ('110', 'Resultados no asignados', 'NP'),
            ('129', 'Resultado del ejercicio (pendiente de dotación)', 'NP'),
            
            # Grupo 2 - Inmovilizado
            ('200', 'Terrenos y bienes naturales', 'A'),
            ('210', 'Edificios', 'A'),
            ('220', 'Instalaciones técnicas', 'A'),
            ('230', 'Maquinaria', 'A'),
            ('240', 'Utillaje', 'A'),
            ('250', 'Elementos de transporte', 'A'),
            ('260', 'Mobiliario', 'A'),
            ('270', 'Equipos para procesos de información', 'A'),
            
            # Grupo 3 - Existencias
            ('300', 'Compras', 'G'),
            ('310', 'Mercaderías', 'A'),
            ('320', 'Materias primas', 'A'),
            ('330', 'Otros aprovisionamientos', 'A'),
            
            # Grupo 4 - Acreedores y deudas
            ('400', 'Proveedores', 'P'),
            ('410', 'Acreedores varios', 'P'),
            ('430', 'Clientes', 'A'),
            ('440', 'Deudores varios', 'A'),
            ('472', 'Hacienda Pública, IVA soportado', 'P'),
            ('471', 'Hacienda Pública, IVA repercutido', 'P'),
            ('4751', 'Retenciones y anticipos IRPF', 'P'),
            
            # Grupo 5 - Tesorería
            ('570', 'Caja', 'A'),
            ('572', 'Banco', 'A'),
            
            # Grupo 6 - Gastos
            ('600', 'Compras de mercaderías', 'G'),
            ('602', 'Servicios exteriores', 'G'),
            ('606', 'Repuestos', 'G'),
            ('607', 'Trabajos realizados por otras empresas', 'G'),
            ('610', 'Compras de materias primas', 'G'),
            ('620', 'Otros gastos exteriores', 'G'),
            ('621', 'Arrendamientos y cánones', 'G'),
            ('623', 'Reparaciones y conservación', 'G'),
            ('628', 'Suministros y otros gastos', 'G'),
            ('629', 'Otros servicios exteriores', 'G'),
            ('630', 'Gastos financieros', 'G'),
            ('631', 'Pérdidas por deterioro y otorg. valore', 'G'),
            ('640', 'Sueldos y salarios', 'G'),
            ('642', 'Seguridad social', 'G'),
            ('680', 'Impuesto sobre sociedades', 'G'),
            
            # Grupo 7 - Ingresos
            ('700', 'Ventas de mercaderías', 'I'),
            ('710', 'Ventas de productos', 'I'),
            ('754', 'Descuentos por pronto pago', 'I'),
            ('759', 'otros', 'I'),
        ]
        
        for codigo, nombre, tipo in cuentas:
            CuentaContable.objects.get_or_create(
                codigo=codigo,
                defaults={'nombre': nombre, 'tipo': tipo}
            )
