from django import forms
from .models import HistorialReparacionGarantia


class HistorialReparacionGarantiaForm(forms.ModelForm):
    """Formulario para crear/editar reparaciones en garantía."""
    
    class Meta:
        model = HistorialReparacionGarantia
        fields = [
            'garantia',
            'fecha_ingreso_taller',
            'descripcion_averia',
            'estado',
            'costo_repuestos_interno',
            'costo_mano_obra_interno',
            'fecha_resolucion',
        ]
        widgets = {
            'fecha_ingreso_taller': forms.DateInput(attrs={'type': 'date'}),
            'fecha_resolucion': forms.DateInput(attrs={'type': 'date'}),
            'descripcion_averia': forms.Textarea(attrs={'rows': 4}),
        }


class FiltroGarantiasForm(forms.Form):
    """Filtros para la lista de garantías."""
    
    buscar = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Buscar por matrícula o cliente...'})
    )
    estado = forms.ChoiceField(
        choices=[
            ('', 'Todos'),
            ('vigente', 'Vigentes'),
            ('caducada', 'Caducadas'),
        ],
        required=False
    )
