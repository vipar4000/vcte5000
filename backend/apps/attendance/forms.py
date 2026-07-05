from django import forms
from django.contrib.auth import get_user_model
from .models import Marcaje, ConfiguracionNomina

User = get_user_model()


class MarcajeForm(forms.ModelForm):
    """Formulario para registrar marcajes."""
    
    class Meta:
        model = Marcaje
        fields = ['operario', 'tipo']
        widgets = {
            'operario': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'tipo': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['operario'].queryset = User.objects.filter(
            rol='OPERARIO', is_active=True
        ).order_by('first_name', 'last_name')


class PinMarcajeForm(forms.Form):
    """Formulario de fichaje por PIN."""
    
    pin = forms.CharField(
        max_length=4,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-6 py-4 text-center text-3xl border-2 rounded-lg focus:ring-2 focus:ring-eurocar-light',
            'placeholder': '••••',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'autocomplete': 'off',
        })
    )
    
    def clean_pin(self):
        pin = self.cleaned_data.get('pin')
        if not pin.isdigit():
            raise forms.ValidationError('El PIN debe contener solo números.')
        return pin


class ConfiguracionNominaForm(forms.ModelForm):
    """Formulario de configuración de nómina."""
    
    class Meta:
        model = ConfiguracionNomina
        fields = ['operario', 'salario_base_mensual', 'porcentaje_ss_patronal']
        widgets = {
            'operario': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'salario_base_mensual': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
            }),
            'porcentaje_ss_patronal': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
                'max': '100',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['operario'].queryset = User.objects.filter(
            rol='OPERARIO', is_active=True
        ).order_by('first_name', 'last_name')
