"""Formulario de alta y edición de usuarios desde el propio ERP.

Sustituye al admin de Django para la gestión diaria: mismo aspecto que el resto
del sistema y sin necesidad de que el usuario sea `is_staff`.
"""
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import User

CLASE_INPUT = 'w-full px-3 py-2 border rounded-lg'
CLASE_SELECT = 'w-full px-3 py-2 border rounded-lg'


class UsuarioForm(forms.ModelForm):
    """Alta y edición de usuarios y fichas laborales.

    Dos modos:
      - Con acceso: usuario, correo y contraseña (como siempre).
      - Sin acceso: solo ficha laboral (obreros, limpieza, auxiliares). No pide
        usuario ni contraseña: se genera un usuario interno y una contraseña
        inservible, pero aparece en nóminas y puede fichar con su PIN.
    """

    password = forms.CharField(
        label='Contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': CLASE_INPUT, 'autocomplete': 'new-password',
        }),
        help_text='Mínimo 8 caracteres. Al editar, déjelo vacío para no cambiarla.',
    )
    password2 = forms.CharField(
        label='Repetir contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': CLASE_INPUT, 'autocomplete': 'new-password',
        }),
    )

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email', 'movil',
            'puesto_trabajo',
            'rol', 'pin_kiosco', 'is_active', 'puede_eliminar',
            'salario_base_mensual', 'porcentaje_ss_patronal',
            'sin_acceso', 'periodicidad_pago', 'porcentaje_irpf',
            'porcentaje_ss_obrera',
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': CLASE_INPUT, 'autocomplete': 'off'}),
            'first_name': forms.TextInput(attrs={'class': CLASE_INPUT}),
            'last_name': forms.TextInput(attrs={'class': CLASE_INPUT}),
            'email': forms.EmailInput(attrs={'class': CLASE_INPUT}),
            'movil': forms.TextInput(attrs={'class': CLASE_INPUT, 'placeholder': '600123456'}),
            'puesto_trabajo': forms.TextInput(attrs={'class': CLASE_INPUT}),
            'rol': forms.Select(attrs={'class': CLASE_SELECT}),
            'pin_kiosco': forms.TextInput(attrs={
                'class': CLASE_INPUT, 'maxlength': '4', 'placeholder': '1234',
            }),
            'salario_base_mensual': forms.NumberInput(attrs={
                'class': CLASE_INPUT, 'step': '0.01', 'placeholder': '0,00',
            }),
            'porcentaje_ss_patronal': forms.NumberInput(attrs={
                'class': CLASE_INPUT, 'step': '0.01',
            }),
            'periodicidad_pago': forms.Select(attrs={'class': CLASE_SELECT}),
            'porcentaje_irpf': forms.NumberInput(attrs={
                'class': CLASE_INPUT, 'step': '0.01', 'min': '0', 'max': '100',
            }),
            'porcentaje_ss_obrera': forms.NumberInput(attrs={
                'class': CLASE_INPUT, 'step': '0.01', 'min': '0', 'max': '100',
            }),
            'sin_acceso': forms.CheckboxInput(attrs={'class': 'h-4 w-4'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        es_alta = self.instance.pk is None

        # En un POST manda el checkbox; en GET, lo guardado
        if self.is_bound:
            self.sin_acceso = self.data.get('sin_acceso') in ('on', 'true', '1', True)
        else:
            self.sin_acceso = bool(getattr(self.instance, 'sin_acceso', False))

        self.fields['password'].required = es_alta and not self.sin_acceso
        self.fields['password2'].required = es_alta and not self.sin_acceso
        self.fields['username'].required = not self.sin_acceso
        self.fields['email'].required = not self.sin_acceso
        for campo in ('periodicidad_pago', 'porcentaje_irpf', 'porcentaje_ss_obrera'):
            self.fields[campo].required = False

        if self.sin_acceso:
            self.fields['password'].help_text = (
                'Un trabajador sin acceso no necesita contraseña.'
            )

    def clean_pin_kiosco(self):
        pin = (self.cleaned_data.get('pin_kiosco') or '').strip()
        if pin and (not pin.isdigit() or len(pin) != 4):
            raise ValidationError('El PIN de kiosco debe tener exactamente 4 dígitos.')
        if pin:
            otros = User.objects.filter(pin_kiosco=pin, is_active=True)
            if self.instance.pk:
                otros = otros.exclude(pk=self.instance.pk)
            if otros.exists():
                raise ValidationError(
                    'Ese PIN ya lo usa otro trabajador. Elija otro de 4 dígitos.'
                )
        return pin

    def clean(self):
        datos = super().clean()
        password = datos.get('password')
        password2 = datos.get('password2')

        if password or password2:
            if password != password2:
                raise ValidationError('Las dos contraseñas no coinciden.')
            if len(password or '') < 8:
                raise ValidationError('La contraseña debe tener al menos 8 caracteres.')

        sin_acceso = self.sin_acceso

        if sin_acceso:
            if password:
                raise ValidationError(
                    'Un trabajador sin acceso no lleva contraseña: desmarque '
                    '«Trabajador sin acceso» si quiere darle entrada al ERP.'
                )
            if not (datos.get('first_name') or datos.get('last_name')):
                raise ValidationError(
                    'Indique al menos el nombre del trabajador (es lo que verá en nóminas).'
                )
            if datos.get('rol') == 'OPERARIO' and not datos.get('pin_kiosco'):
                raise ValidationError(
                    'Para fichar en taller hace falta el PIN de 4 dígitos.'
                )
            # Usuario interno único y correo de relleno
            if not datos.get('username'):
                datos['username'] = self._username_interno(datos)
            if not datos.get('email'):
                datos['email'] = f'{datos["username"]}@sin-acceso.local'
        else:
            # Al quitar el acceso hace falta una contraseña utilizable
            if self.instance.pk and not self.instance.has_usable_password() and not password:
                raise ValidationError(
                    'Este trabajador no tenía contraseña. Indique una para darle '
                    'acceso al ERP.'
                )

        if not datos.get('periodicidad_pago'):
            datos['periodicidad_pago'] = getattr(
                self.instance, 'periodicidad_pago', None
            ) or 'MENSUAL'
        if datos.get('porcentaje_irpf') is None:
            datos['porcentaje_irpf'] = getattr(
                self.instance, 'porcentaje_irpf', None
            ) or Decimal('6.00')
        if datos.get('porcentaje_ss_obrera') is None:
            datos['porcentaje_ss_obrera'] = getattr(
                self.instance, 'porcentaje_ss_obrera', None
            ) or Decimal('6.35')

        self.cleaned_data = datos
        return datos

    def _username_interno(self, datos):
        from uuid import uuid4

        base = (datos.get('first_name') or 'trabajador').strip().lower()
        base = ''.join(c for c in base if c.isalnum()) or 'trabajador'
        while True:
            candidato = f'{base}-{uuid4().hex[:6]}'
            if not User.objects.filter(username=candidato).exists():
                return candidato

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.sin_acceso:
            # Sin credenciales: no puede iniciar sesión
            usuario.set_unusable_password()
            usuario.sin_acceso = True
        else:
            password = self.cleaned_data.get('password')
            if password:
                usuario.set_password(password)
            usuario.sin_acceso = False
        if commit:
            usuario.save()
        return usuario
