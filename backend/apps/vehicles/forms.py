from django import forms
from django.forms import inlineformset_factory
from .models import Vehiculo, ImagenVehiculo


class VehiculoForm(forms.ModelForm):
    """Formulario para crear/editar vehículos."""
    
    class Meta:
        model = Vehiculo
        fields = [
            'matricula', 'bastidor', 'marca', 'modelo', 'anio',
            'combustible', 'kilometraje', 'tipo_dano', 'etiqueta_ambiental',
            'estado', 'fecha_adquisicion', 'plataforma_subasta',
            'precio_subasta', 'tasas_sala', 'logistica_grua',
            'precio_venta',
            'descripcion_dano', 'imagen_principal',
        ]
        widgets = {
            'matricula': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': '1234ABC',
                'maxlength': '7',
            }),
            'bastidor': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'WVWZZZ3CZWE123456',
                'maxlength': '17',
            }),
            'marca': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'Volkswagen',
            }),
            'modelo': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'Golf',
            }),
            'anio': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'min': '1900',
                'max': '2030',
            }),
            'combustible': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'kilometraje': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'min': '0',
            }),
            'tipo_dano': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'etiqueta_ambiental': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'estado': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'fecha_adquisicion': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'type': 'date',
            }),
            'plataforma_subasta': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'precio_subasta': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
            }),
            'tasas_sala': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
            }),
            'logistica_grua': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
            }),
            'precio_venta': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Precio de venta en euros',
            }),
            'descripcion_dano': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'rows': '4',
                'placeholder': 'Descripción del estado del vehículo...',
            }),
            'imagen_principal': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
        }
    
    def clean_matricula(self):
        matricula = self.cleaned_data.get('matricula')
        if len(matricula) != 7:
            raise forms.ValidationError('La matrícula debe tener 7 caracteres.')
        return matricula.upper()
    
    def clean_bastidor(self):
        bastidor = self.cleaned_data.get('bastidor')
        if len(bastidor) != 17:
            raise forms.ValidationError('El bastidor/VIN debe tener 17 caracteres.')
        return bastidor.upper()
    
    def clean_anio(self):
        anio = self.cleaned_data.get('anio')
        if anio < 1900 or anio > 2030:
            raise forms.ValidationError('El año debe estar entre 1900 y 2030.')
        return anio


class VehiculoBusquedaForm(forms.Form):
    """Formulario de búsqueda de vehículos."""
    
    busqueda = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg',
            'placeholder': 'Buscar por matrícula, marca, modelo...',
        })
    )
    estado = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos los estados')] + Vehiculo.ESTADOS,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border rounded-lg',
        })
    )
    marca = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'px-4 py-2 border rounded-lg',
            'placeholder': 'Marca',
        })
    )


ImagenVehiculoFormSet = inlineformset_factory(
    Vehiculo, ImagenVehiculo,
    fields=['imagen', 'es_principal', 'orden'],
    extra=1,
    max_num=8,
    can_delete=True,
)
