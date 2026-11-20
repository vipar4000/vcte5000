"""Formulario de nómina: importes automáticos según la ficha del trabajador."""
from django import forms

from .models import NominaEstructura
from .services import importes_para_periodo
from apps.accounts.models import User

CLASE_INPUT = 'w-full px-3 py-2 border rounded-lg'


class NominaEstructuraForm(forms.ModelForm):
    """Nómina de estructura.

    Al elegir el empleado y la periodicidad, los importes se calculan solos a
    partir de su ficha (salario base mensual, % SS patronal, % SS obrera y
    % IRPF). El usuario puede desmarcar la casilla y escribirlos a mano.
    """

    calcular_automaticamente = forms.BooleanField(
        required=False,
        initial=True,
        label='Calcular importes según la ficha del trabajador',
        help_text=(
            'Salario, SS e IRPF se reparten según su periodicidad (mensual, '
            'quincenal o semanal) y sus porcentajes.'
        ),
    )

    class Meta:
        model = NominaEstructura
        fields = [
            'empleado', 'periodo', 'fecha_nomina',
            'salario_bruto', 'ss_patronal',
            'retencion_irpf', 'ss_obrera',
        ]
        widgets = {
            'empleado': forms.Select(attrs={'class': CLASE_INPUT}),
            'periodo': forms.Select(attrs={'class': CLASE_INPUT}),
            'fecha_nomina': forms.DateInput(attrs={
                'type': 'date', 'class': CLASE_INPUT,
            }),
            'salario_bruto': forms.NumberInput(attrs={
                'class': CLASE_INPUT, 'step': '0.01', 'placeholder': '0,00',
            }),
            'ss_patronal': forms.NumberInput(attrs={
                'class': CLASE_INPUT, 'step': '0.01', 'placeholder': '0,00',
            }),
            'retencion_irpf': forms.NumberInput(attrs={
                'class': CLASE_INPUT, 'step': '0.01', 'placeholder': '0,00',
            }),
            'ss_obrera': forms.NumberInput(attrs={
                'class': CLASE_INPUT, 'step': '0.01', 'placeholder': '0,00',
            }),
        }
        labels = {
            'empleado': 'Trabajador',
            'periodo': 'Periodicidad',
            'fecha_nomina': 'Fecha de nómina',
            'salario_bruto': 'Salario Bruto (640)',
            'ss_patronal': 'SS Patronal (642)',
            'retencion_irpf': 'Retención IRPF (4751)',
            'ss_obrera': 'SS Obrera (476)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['empleado'].queryset = User.objects.filter(
            is_active=True
        ).order_by('first_name', 'last_name')
        # Con el cálculo automático, los importes pueden ir vacíos
        self.fields['calcular_automaticamente'].initial = True
        for campo in ('salario_bruto', 'ss_patronal', 'retencion_irpf', 'ss_obrera'):
            self.fields[campo].required = False

    def clean(self):
        datos = super().clean()
        empleado = datos.get('empleado')
        if not empleado:
            return datos

        periodo = datos.get('periodo') or getattr(
            empleado, 'periodicidad_pago', 'MENSUAL'
        )
        datos['periodo'] = periodo

        if datos.get('calcular_automaticamente'):
            importes = importes_para_periodo(empleado, periodo)
            if importes['salario_bruto'] <= 0:
                raise forms.ValidationError(
                    f'{empleado.nombre_completo} no tiene salario base en su ficha. '
                    f'Rellénelo en 👥 Usuarios o escriba los importes a mano.'
                )
            datos['salario_bruto'] = importes['salario_bruto']
            datos['ss_patronal'] = importes['ss_patronal']
            datos['ss_obrera'] = importes['ss_obrera']
            datos['retencion_irpf'] = importes['retencion_irpf']
        else:
            if not datos.get('salario_bruto'):
                self.add_error(
                    'salario_bruto',
                    'Indique el salario bruto o marque el cálculo automático.',
                )

        return datos
