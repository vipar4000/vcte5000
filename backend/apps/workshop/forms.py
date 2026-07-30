from django import forms
from django.contrib.auth import get_user_model
from .models import OrdenTrabajo, Material, MaterialUsado, CompraMaterial
from apps.vehicles.models import Vehiculo

User = get_user_model()


class OrdenTrabajoForm(forms.ModelForm):
    """Formulario para crear/editar órdenes de trabajo."""
    
    class Meta:
        model = OrdenTrabajo
        fields = [
            'vehiculo', 'operario', 'titulo', 'descripcion',
            'horas_estimadas', 'horas_reales', 'estado',
            'fecha_inicio', 'fecha_fin',
        ]
        widgets = {
            'vehiculo': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'operario': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'titulo': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'Ej: Reparación de parachoques',
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'rows': '4',
                'placeholder': 'Descripción detallada del trabajo...',
            }),
            'horas_estimadas': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.5',
                'min': '0',
            }),
            'horas_reales': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.5',
                'min': '0',
            }),
            'estado': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'type': 'date',
            }),
            'fecha_fin': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'type': 'date',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar vehículos que no estén vendidos
        self.fields['vehiculo'].queryset = (
            Vehiculo.objects.exclude(estado='VENDIDO')
            .order_by('-fecha_adquisicion')
        )
        # Solo mostrar operarios activos
        self.fields['operario'].queryset = (
            User.objects.filter(rol='OPERARIO', is_active=True)
            .order_by('first_name', 'last_name')
        )


class MaterialForm(forms.ModelForm):
    """Formulario para crear/editar materiales."""
    
    class Meta:
        model = Material
        fields = [
            'nombre', 'descripcion', 'unidad',
            'stock_actual', 'stock_minimo', 'precio_unitario',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'Ej: Pintura blanca',
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'rows': '2',
            }),
            'unidad': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'litros, kg, unidades',
            }),
            'stock_actual': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
            }),
            'stock_minimo': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
            }),
            'precio_unitario': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0',
            }),
        }


class MaterialSelectWidget(forms.Select):
    """Widget personalizado que agrega precio como data attribute."""
    
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            try:
                material = Material.objects.get(pk=value)
                option['attrs']['data-precio'] = str(material.precio_unitario)
            except (Material.DoesNotExist, ValueError):
                pass
        return option


class MaterialUsadoForm(forms.ModelForm):
    """Formulario para agregar material a una OT."""
    
    class Meta:
        model = MaterialUsado
        fields = ['material', 'cantidad']
        widgets = {
            'material': MaterialSelectWidget(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'onchange': 'calcularCostes()',
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01',
                'min': '0.01',
                'oninput': 'calcularCostes()',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = (
            Material.objects.filter(stock_actual__gt=0)
            .order_by('nombre')
        )


MaterialUsadoFormSet = forms.inlineformset_factory(
    OrdenTrabajo,
    MaterialUsado,
    form=MaterialUsadoForm,
    extra=1,
    can_delete=True,
)


class CompraMaterialForm(forms.ModelForm):
    """Formulario para registrar la compra de material de inventario.

    El campo "Material" es un desplegable con los materiales del catálogo.
    El material debe existir previamente en inventario.
    """

    material = forms.ModelChoiceField(
        queryset=Material.objects.all(),
        required=True, label='Material *',
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
        }),
    )

    class Meta:
        model = CompraMaterial
        fields = [
            'material', 'cantidad', 'precio_unitario',
            'fecha_compra', 'proveedor', 'cif_nif', 'numero_factura',
            'tipo_inventario', 'tipo_iva', 'documento_pdf',
        ]
        widgets = {
            'cantidad': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01', 'min': '0.01',
            }),
            'precio_unitario': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01', 'min': '0',
            }),
            'fecha_compra': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'type': 'date',
            }),
            'proveedor': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'Nombre del proveedor',
            }),
            'cif_nif': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'B12345678', 'maxlength': '15',
            }),
            'numero_factura': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'Ej: FAC-2026-0011',
            }),
            'tipo_inventario': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'tipo_iva': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01', 'min': '0', 'max': '100',
            }),
            'documento_pdf': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
        }
