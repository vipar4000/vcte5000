from django import forms
from .models import GastoEstructura


class GastoEstructuraForm(forms.ModelForm):
    """Formulario para crear/editar gastos de estructura."""

    class Meta:
        model = GastoEstructura
        fields = [
            'fecha_factura', 'proveedor_acreedor', 'cif_nif', 'categoria',
            'base_imponible', 'tipo_iva', 'retencion_irpf',
            'documento_pdf', 'pagado', 'fecha_pago',
        ]
        widgets = {
            'fecha_factura': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'type': 'date',
            }),
            'proveedor_acreedor': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'Nombre del proveedor o acreedor',
            }),
            'cif_nif': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'B12345678',
                'maxlength': '15',
            }),
            'categoria': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'base_imponible': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
            }),
            'tipo_iva': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
                'max': '100',
            }),
            'retencion_irpf': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
                'max': '100',
            }),
            'pagado': forms.CheckboxInput(attrs={
                'class': 'rounded',
            }),
            'fecha_pago': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'type': 'date',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_pago'].required = False
        self.fields['documento_pdf'].required = False


class GastoBusquedaForm(forms.Form):
    """Formulario de búsqueda de gastos."""

    busqueda = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg',
            'placeholder': 'Buscar por proveedor, CIF...',
        })
    )
    categoria = forms.ChoiceField(
        required=False,
        choices=[('', 'Todas las categorías')] + GastoEstructura.CATEGORIAS_GASTO,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border rounded-lg',
        })
    )
    pagado = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos'), ('True', 'Pagados'), ('False', 'Pendientes')],
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border rounded-lg',
        })
    )
