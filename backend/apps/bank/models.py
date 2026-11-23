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

    def saldo_a_fecha(self, fecha):
        """Saldo real de la cuenta en una fecha concreta.

        Cuenta **todos** los movimientos (conciliados o no) con fecha menor o
        igual a la indicada. Es la referencia para autorizar un pago: no se
        puede pagar con dinero que aún no había entrado.
        """
        if fecha is None:
            from django.utils import timezone
            fecha = timezone.localdate()

        movimientos = self.movimientos.filter(fecha__lte=fecha)
        ingresos = movimientos.filter(tipo='INGRESO').aggregate(
            total=models.Sum('importe')
        )['total'] or Decimal('0')
        egresos = movimientos.filter(tipo='EGRESO').aggregate(
            total=models.Sum('importe')
        )['total'] or Decimal('0')
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

    TIPOS_CLIENTE = [
        ('PARTICULAR', 'Particular (B2C)'),
        ('EMPRESA', 'Empresa/Autónomo (B2B)'),
    ]

    METODOS_PAGO = [
        ('TRANSFERENCIA', 'Transferencia bancaria'),
        ('EFECTIVO', 'Efectivo'),
        ('TARJETA', 'Tarjeta'),
    ]

    vehiculo = models.ForeignKey(
        'vehicles.Vehiculo',
        on_delete=models.PROTECT,
        related_name='reservas',
        verbose_name='vehículo',
    )
    tipo_cliente = models.CharField(
        max_length=15, choices=TIPOS_CLIENTE, default='PARTICULAR',
        verbose_name='tipo de cliente',
    )
    cliente_nombre = models.CharField(
        max_length=200, verbose_name='nombre completo / razón social'
    )
    cliente_dni = models.CharField(max_length=9, verbose_name='DNI/NIE/CIF')
    cliente_direccion = models.CharField(
        max_length=200, blank=True, verbose_name='dirección fiscal'
    )
    cliente_poblacion = models.CharField(
        max_length=100, blank=True, verbose_name='población'
    )
    cliente_provincia = models.CharField(
        max_length=100, blank=True, verbose_name='provincia'
    )
    cliente_cp = models.CharField(
        max_length=5, blank=True, verbose_name='código postal'
    )
    cliente_telefono = models.CharField(
        max_length=15, blank=True, verbose_name='teléfono'
    )
    cliente_email = models.EmailField(
        blank=True, verbose_name='email'
    )
    metodo_pago = models.CharField(
        max_length=20, choices=METODOS_PAGO, default='TRANSFERENCIA',
        verbose_name='método de pago',
    )
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
    def es_entrega_a_cuenta_rebu(self):
        """La señal es una entrega a cuenta REBU: no lleva IVA propio.

        El importe completo se registra en la cuenta 438 (anticipos de
        clientes) y se cancela en el asiento de la venta final, donde el IVA
        se liquida sobre el margen.
        """
        return True


class FacturaReserva(models.Model):
    """Factura de entrega a cuenta (señal) de una reserva.

    Numeración correlativa por año (`A-2026-0001`). Al ser vehículos en REBU,
    el documento refleja la entrega a cuenta **sin desglosar IVA**: el IVA se
    liquida sobre el margen en la factura final de la venta.
    """

    reserva = models.OneToOneField(
        Reserva, on_delete=models.CASCADE,
        related_name='factura', verbose_name='reserva',
    )
    codigo = models.CharField(max_length=20, unique=True, verbose_name='código')
    fecha_emision = models.DateTimeField(auto_now_add=True, verbose_name='fecha de emisión')
    fecha_operacion = models.DateField(verbose_name='fecha de la operación')
    importe = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='importe recibido'
    )
    metodo_pago = models.CharField(
        max_length=20, choices=Reserva.METODOS_PAGO, default='TRANSFERENCIA',
        verbose_name='método de pago',
    )
    concepto = models.CharField(max_length=255, verbose_name='concepto')
    pdf = models.FileField(
        upload_to='reservas/facturas/', blank=True, verbose_name='PDF'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='facturas_reserva_creadas', verbose_name='creado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'factura de reserva'
        verbose_name_plural = 'facturas de reserva'
        ordering = ['-fecha_emision']

    def __str__(self):
        return f'{self.codigo} - {self.reserva.cliente_nombre}'

    @classmethod
    def generar_siguiente_codigo(cls):
        """Código correlativo por año: A-2026-0001, A-2026-0002..."""
        from django.utils import timezone

        anio = timezone.localdate().year
        prefijo = f'A-{anio}-'
        ultima = (
            cls.objects.filter(codigo__startswith=prefijo)
            .order_by('-codigo')
            .first()
        )
        numero = 1
        if ultima:
            try:
                numero = int(ultima.codigo.split('-')[-1]) + 1
            except (ValueError, IndexError):
                numero = 1

        while True:
            codigo = f'{prefijo}{numero:04d}'
            if not cls.objects.filter(codigo=codigo).exists():
                return codigo
            numero += 1
