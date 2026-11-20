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
    """Configuración de nómina de un trabajador (se guarda en su ficha)."""

    periodicidad_pago = forms.ChoiceField(
        choices=User.PERIODICIDADES_PAGO,
        initial='MENSUAL',
        label='Periodicidad de pago',
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded-lg'}),
        help_text='Mensual, quincenal (2 pagos) o semanal (4 pagos al mes).',
    )
    porcentaje_irpf = forms.DecimalField(
        max_digits=5, decimal_places=2, initial='6.00',
        label='% IRPF',
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
            'step': '0.01', 'min': '0', 'max': '100',
        }),
    )
    porcentaje_ss_obrera = forms.DecimalField(
        max_digits=5, decimal_places=2, initial='6.35',
        label='% SS obrera',
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
            'step': '0.01', 'min': '0', 'max': '100',
        }),
    )

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
            is_active=True
        ).order_by('first_name', 'last_name')

        trabajador = getattr(self.instance, 'operario', None)
        if trabajador is not None and trabajador.pk:
            self.fields['periodicidad_pago'].initial = trabajador.periodicidad_pago
            self.fields['porcentaje_irpf'].initial = trabajador.porcentaje_irpf
            self.fields['porcentaje_ss_obrera'].initial = trabajador.porcentaje_ss_obrera

    def save(self, commit=True):
        """Guarda la configuración y la refleja en la ficha del trabajador."""
        config = super().save(commit=commit)
        if commit:
            trabajador = config.operario
            trabajador.salario_base_mensual = config.salario_base_mensual
            trabajador.porcentaje_ss_patronal = config.porcentaje_ss_patronal
            trabajador.periodicidad_pago = self.cleaned_data['periodicidad_pago']
            trabajador.porcentaje_irpf = self.cleaned_data['porcentaje_irpf']
            trabajador.porcentaje_ss_obrera = self.cleaned_data['porcentaje_ss_obrera']
            trabajador.save(update_fields=[
                'salario_base_mensual', 'porcentaje_ss_patronal',
                'periodicidad_pago', 'porcentaje_irpf', 'porcentaje_ss_obrera',
            ])
        return config
