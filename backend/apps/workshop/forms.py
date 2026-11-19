from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from django.forms import formset_factory
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
        pk_value = getattr(value, 'value', value)
        if pk_value:
            try:
                material = Material.objects.get(pk=pk_value)
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


class CompraFacturaForm(forms.Form):
    """Cabecera de factura — datos compartidos por todas las líneas de material."""

    proveedor = forms.CharField(
        max_length=150, label='Proveedor *',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
            'placeholder': 'Nombre del proveedor',
        }),
    )
    cif_nif = forms.CharField(
        max_length=15, label='CIF/NIF *',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
            'placeholder': 'B12345678',
        }),
    )
    fecha_compra = forms.DateField(
        label='Fecha de compra *',
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
            'type': 'date',
        }),
    )
    fecha_vencimiento = forms.DateField(
        required=False, label='Fecha de vencimiento',
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
            'type': 'date',
        }),
    )
    numero_factura = forms.CharField(
        max_length=50, required=False, label='Número de factura',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
            'placeholder': 'Ej: FAC-2026-0011',
        }),
    )
    tipo_inventario = forms.ChoiceField(
        choices=CompraMaterial.TIPOS_INVENTARIO, label='Cuenta de inventario *',
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
        }),
    )
    tipo_iva = forms.DecimalField(
        max_digits=4, decimal_places=2, initial=Decimal('21.00'),
        label='Tipo IVA (%)',
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
            'step': '0.01', 'min': '0', 'max': '100',
        }),
    )
    forma_pago = forms.ChoiceField(
        required=False, label='Forma de pago',
        choices=[
            ('', 'Crédito (acreedores 410) — queda pendiente de pago'),
            ('572', 'Contado — Banco (572, genera EGRESO)'),
            ('570', 'Contado — Caja (570)'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
        }),
    )
    pagado = forms.BooleanField(
        required=False, label='Pagar ahora (solo crédito)',
        help_text='Solo aplica si la forma de pago es Crédito (410). Al marcar, '
                  'cada línea genera automáticamente su asiento de pago '
                  '(DEBE 410 / HABER tesorería) y, si es banco, el EGRESO en el '
                  'módulo Banco.',
        widget=forms.CheckboxInput(attrs={
            'class': 'rounded',
        }),
    )
    fecha_pago = forms.DateField(
        required=False, label='Fecha de pago',
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
            'type': 'date',
        }),
    )
    cuenta_pago = forms.ChoiceField(
        required=False, label='Cuenta de pago (banco/caja)',
        choices=[
            ('', 'Banco (572, por defecto)'),
            ('572', 'Banco (572)'),
            ('570', 'Caja (570)'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
        }),
    )
    documento_pdf = forms.FileField(
        required=False, label='Factura PDF',
        widget=forms.FileInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
        }),
    )

    def clean(self):
        datos = super().clean()
        forma_pago = datos.get('forma_pago') or ''
        pagado = datos.get('pagado', False)
        vencimiento = datos.get('fecha_vencimiento')
        fecha_compra = datos.get('fecha_compra')

        # La fecha de vencimiento es el dato de tesorería de las compras a
        # crédito: sin ella no se puede avisar de una factura vencida.
        a_credito = not forma_pago or forma_pago == '410'
        if a_credito and not pagado and not vencimiento:
            self.add_error(
                'fecha_vencimiento',
                'Indique la fecha de vencimiento: es una compra a crédito '
                'pendiente de pago.',
            )
        if vencimiento and fecha_compra and vencimiento < fecha_compra:
            self.add_error(
                'fecha_vencimiento',
                'La fecha de vencimiento no puede ser anterior a la fecha de compra.',
            )
        return datos


UNIDADES_SUGERIDAS = [
    'unidades', 'litros', 'juegos', 'pares', 'kg', 'metros', 'botes', 'cajas',
]


class CompraMaterialLineaForm(forms.Form):
    """Una línea de factura: el material se escribe por su nombre.

    Si el nombre coincide con uno existente (sin distinguir mayúsculas) se usa
    ese material y la compra suma al stock. Si es nuevo, se crea
    automáticamente al guardar la factura; en ese caso hay que indicar la
    unidad de medida.
    """

    material = forms.CharField(
        max_length=150, label='Material *',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-2 py-1 text-sm border rounded-lg material-input',
            'list': 'materiales-disponibles',
            'autocomplete': 'off',
            'placeholder': 'Escriba o elija…',
        }),
    )
    unidad = forms.CharField(
        required=False, max_length=20, label='Unidad',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-2 py-1 text-sm border rounded-lg',
            'list': 'unidades-disponibles',
            'autocomplete': 'off',
            'placeholder': 'solo si es nuevo',
        }),
    )
    cantidad = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=0.01, label='Cantidad *',
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-2 py-1 text-sm border rounded-lg text-right',
            'step': '0.01', 'min': '0.01',
        }),
    )
    precio_unitario = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=0, label='Precio unitario (€) *',
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-2 py-1 text-sm border rounded-lg text-right',
            'step': '0.01', 'min': '0',
        }),
    )

    def clean_material(self):
        nombre = ' '.join((self.cleaned_data.get('material') or '').split())
        if not nombre:
            raise forms.ValidationError('Escriba el nombre del material.')
        return nombre

    def clean(self):
        datos = super().clean()
        nombre = datos.get('material')
        if not nombre:
            return datos

        existente = Material.objects.filter(nombre__iexact=nombre).first()
        datos['material_existente'] = existente
        if existente is None:
            unidad = (datos.get('unidad') or '').strip()
            if not unidad:
                self.add_error(
                    'unidad',
                    'Material nuevo: indique la unidad (litros, unidades, juegos…).',
                )
            else:
                datos['unidad'] = unidad
        return datos

    def resolver_material(self):
        """Devuelve el Material de la línea, creándolo si es nuevo.

        Debe llamarse dentro de la transacción de la vista: así, si alguna línea
        falla, no queda ningún material suelto en el inventario.
        """
        datos = self.cleaned_data
        existente = datos.get('material_existente')
        if existente is not None:
            return existente
        return Material.objects.create(
            nombre=datos['material'],
            unidad=datos['unidad'],
            precio_unitario=datos.get('precio_unitario') or Decimal('0'),
            stock_actual=Decimal('0'),
        )


CompraMaterialLineaFormSet = formset_factory(
    CompraMaterialLineaForm,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
