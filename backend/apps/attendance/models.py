from django.db import models
from django.conf import settings


class Marcaje(models.Model):
    """Registro de asistencia/jornada laboral."""
    
    TIPOS_MARCAJE = [
        ('ENTRADA', 'Entrada'),
        ('SALIDA', 'Salida'),
        ('DESCANSO_INICIO', 'Inicio Descanso'),
        ('DESCANSO_FIN', 'Fin Descanso'),
    ]
    
    operario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT,
        related_name='marcajes',
        verbose_name='operario'
    )
    tipo = models.CharField(
        max_length=15, 
        choices=TIPOS_MARCAJE,
        verbose_name='tipo de marcaje'
    )
    fecha_hora = models.DateTimeField(verbose_name='fecha y hora')
    ip_address = models.GenericIPAddressField(
        verbose_name='dirección IP'
    )
    validado = models.BooleanField(
        default=False,
        verbose_name='validado'
    )
    
    class Meta:
        verbose_name = 'marcaje'
        verbose_name_plural = 'marcajes'
        ordering = ['-fecha_hora']
    
    def __str__(self):
        return f"{self.operario} - {self.get_tipo_display()} - {self.fecha_hora}"


class ConfiguracionNomina(models.Model):
    """Configuración de nómina por operario."""
    
    operario = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT,
        related_name='configuracion_nomina',
        verbose_name='operario'
    )
    salario_base_mensual = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name='salario base mensual'
    )
    porcentaje_ss_patronal = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=31.50,
        verbose_name='% SS patronal'
    )
    
    class Meta:
        verbose_name = 'configuración de nómina'
        verbose_name_plural = 'configuraciones de nómina'
    
    def __str__(self):
        return f"Nómina: {self.operario}"
    
    @property
    def coste_mensual_total(self):
        """Coste mensual total incluyendo SS patronal."""
        if self.salario_base_mensual is None or self.porcentaje_ss_patronal is None:
            return 0
        return self.salario_base_mensual * (1 + self.porcentaje_ss_patronal / 100)

    @property
    def coste_hora(self):
        """Coste real por hora."""
        total = self.coste_mensual_total
        if not total:
            return 0
        horas_mensuales = 22 * 8  # 22 días × 8 horas
        return total / horas_mensuales
