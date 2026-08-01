from django.db import models
from django.conf import settings
from decimal import Decimal

from apps.core.formatting import format_euros


class BancoCuenta(models.Model):
    """Cuenta bancaria corporativa de la S.L."""

    nombre = models.CharField(
        max_length=100, verbose_name='nombre',
        help_text='Ej: BBVA Empresa'
    )
    iban = models.CharField(max_length=34, unique=True, verbose_name='IBAN')
    swift = models.CharField(max_length=11, blank=True, verbose_name='SWIFT/BIC')
    cuenta_contable = models.ForeignKey(
        'accounting.CuentaContable',
        on_delete=models.PROTECT,
        related_name='cuentas_bancarias',
        verbose_name='cuenta contable (572)',
        limit_choices_to={'codigo__startswith': '572'},
    )
    activa = models.BooleanField(default=True, verbose_name='activa')
    soporte_deposito = models.FileField(
        upload_to='banco/soportes/',
        blank=True,
        verbose_name='soporte del deposito inicial'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'cuenta bancaria'
        verbose_name_plural = 'cuentas bancarias'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} (*{self.iban[-4:]})"

    @property
    def saldo(self):
        """Saldo calculado on-the-fly desde movimientos."""
        ingresos = self.movimientos.filter(
            tipo='INGRESO', conciliado=True
        ).aggregate(total=models.Sum('importe'))['total'] or Decimal('0')
        egresos = self.movimientos.filter(
            tipo='EGRESO', conciliado=True
        ).aggregate(total=models.Sum('importe'))['total'] or Decimal('0')
        return ingresos - egresos

    @property
    def saldo_pendiente(self):
        """Saldo incluyendo movimientos no conciliados."""
        ingresos = self.movimientos.filter(
            tipo='INGRESO'
        ).aggregate(total=models.Sum('importe'))['total'] or Decimal('0')
        egresos = self.movimientos.filter(
            tipo='EGRESO'
        ).aggregate(total=models.Sum('importe'))['total'] or Decimal('0')
        return ingresos - egresos

    @property
    def saldo_sin_conciliar(self):
        """Movimientos pendientes de conciliar (saldo_pendiente - saldo)."""
        return self.saldo_pendiente - self.saldo


class BancoMovimiento(models.Model):
    """Espejo del extracto bancario real."""

    TIPO_CHOICES = [
        ('INGRESO', 'Ingreso / Cobro'),
        ('EGRESO', 'Egreso / Pago'),
    ]

    banco_cuenta = models.ForeignKey(
        BancoCuenta,
        on_delete=models.PROTECT,
        related_name='movimientos',
        verbose_name='cuenta bancaria',
    )
    fecha = models.DateField(verbose_name='fecha')
    fecha_valor = models.DateField(
        null=True, blank=True, verbose_name='fecha de valor'
    )
    concepto = models.CharField(max_length=255, verbose_name='concepto')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name='tipo')
    importe = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='importe',
        help_text='Valor absoluto'
    )
    conciliado = models.BooleanField(default=False, verbose_name='conciliado')

    # Referencias cruzadas
    asiento_asociado = models.OneToOneField(
        'accounting.AsientoContable',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movimiento_banco',
        verbose_name='asiento contable',
    )
    vehiculo_asociado = models.ForeignKey(
        'vehicles.Vehiculo',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movimientos_banco',
        verbose_name='vehículo',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    notas = models.TextField(blank=True, verbose_name='notas')
    soporte = models.FileField(
        upload_to='banco/movimientos/',
        blank=True,
        verbose_name='soporte'
    )

    class Meta:
        verbose_name = 'movimiento bancario'
        verbose_name_plural = 'movimientos bancarios'
        ordering = ['-fecha', '-created_at']
        indexes = [
            models.Index(fields=['fecha', 'importe', 'tipo']),
            models.Index(fields=['conciliado', 'fecha']),
            models.Index(fields=['banco_cuenta', 'fecha']),
        ]

    def __str__(self):
        signo = '+' if self.tipo == 'INGRESO' else '-'
        return f"{self.fecha} {signo} {format_euros(self.importe)} - {self.concepto[:50]}"


class Reserva(models.Model):
    """Gestión de Arras / Señales para apartar vehículos."""

    ESTADO_CHOICES = [
        ('ACTIVA', 'Activa'),
        ('CONVERTIDA', 'Convertida en Venta'),
        ('DEVUELTA', 'Devuelta al cliente'),
        ('PENALIZADA', 'Penalización (S.L. retiene)'),
    ]

    vehiculo = models.ForeignKey(
        'vehicles.Vehiculo',
        on_delete=models.PROTECT,
        related_name='reservas',
        verbose_name='vehículo',
    )
    cliente_nombre = models.CharField(max_length=150, verbose_name='nombre del cliente')
    cliente_dni = models.CharField(max_length=9, verbose_name='DNI/NIE')
    fecha_reserva = models.DateField(verbose_name='fecha de reserva')
    importe_reserva = models.DecimalField(
        max_digits=8, decimal_places=2, verbose_name='importe de la reserva'
    )
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='ACTIVA',
        verbose_name='estado'
    )
    banco_movimiento = models.OneToOneField(
        BancoMovimiento,
        on_delete=models.PROTECT,
        related_name='reserva',
        verbose_name='movimiento bancario',
    )
    venta = models.OneToOneField(
        'sales.VentaVehiculo',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reserva',
        verbose_name='venta asociada',
    )
    notas = models.TextField(blank=True, verbose_name='notas')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reservas_creadas',
        verbose_name='creado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'reserva'
        verbose_name_plural = 'reservas'
        ordering = ['-fecha_reserva']

    def __str__(self):
        return f"Reserva {self.vehiculo} - {self.cliente_nombre} ({format_euros(self.importe_reserva)})"

    @property
    def base_imponible(self):
        """Base imponible del anticipo (IVA 21%)."""
        return (self.importe_reserva / Decimal('1.21')).quantize(Decimal('0.01'))

    @property
    def cuota_iva(self):
        """IVA del anticipo."""
        return (self.base_imponible * Decimal('0.21')).quantize(Decimal('0.01'))
