from django import forms
from .models import BancoCuenta, BancoMovimiento, Reserva


class BancoCuentaForm(forms.ModelForm):
    class Meta:
        model = BancoCuenta
        fields = ['nombre', 'iban', 'swift', 'cuenta_contable', 'activa']


class BancoMovimientoFilterForm(forms.Form):
    fecha_desde = forms.DateField(
        required=False, label='Desde',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    fecha_hasta = forms.DateField(
        required=False, label='Hasta',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    tipo = forms.ChoiceField(
        required=False, label='Tipo',
        choices=[('', 'Todos')] + BancoMovimiento.TIPO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    conciliado = forms.NullBooleanField(
        required=False, label='Conciliado',
        widget=forms.Select(
            attrs={'class': 'form-select'},
            choices=[
                ( '', 'Todos'),
                (True, 'Conciliados'),
                (False, 'Pendientes'),
            ]
        )
    )
    busqueda = forms.CharField(
        required=False, label='Buscar',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Concepto...'})
    )


class ReservaForm(forms.ModelForm):
    class Meta:
        model = Reserva
        fields = [
            'vehiculo', 'cliente_nombre', 'cliente_dni',
            'fecha_reserva', 'importe_reserva', 'notas',
        ]
        widgets = {
            'fecha_reserva': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'importe_reserva': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cliente_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'cliente_dni': forms.TextInput(attrs={'class': 'form-control'}),
            'vehiculo': forms.Select(attrs={'class': 'form-select'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ConciliacionUploadForm(forms.Form):
    archivo = forms.FileField(
        label='Extracto bancario (Excel o CSV)',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls,.csv'})
    )
    banco_cuenta = forms.ModelChoiceField(
        queryset=BancoCuenta.objects.filter(activa=True),
        label='Cuenta bancaria',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
