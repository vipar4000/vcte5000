from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP


class User(AbstractUser):
    """Modelo de usuario personalizado para R Car Rogil."""
    
    ROLES = [
        ('ADMIN', 'Administrador'),
        ('OPERARIO', 'Operario de Taller'),
        ('VENDEDOR', 'Vendedor'),
        ('GESTORIA', 'Gestoría Externa'),
    ]
    
    email = models.EmailField(unique=True, verbose_name='correo electrónico')
    rol = models.CharField(max_length=20, choices=ROLES, default='ADMIN', verbose_name='rol')
    movil = models.CharField(max_length=15, blank=True, verbose_name='móvil')
    pin_kiosco = models.CharField(max_length=4, blank=True, verbose_name='PIN kiosco')
    qr_code = models.ImageField(upload_to='qr/', blank=True, verbose_name='código QR')
    requires_password_change = models.BooleanField(
        default=False, 
        verbose_name='requiere cambio de contraseña'
    )
    failed_login_attempts = models.IntegerField(
        default=0, 
        verbose_name='intentos fallidos'
    )
    locked_until = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name='bloqueado hasta'
    )
    puede_eliminar = models.BooleanField(
        default=True,
        verbose_name='puede eliminar registros'
    )
    
    # Para operarios - coste por hora
    salario_base_mensual = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name='salario base mensual'
    )
    porcentaje_ss_patronal = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=31.50,
        verbose_name='% SS patronal'
    )
    
    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'
        ordering = ['-date_joined']
    
    def __str__(self):
        nombre = self.get_full_name().strip() or self.username
        return f"{nombre} ({self.get_rol_display()})"
    
    @property
    def is_admin(self):
        return self.rol == 'ADMIN' or self.is_superuser
    
    @property
    def is_operario(self):
        return self.rol == 'OPERARIO' or self.is_superuser
    
    @property
    def is_vendedor(self):
        return self.rol == 'VENDEDOR' or self.is_superuser
    
    @property
    def is_gestoria(self):
        return self.rol == 'GESTORIA' or self.is_superuser
    
    @property
    def coste_hora(self):
        """Calcula el coste real por hora incluyendo SS patronal.

        Redondeado a 2 decimales para evitar precisión infinita en cálculos
        contables.
        """
        salario = self.salario_base_mensual
        ss = self.porcentaje_ss_patronal
        if not salario or ss is None:
            return Decimal('0')
        salario = Decimal(str(salario))
        ss = Decimal(str(ss))
        coste_mensual = salario * (1 + ss / Decimal('100'))
        horas_mensuales = Decimal('176')  # 22 días × 8 horas
        return (coste_mensual / horas_mensuales).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    
    @property
    def is_locked(self):
        """Verifica si la cuenta está bloqueada."""
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False
    
    def lock_account(self):
        """Bloquea la cuenta por 1 hora."""
        self.locked_until = timezone.now() + timedelta(hours=1)
        self.save(update_fields=['locked_until'])
    
    def unlock_account(self):
        """Desbloquea la cuenta."""
        self.locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=['locked_until', 'failed_login_attempts'])
    
    def increment_failed_attempts(self):
        """Incrementa intentos fallidos y bloquea si es necesario."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.lock_account()
        else:
            self.save(update_fields=['failed_login_attempts'])
    
    def reset_failed_attempts(self):
        """Resetea intentos fallidos tras login exitoso."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=['failed_login_attempts', 'locked_until'])
