from django import forms
from .models import NominaEstructura
from apps.accounts.models import User


class NominaEstructuraForm(forms.ModelForm):
    empleado = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
        }),
        label='Empleado',
    )

    class Meta:
        model = NominaEstructura
        fields = [
            'empleado', 'fecha_nomina',
            'salario_bruto', 'ss_patronal',
            'retencion_irpf', 'ss_obrera',
        ]
        widgets = {
            'fecha_nomina': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'salario_bruto': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01', 'placeholder': '0,00',
            }),
            'ss_patronal': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01', 'placeholder': '0,00',
            }),
            'retencion_irpf': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01', 'placeholder': '0,00',
            }),
            'ss_obrera': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01', 'placeholder': '0,00',
            }),
        }
        labels = {
            'fecha_nomina': 'Fecha de nómina',
            'salario_bruto': 'Salario Bruto (640)',
            'ss_patronal': 'SS Patronal (642)',
            'retencion_irpf': 'Retención IRPF (4751)',
            'ss_obrera': 'SS Obrera (476)',
        }
