from django import forms
from .models import BancoCuenta, BancoMovimiento, Reserva


class BancoCuentaForm(forms.ModelForm):
    deposito_inicial = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False,
        label='Deposito inicial',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    notas_deposito = forms.CharField(
        required=False, label='Notas del deposito',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )
    fecha_deposito = forms.DateField(
        required=False,
        label='Fecha del deposito',
        help_text='Fecha real en la que el banco abono el dinero (no la de hoy).',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )

    class Meta:
        model = BancoCuenta
        fields = ['nombre', 'iban', 'swift', 'cuenta_contable', 'activa',
                  'soporte_deposito', 'deposito_inicial', 'fecha_deposito',
                  'notas_deposito']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: BBVA Empresa'}),
            'iban': forms.TextInput(attrs={'class': 'form-control'}),
            'swift': forms.TextInput(attrs={'class': 'form-control'}),
            'cuenta_contable': forms.Select(attrs={'class': 'form-select'}),
            'soporte_deposito': forms.ClearableFileInput(
                attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}
            ),
        }

    def __init__(self, *args, editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['iban'].required = False
        self.fields['iban'].label = 'IBAN (no aplica a la caja)'
        self.fields['cuenta_contable'].label = (
            'Cuenta contable (570 Caja / 572 Banco)'
        )
        if editing:
            del self.fields['deposito_inicial']
            del self.fields['fecha_deposito']
            del self.fields['notas_deposito']
            del self.fields['soporte_deposito']

    def clean(self):
        datos = super().clean()
        cuenta = datos.get('cuenta_contable')
        iban = (datos.get('iban') or '').strip()

        if cuenta is not None and cuenta.codigo.startswith('570'):
            # Caja de efectivo: no tiene IBAN ni SWIFT.
            datos['iban'] = None
            datos['swift'] = ''
            if not (datos.get('nombre') or '').strip():
                datos['nombre'] = 'Caja'
        elif not iban:
            self.add_error(
                'iban',
                'El IBAN es obligatorio para una cuenta bancaria. '
                'Solo la caja (570) puede quedar sin IBAN.',
            )
        return datos


class TraspasoForm(forms.Form):
    """Traspaso de efectivo entre dos cuentas de tesorería (banco <-> caja)."""

    origen = forms.ModelChoiceField(
        queryset=BancoCuenta.objects.filter(activa=True),
        label='Cuenta de origen *',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    destino = forms.ModelChoiceField(
        queryset=BancoCuenta.objects.filter(activa=True),
        label='Cuenta de destino *',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    fecha = forms.DateField(
        label='Fecha del traspaso *',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    importe = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=0.01,
        label='Importe *',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
    concepto = forms.CharField(
        max_length=150, required=False,
        label='Concepto',
        help_text='Por defecto: «Traspaso de tesorería».',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    soporte = forms.FileField(
        required=False,
        label='Resguardo (PDF o imagen)',
        help_text='Por ejemplo, el resguardo de retirada de efectivo del banco.',
        widget=forms.ClearableFileInput(
            attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}
        ),
    )

    def __init__(self, *args, **kwargs):
        origen = kwargs.pop('origen', None)
        super().__init__(*args, **kwargs)
        if origen is not None:
            self.fields['origen'].initial = origen
            self.fields['origen'].queryset = BancoCuenta.objects.filter(
                activa=True
            )

    def clean(self):
        datos = super().clean()
        origen = datos.get('origen')
        destino = datos.get('destino')
        if origen and destino and origen.pk == destino.pk:
            raise forms.ValidationError(
                'La cuenta de origen y la de destino deben ser distintas.'
            )
        return datos


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
    """Reserva con los datos fiscales del comprador (para la factura de anticipo)."""

    class Meta:
        model = Reserva
        fields = [
            'vehiculo',
            'tipo_cliente', 'cliente_nombre', 'cliente_dni',
            'cliente_direccion', 'cliente_poblacion', 'cliente_provincia',
            'cliente_cp', 'cliente_telefono', 'cliente_email',
            'fecha_reserva', 'importe_reserva', 'metodo_pago', 'notas',
        ]
        widgets = {
            'vehiculo': forms.Select(attrs={'class': 'form-select'}),
            'tipo_cliente': forms.Select(attrs={'class': 'form-select'}),
            'cliente_nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre completo o razón social',
            }),
            'cliente_dni': forms.TextInput(attrs={
                'class': 'form-control', 'maxlength': '9', 'placeholder': '12345678A',
            }),
            'cliente_direccion': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Calle y número',
            }),
            'cliente_poblacion': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Madrid',
            }),
            'cliente_provincia': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Madrid',
            }),
            'cliente_cp': forms.TextInput(attrs={
                'class': 'form-control', 'maxlength': '5', 'placeholder': '28001',
            }),
            'cliente_telefono': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': '612345678',
            }),
            'cliente_email': forms.EmailInput(attrs={
                'class': 'form-control', 'placeholder': 'cliente@email.com',
            }),
            'fecha_reserva': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-control',
            }),
            'importe_reserva': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01',
            }),
            'metodo_pago': forms.Select(attrs={'class': 'form-select'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'vehiculo': 'Vehículo *',
            'tipo_cliente': 'Tipo de cliente *',
            'cliente_nombre': 'Nombre completo / Razón social *',
            'cliente_dni': 'DNI / NIE / CIF *',
            'cliente_direccion': 'Dirección fiscal (calle y número) *',
            'cliente_poblacion': 'Población *',
            'cliente_provincia': 'Provincia *',
            'cliente_cp': 'Código postal *',
            'cliente_telefono': 'Teléfono *',
            'cliente_email': 'Email',
            'fecha_reserva': 'Fecha de la reserva *',
            'importe_reserva': 'Importe de la señal (€) *',
            'metodo_pago': 'Método de pago *',
            'notas': 'Notas',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La dirección fiscal es imprescindible para emitir la factura
        for campo in (
            'cliente_direccion', 'cliente_poblacion',
            'cliente_provincia', 'cliente_cp', 'cliente_telefono',
        ):
            self.fields[campo].required = True

    def clean_cliente_cp(self):
        cp = (self.cleaned_data.get('cliente_cp') or '').strip()
        if cp and (not cp.isdigit() or len(cp) != 5):
            raise forms.ValidationError('El código postal debe tener 5 dígitos.')
        return cp


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


class DepositoForm(forms.Form):
    fecha = forms.DateField(
        label='Fecha del deposito',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    importe = forms.DecimalField(
        max_digits=12, decimal_places=2,
        label='Importe',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    concepto = forms.CharField(
        max_length=255, initial='Deposito',
        label='Concepto',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    notas = forms.CharField(
        required=False, label='Notas',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )
    soporte = forms.FileField(
        required=False, label='Soporte (PDF, imagen)',
        widget=forms.ClearableFileInput(
            attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}
        )
    )
