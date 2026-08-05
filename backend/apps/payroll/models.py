from django.db import models
from django.conf import settings
from decimal import Decimal


class NominaEstructura(models.Model):
    """Nómina de personal de estructura (limpieza, administración).
    
    Asiento contable estándar PGC español:
        DEBE  640 (salario_bruto)
        DEBE  642 (ss_patronal)
        HABER 4751 (retencion_irpf)
        HABER 476 (ss_obrera + ss_patronal)
        HABER 465 (liquido_percibir)
    """

    empleado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='nominas_estructura',
        verbose_name='empleado',
    )
    fecha_nomina = models.DateField(verbose_name='fecha de nómina')

    # Devengos
    salario_bruto = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='salario bruto (640)'
    )
    ss_patronal = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='SS patronal (642)'
    )

    # Deducciones
    retencion_irpf = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='retención IRPF (4751)'
    )
    ss_obrera = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='SS obrera (476)'
    )

    # Líquido
    liquido_percibir = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='líquido a percibir (465)'
    )

    # Contabilidad
    asiento_contable = models.OneToOneField(
        'accounting.AsientoContable',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='nomina_estructura',
        verbose_name='asiento contable',
    )

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='nominas_estructura_creadas',
        verbose_name='creado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'nómina de estructura'
        verbose_name_plural = 'nóminas de estructura'
        ordering = ['-fecha_nomina', '-created_at']

    def __str__(self):
        return f"Nómina {self.empleado} - {self.fecha_nomina.strftime('%m/%Y')}"

    def save(self, *args, **kwargs):
        self.liquido_percibir = (
            self.salario_bruto
            - self.retencion_irpf
            - self.ss_obrera
        )
        super().save(*args, **kwargs)

    @property
    def total_devengos(self):
        return self.salario_bruto + self.ss_patronal

    @property
    def total_deducciones(self):
        return self.retencion_irpf + self.ss_obrera + self.ss_patronal

    def crear_asiento_contable(self):
        """Genera el asiento contable de nómina según PGC español."""
        from django.db import transaction
        from apps.accounting.models import (
            AsientoContable, MovimientoContable, CuentaContable,
        )
        from apps.accounting.views import generar_numero_asiento

        with transaction.atomic():
            cuenta_640 = CuentaContable.objects.get(codigo='640')
            cuenta_642 = CuentaContable.objects.get(codigo='642')
            cuenta_4751 = CuentaContable.objects.get(codigo='4751')
            cuenta_476 = CuentaContable.objects.get(codigo='476')
            cuenta_465 = CuentaContable.objects.get(codigo='465')

            asiento = AsientoContable.objects.create(
                numero=generar_numero_asiento(),
                fecha=self.fecha_nomina,
                concepto=f"Nómina {self.empleado} - {self.fecha_nomina.strftime('%m/%Y')}",
                estado='BORRADOR',
                tipo_documento='NominaEstructura',
                documento_id=self.pk,
                created_by=self.created_by,
            )

            # DEBE 640 — Sueldos y salarios
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_640,
                debe=self.salario_bruto, haber=Decimal('0'),
                descripcion=f"Sueldo bruto: {self.empleado}",
            )

            # DEBE 642 — Seguridad social a cargo de la empresa
            MovimientoContable.objects.create(
                asiento=asiento, cuenta=cuenta_642,
                debe=self.ss_patronal, haber=Decimal('0'),
                descripcion=f"SS patronal: {self.empleado}",
            )

            # HABER 4751 — Retención IRPF
            if self.retencion_irpf > 0:
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_4751,
                    debe=Decimal('0'), haber=self.retencion_irpf,
                    descripcion=f"Retención IRPF: {self.empleado}",
                )

            # HABER 476 — SS a pagar (obrera + patronal)
            total_ss = self.ss_obrera + self.ss_patronal
            if total_ss > 0:
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_476,
                    debe=Decimal('0'), haber=total_ss,
                    descripcion=f"SS a pagar: {self.empleado}",
                )

            # HABER 465 — Remuneraciones pendientes (líquido)
            if self.liquido_percibir > 0:
                MovimientoContable.objects.create(
                    asiento=asiento, cuenta=cuenta_465,
                    debe=Decimal('0'), haber=self.liquido_percibir,
                    descripcion=f"Líquido a percibir: {self.empleado}",
                )

            self.asiento_contable = asiento
            self.save(update_fields=['asiento_contable'])

            if asiento.esta_cuadrado:
                asiento.estado = 'POSTEADO'
                asiento.save(update_fields=['estado'])

            return asiento
