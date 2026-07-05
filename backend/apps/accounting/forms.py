from django import forms
from .models import AsientoContable, MovimientoContable, CuentaContable


class AsientoContableForm(forms.ModelForm):
    """Formulario para crear/editar asientos contables."""
    
    class Meta:
        model = AsientoContable
        fields = [
            'numero',
            'fecha',
            'concepto',
            'estado',
            'tipo_documento',
            'documento_id',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'concepto': forms.Textarea(attrs={'rows': 3}),
        }


class MovimientoContableForm(forms.ModelForm):
    """Formulario para movimientos contables."""
    
    class Meta:
        model = MovimientoContable
        fields = [
            'cuenta',
            'debe',
            'haber',
            'descripcion',
        ]
        widgets = {
            'descripcion': forms.TextInput(attrs={'placeholder': 'Descripción del movimiento'}),
        }


MovimientoContableFormSet = forms.inlineformset_factory(
    AsientoContable,
    MovimientoContable,
    form=MovimientoContableForm,
    extra=2,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class FiltroAsientosForm(forms.Form):
    """Filtros para la lista de asientos."""
    
    buscar = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Buscar por número o concepto...'})
    )
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    estado = forms.ChoiceField(
        choices=[('', 'Todos')] + AsientoContable.ESTADOS,
        required=False
    )


class CuentaContableForm(forms.ModelForm):
    """Formulario para cuentas contables."""
    
    class Meta:
        model = CuentaContable
        fields = [
            'codigo',
            'nombre',
            'tipo',
            'padre',
            'activa',
        ]
