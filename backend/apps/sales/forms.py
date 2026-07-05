from django import forms
from .models import VentaVehiculo


class VentaVehiculoForm(forms.ModelForm):
    """Formulario para registrar ventas de vehículos."""
    
    class Meta:
        model = VentaVehiculo
        fields = [
            'vehiculo', 'tipo_cliente',
            'cliente_nombre', 'cliente_dni', 'cliente_direccion',
            'cliente_poblacion', 'cliente_provincia', 'cliente_cp',
            'cliente_telefono', 'cliente_email',
            'fecha_venta', 'metodo_pago', 'precio_venta',
        ]
        widgets = {
            'vehiculo': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'tipo_cliente': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'cliente_nombre': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'Nombre completo del cliente',
            }),
            'cliente_dni': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': '12345678A',
                'maxlength': '9',
            }),
            'cliente_direccion': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'rows': '2',
            }),
            'cliente_poblacion': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'Madrid',
            }),
            'cliente_provincia': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'Madrid',
            }),
            'cliente_cp': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': '28001',
                'maxlength': '5',
            }),
            'cliente_telefono': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': '612345678',
            }),
            'cliente_email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'cliente@email.com',
            }),
            'fecha_venta': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'type': 'date',
            }),
            'metodo_pago': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'precio_venta': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar vehículos listos para venta
        from apps.vehicles.models import Vehiculo
        self.fields['vehiculo'].queryset = Vehiculo.objects.filter(
            estado__in=['ACONDICIONADO', 'EN_VENTA']
        ).order_by('-fecha_adquisicion')
    
    def clean_cliente_dni(self):
        dni = self.cleaned_data.get('cliente_dni')
        if len(dni) != 9:
            raise forms.ValidationError('El DNI debe tener 9 caracteres.')
        return dni.upper()


class VentaBusquedaForm(forms.Form):
    """Formulario de búsqueda de ventas."""
    
    busqueda = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg',
            'placeholder': 'Buscar por cliente, matrícula...',
        })
    )
    metodo_pago = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos los métodos')] + VentaVehiculo.METODOS_PAGO,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border rounded-lg',
        })
    )
