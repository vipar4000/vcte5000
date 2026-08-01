from django import forms
from django.forms import inlineformset_factory
from .models import GastoEstructura, InversionInicial, LineaInversionInicial
from apps.core.formatting import format_euros


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


class InversionInicialForm(forms.ModelForm):
    """Cabecera del asistente de inversión inicial."""

    class Meta:
        model = InversionInicial
        fields = [
            'fecha_emision', 'proveedor_acreedor', 'numero_factura',
            'forma_pago', 'total_factura_fisico', 'documento_pdf',
        ]
        widgets = {
            'fecha_emision': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg', 'type': 'date',
            }),
            'proveedor_acreedor': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'Nombre del proveedor o acreedor',
            }),
            'numero_factura': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'FAC-2024-001',
            }),
            'forma_pago': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'total_factura_fisico': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'step': '0.01', 'min': '0',
            }),
            'documento_pdf': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'accept': 'application/pdf,image/png,image/jpeg',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['documento_pdf'].required = True
        self.fields['documento_pdf'].help_text = (
            'PDF, PNG o JPEG. Se renombrará como INV_INICIAL_[ID]_[NUM_FACTURA].'
        )

    def clean(self):
        cleaned = super().clean()
        total_fisico = cleaned.get('total_factura_fisico')
        if total_fisico is None:
            return cleaned
        lineas = getattr(self, 'lineas_formset', None)
        if lineas is None:
            return cleaned
        total_calculado = sum(
            (l.cleaned_data.get('base_imponible', 0) or 0) *
            (1 + (l.cleaned_data.get('tipo_iva', 0) or 0) / 100)
            for l in lineas.forms
            if l.cleaned_data and not l.cleaned_data.get('DELETE', False)
        )
        from decimal import Decimal
        lineas_validas = [
            l for l in lineas.forms
            if l.cleaned_data and not l.cleaned_data.get('DELETE', False)
            and l.cleaned_data.get('base_imponible')
        ]
        if not lineas_validas:
            raise forms.ValidationError(
                'Debe introducir al menos una línea de desglose con importe.'
            )
        total_calculado = sum(
            (Decimal(str(l.cleaned_data['base_imponible'])) *
             (1 + Decimal(str(l.cleaned_data.get('tipo_iva', 0) or 0)) / 100)).quantize(Decimal('0.01'))
            for l in lineas_validas
        )
        if total_calculado != Decimal(str(total_fisico)).quantize(Decimal('0.01')):
            raise forms.ValidationError(
                f'Descuadre: el total calculado de las líneas ({format_euros(total_calculado)}) '
                f'no coincide con el Total Factura Físico ({format_euros(total_fisico)}).'
            )
        return cleaned


class LineaInversionInicialForm(forms.ModelForm):
    """Línea de desglose de la inversión inicial."""

    class Meta:
        model = LineaInversionInicial
        fields = ['categoria', 'concepto', 'base_imponible', 'tipo_iva']
        widgets = {
            'categoria': forms.Select(attrs={
                'class': 'w-full px-2 py-1 border rounded-lg',
            }),
            'concepto': forms.TextInput(attrs={
                'class': 'w-full px-2 py-1 border rounded-lg',
                'placeholder': 'Descripción del artículo/servicio',
            }),
            'base_imponible': forms.NumberInput(attrs={
                'class': 'w-full px-2 py-1 border rounded-lg base-imponible',
                'step': '0.01', 'min': '0',
            }),
            'tipo_iva': forms.NumberInput(attrs={
                'class': 'w-full px-2 py-1 border rounded-lg tipo-iva',
                'step': '0.01', 'min': '0', 'max': '100',
            }),
        }


LineaInversionInicialFormSet = inlineformset_factory(
    InversionInicial, LineaInversionInicial,
    form=LineaInversionInicialForm,
    fields=['categoria', 'concepto', 'base_imponible', 'tipo_iva'],
    extra=1,
    can_delete=True,
)
