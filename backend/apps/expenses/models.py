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


class InversionInicial(models.Model):
    """Inversión inicial / gastos pre-apertura con desglose multilínea (Split Billing).

    Cabecera de una factura de inversión inicial. Las líneas van en
    LineaInversionInicial. El total calculado de las líneas debe coincidir
    exactamente con total_factura_fisico (validación de descuadre).
    """

    CATEGORIAS_INVERSION = [
        ('HERRAMIENTAS', 'Herramientas / Utillaje (Cuenta PGC 214)'),
        ('MOBILIARIO', 'Mobiliario (Cuenta PGC 216)'),
        ('INFORMATICA', 'Informática (Cuenta PGC 217)'),
        ('ALQUILER', 'Alquiler del local (Cuenta PGC 621)'),
        ('NOTARIA', 'Notaría / Registro (Cuenta PGC 622)'),
        ('TASAS', 'Tasas y permisologías (Cuenta PGC 631)'),
        ('OTROS', 'Otros gastos de apertura'),
    ]

    MAPPINGS_CATEGORIA_CUENTA = {
        'HERRAMIENTAS': '214',
        'MOBILIARIO': '216',
        'INFORMATICA': '217',
        'ALQUILER': '621',
        'NOTARIA': '622',
        'TASAS': '631',
        'OTROS': '620',
    }

    CUENTAS_INMOVILIZADO = {'214', '216', '217'}
    LIMITE_GASTO_DIRECTO = Decimal('300.00')

    fecha_emision = models.DateField(verbose_name='fecha de emisión')
    proveedor_acreedor = models.CharField(max_length=150, verbose_name='proveedor/acreedor')
    numero_factura = models.CharField(max_length=50, verbose_name='número de factura')
    forma_pago = models.ForeignKey(
        'accounting.CuentaContable',
        on_delete=models.PROTECT,
        related_name='inversiones_forma_pago',
        verbose_name='forma de pago (banco)',
        limit_choices_to={'codigo__in': ['570', '572']},
    )
    total_factura_fisico = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='total factura físico (€)'
    )
    documento_pdf = models.FileField(
        upload_to='facturas_gastos/', null=True, blank=True, verbose_name='factura PDF'
    )
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='inversiones_iniciales',
        verbose_name='creado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'inversión inicial'
        verbose_name_plural = 'inversiones iniciales'
        ordering = ['-fecha_emision', '-created_at']

    def __str__(self):
        return f"Inversión {self.numero_factura} - {self.proveedor_acreedor}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.documento_pdf and self.documento_pdf.name:
            self._renombrar_documento()

    def _renombrar_documento(self):
        from django.core.files.base import ContentFile
        original = self.documento_pdf
        ext = original.name.split('.')[-1].lower() if '.' in original.name else 'pdf'
        nuevo_nombre = f"INV_INICIAL_{self.pk}_{self.numero_factura}.{ext}"
        if original.name != nuevo_nombre:
            data = original.read()
            original.save(nuevo_nombre, ContentFile(data), save=True)

    @property
    def total_base_calculado(self):
        return sum((l.base_imponible for l in self.lineas.all()), Decimal('0'))

    @property
    def total_iva_calculado(self):
        return sum((l.cuota_iva for l in self.lineas.all()), Decimal('0'))

    @property
    def total_calculado(self):
        return self.total_base_calculado + self.total_iva_calculado

    @property
    def esta_cuadrado(self):
        return self.total_calculado.quantize(Decimal('0.01')) == self.total_factura_fisico.quantize(Decimal('0.01'))

    def crear_asiento_contable(self):
        """Genera el asiento compuesto automático a partir de las líneas."""
        from apps.accounting.models import (
            AsientoContable, MovimientoContable, CuentaContable,
        )
        from apps.accounting.views import generar_numero_asiento

        asiento = AsientoContable.objects.create(
            numero=generar_numero_asiento(),
            fecha=self.fecha_emision,
            concepto=f"Inversión inicial {self.numero_factura}: {self.proveedor_acreedor}",
            estado='BORRADOR',
            tipo_documento='InversionInicial',
            documento_id=self.pk,
            created_by=self.created_by,
        )

        for linea in self.lineas.all():
            cuenta_codigo = linea.cuenta_contable_destino()
            cuenta = CuentaContable.objects.get(codigo=cuenta_codigo)
            MovimientoContable.objects.create(
                asiento=asiento,
                cuenta=cuenta,
                debe=linea.base_imponible,
                haber=Decimal('0'),
                descripcion=f"{linea.get_categoria_display()}: {linea.concepto}",
            )
            if linea.cuota_iva > 0:
                cuenta_iva = CuentaContable.objects.get(codigo='472')
                MovimientoContable.objects.create(
                    asiento=asiento,
                    cuenta=cuenta_iva,
                    debe=linea.cuota_iva,
                    haber=Decimal('0'),
                    descripcion=f"IVA soportado {linea.tipo_iva}%",
                )

        MovimientoContable.objects.create(
            asiento=asiento,
            cuenta=self.forma_pago,
            debe=Decimal('0'),
            haber=self.total_calculado,
            descripcion=f"Pago (banco): {self.proveedor_acreedor}",
        )

        return asiento


class LineaInversionInicial(models.Model):
    """Línea de desglose de una InversionInicial (Split Billing)."""

    inversion = models.ForeignKey(
        InversionInicial,
        on_delete=models.CASCADE,
        related_name='lineas',
        verbose_name='inversión',
    )
    categoria = models.CharField(
        max_length=20, choices=InversionInicial.CATEGORIAS_INVERSION, verbose_name='categoría'
    )
    concepto = models.CharField(max_length=255, verbose_name='concepto/descripción')
    base_imponible = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='base imponible (€)'
    )
    tipo_iva = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('21.00'), verbose_name='tipo de IVA (%)'
    )
    cuota_iva = models.DecimalField(
        max_digits=12, decimal_places=2, editable=False, default=Decimal('0'), verbose_name='cuota IVA'
    )
    total_linea = models.DecimalField(
        max_digits=12, decimal_places=2, editable=False, default=Decimal('0'), verbose_name='total línea'
    )

    class Meta:
        verbose_name = 'línea de inversión'
        verbose_name_plural = 'líneas de inversión'
        ordering = ['id']

    def __str__(self):
        return f"{self.get_categoria_display()} - {self.concepto}"

    def save(self, *args, **kwargs):
        self.cuota_iva = (self.base_imponible * (self.tipo_iva / Decimal('100'))).quantize(Decimal('0.01'))
        self.total_linea = (self.base_imponible + self.cuota_iva).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)
        self._registrar_activo_si_procede()

    def cuenta_contable_destino(self):
        """Cuenta destino: 602 si Herramientas y base <= 300€, sino la del PGC."""
        codigo = InversionInicial.MAPPINGS_CATEGORIA_CUENTA.get(self.categoria, '620')
        if self.categoria == 'HERRAMIENTAS' and self.base_imponible <= InversionInicial.LIMITE_GASTO_DIRECTO:
            return '602'
        return codigo

    def _registrar_activo_si_procede(self):
        from django.utils.dateparse import parse_date
        cuenta = self.cuenta_contable_destino()
        if cuenta in InversionInicial.CUENTAS_INMOVILIZADO and \
                self.base_imponible > InversionInicial.LIMITE_GASTO_DIRECTO:
            fecha = self.inversion.fecha_emision
            if isinstance(fecha, str):
                fecha = parse_date(fecha)
            ActivoFijo.objects.get_or_create(
                linea=self,
                defaults={
                    'cuenta': cuenta,
                    'descripcion': self.concepto,
                    'valor_adquisicion': self.base_imponible,
                    'fecha_adquisicion': fecha,
                },
            )


class ActivoFijo(models.Model):
    """Registro de inmovilizado y tabla de amortización lineal anual (REQ-04)."""

    VIDAS_UTILES = {
        '214': 5,
        '216': 10,
        '217': 5,
    }

    linea = models.OneToOneField(
        LineaInversionInicial,
        on_delete=models.CASCADE,
        related_name='activo_fijo',
        verbose_name='línea de inversión',
    )
    cuenta = models.CharField(max_length=10, verbose_name='cuenta PGC')
    descripcion = models.CharField(max_length=255, verbose_name='descripción')
    valor_adquisicion = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='valor de adquisición (€)'
    )
    fecha_adquisicion = models.DateField(verbose_name='fecha de adquisición')
    vida_util_anos = models.IntegerField(default=10, verbose_name='vida útil (años)')
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'activo fijo'
        verbose_name_plural = 'activos fijos'
        ordering = ['-fecha_adquisicion']

    def __str__(self):
        return f"Activo {self.cuenta} - {self.descripcion}"

    def save(self, *args, **kwargs):
        if not self.vida_util_anos or self.vida_util_anos <= 0:
            self.vida_util_anos = self.VIDAS_UTILES.get(self.cuenta, 10)
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.generar_amortizacion()

    @property
    def cuota_anual(self):
        if self.vida_util_anos > 0:
            return (self.valor_adquisicion / Decimal(self.vida_util_anos)).quantize(Decimal('0.01'))
        return self.valor_adquisicion

    def generar_amortizacion(self):
        año_inicio = self.fecha_adquisicion.year
        for i in range(self.vida_util_anos):
            AmortizacionAnual.objects.create(
                activo=self,
                año=año_inicio + i,
                cuota=self.cuota_anual,
            )


class AmortizacionAnual(models.Model):
    """Cuota de amortización lineal de un activo para un año concreto."""

    activo = models.ForeignKey(
        ActivoFijo,
        on_delete=models.CASCADE,
        related_name='amortizaciones',
        verbose_name='activo',
    )
    año = models.IntegerField(verbose_name='año')
    cuota = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='cuota anual (€)')

    class Meta:
        verbose_name = 'amortización anual'
        verbose_name_plural = 'amortizaciones anuales'
        ordering = ['año']
        unique_together = ['activo', 'año']

    def __str__(self):
        return f"{self.activo} - {self.año}: {self.cuota} €"
