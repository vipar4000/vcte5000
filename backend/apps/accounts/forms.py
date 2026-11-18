"""Formulario de alta y edición de usuarios desde el propio ERP.

Sustituye al admin de Django para la gestión diaria: mismo aspecto que el resto
del sistema y sin necesidad de que el usuario sea `is_staff`.
"""
from django import forms
from django.core.exceptions import ValidationError

from .models import User

CLASE_INPUT = 'w-full px-3 py-2 border rounded-lg'
CLASE_SELECT = 'w-full px-3 py-2 border rounded-lg'


class UsuarioForm(forms.ModelForm):
    """Alta y edición de usuarios. La contraseña es opcional al editar."""

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
            'rol', 'pin_kiosco', 'is_active', 'puede_eliminar',
            'salario_base_mensual', 'porcentaje_ss_patronal',
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': CLASE_INPUT, 'autocomplete': 'off'}),
            'first_name': forms.TextInput(attrs={'class': CLASE_INPUT}),
            'last_name': forms.TextInput(attrs={'class': CLASE_INPUT}),
            'email': forms.EmailInput(attrs={'class': CLASE_INPUT}),
            'movil': forms.TextInput(attrs={'class': CLASE_INPUT, 'placeholder': '600123456'}),
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        es_alta = self.instance.pk is None
        self.fields['password'].required = es_alta
        self.fields['password2'].required = es_alta

    def clean_pin_kiosco(self):
        pin = (self.cleaned_data.get('pin_kiosco') or '').strip()
        if pin and (not pin.isdigit() or len(pin) != 4):
            raise ValidationError('El PIN de kiosco debe tener exactamente 4 dígitos.')
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
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            usuario.set_password(password)
        if commit:
            usuario.save()
        return usuario
