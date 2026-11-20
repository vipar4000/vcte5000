import os
from decimal import Decimal, InvalidOperation
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet
from django.core.files.uploadedfile import UploadedFile
from django.utils.formats import number_format
from .images import ImagenInvalida, nombre_para, procesar_imagen
from .models import Vehiculo, ImagenVehiculo

# Tope de fotos adicionales por vehículo. Se aplica en el formset y en el JS.
MAX_IMAGENES = 15


def parsear_importe(valor):
    """Convierte un importe escrito por el usuario a ``Decimal``.

    Acepta ``7500.00``, ``7500,00``, ``7.500,00`` y ``7.500`` sin ambigüedad:
    si hay coma, los puntos son separadores de miles; si solo hay puntos, el
    último es decimal (formato estándar).

    Antes bastaba un punto de miles para que ``7.500,00`` se leyera como 7,5, y
    al reformatear un valor estándar (``7500.00``) se multiplicaba por 100.
    """
    if valor is None:
        return None
    texto = str(valor).strip().replace(' ', '').replace('€', '').replace('%', '')
    if not texto:
        return None
    if ',' in texto:
        # Formato español: 1.234,56
        texto = texto.replace('.', '').replace(',', '.')
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        raise ValidationError('Introduzca un número válido, por ejemplo 1.234,56.')


class ImporteField(forms.DecimalField):
    """DecimalField que entiende el formato español (1.234,56)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_digits', 12)
        kwargs.setdefault('decimal_places', 2)
        # Renderiza en formato español (7.500,00). El parseo lo hace
        # parsear_importe(), así que no depende de esta opción.
        kwargs.setdefault('localize', True)
        if 'widget' not in kwargs:
            kwargs['widget'] = forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg input-monetario',
                'placeholder': '0,00',
                'inputmode': 'decimal',
            })
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        return parsear_importe(value)


class VehiculoForm(forms.ModelForm):
    """Formulario para crear/editar vehículos."""

    # Importes: aceptan coma decimal y puntos de miles (ver parsear_importe)
    precio_subasta = ImporteField(label='Precio de adjudicación (€)')
    tasas_sala = ImporteField(label='Tasas de la sala (€)')
    logistica_grua = ImporteField(label='Logística/grúa (€)')
    precio_venta = ImporteField(label='Precio de venta (€)', required=False)

    # El input type="date" del navegador exige YYYY-MM-DD
    fecha_adquisicion = forms.DateField(
        label='Fecha de adquisición',
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'class': 'w-full px-3 py-2 border rounded-lg', 'type': 'date'},
        ),
        input_formats=['%Y-%m-%d', '%d/%m/%Y'],
    )

    # Campos cuya modificación obliga a rehacer el asiento de compra
    CAMPOS_ECONOMICOS = (
        'precio_subasta', 'tasas_sala', 'logistica_grua', 'tipo_iva', 'forma_pago',
        'fecha_adquisicion',
    )

    tipo_iva = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg input-monetario',
            'placeholder': '0',
            'inputmode': 'decimal',
        }),
    )

    class Meta:
        model = Vehiculo
        fields = [
            'matricula', 'bastidor', 'marca', 'modelo', 'anio',
            'combustible', 'kilometraje', 'tipo_dano', 'etiqueta_ambiental',
            'estado', 'fecha_adquisicion', 'plataforma_subasta',
            'precio_subasta', 'tasas_sala', 'logistica_grua',
            'proveedor', 'cif_nif', 'numero_factura', 'factura_compra_pdf',
            'tipo_iva', 'forma_pago',
            'precio_venta', 'descripcion_dano', 'imagen_principal',
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
            'precio_subasta': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg input-monetario',
                'placeholder': '0,00',
                'inputmode': 'decimal',
            }),
            'tasas_sala': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg input-monetario',
                'placeholder': '0,00',
                'inputmode': 'decimal',
            }),
            'logistica_grua': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg input-monetario',
                'placeholder': '0,00',
                'inputmode': 'decimal',
            }),
            'proveedor': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'BCA, Copart, ADESA...',
            }),
            'cif_nif': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'B12345678',
                'maxlength': '15',
            }),
            'numero_factura': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'placeholder': 'INV-2026-001',
            }),
            'factura_compra_pdf': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'accept': '.pdf',
            }),
            'tipo_iva': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg input-monetario',
                'placeholder': '0',
                'inputmode': 'decimal',
            }),
            'forma_pago': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'precio_venta': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg input-monetario',
                'placeholder': '0,00',
                'inputmode': 'decimal',
            }),
            'descripcion_dano': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'rows': '4',
                'placeholder': 'Descripción del estado del vehículo...',
            }),
            'imagen_principal': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'accept': 'image/*',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        datos = super().clean()
        # Solo se rellenan los que realmente están en el formulario: si la
        # compra está contabilizada se han quitado y no deben reaparecer en
        # cleaned_data (Django los buscaría luego en self.fields).
        for nombre in ('precio_subasta', 'tasas_sala', 'logistica_grua', 'precio_venta'):
            if nombre in self.fields and datos.get(nombre) is None:
                datos[nombre] = Decimal('0')
        return datos

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

    def clean_tipo_iva(self):
        val = (self.cleaned_data.get('tipo_iva') or '').strip()
        if not val:
            return Decimal('0')
        return parsear_importe(val)

    def clean_precio_venta(self):
        # Vacio -> 0 (el campo del modelo no admite NULL, tiene default=0)
        return self.cleaned_data.get('precio_venta') or Decimal('0')

    def clean_imagen_principal(self):
        """Reduce y optimiza la portada en la carpeta de la matrícula."""
        archivo = self.cleaned_data.get('imagen_principal')
        if not isinstance(archivo, UploadedFile):
            return archivo
        matricula = self.cleaned_data.get('matricula') or self.instance.matricula or ''
        etiqueta = (
            archivo.name.rsplit('.', 1)[0] if getattr(archivo, 'name', '') else 'portada'
        )
        try:
            return procesar_imagen(archivo, nombre_para(matricula, etiqueta))
        except ImagenInvalida as exc:
            raise forms.ValidationError(str(exc))


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


class ImagenVehiculoForm(forms.ModelForm):
    """Formulario de imagen adicional (el archivo es opcional por fila)."""

    class Meta:
        model = ImagenVehiculo
        fields = ['imagen', 'orden']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Las filas vacías (sin archivo) no bloquean el envío del formulario
        self.fields['imagen'].required = False

    def url_actual(self):
        """URL de la foto ya guardada (no la recién subida, que aún no tiene).

        La plantilla la usa para la miniatura: `instance.imagen` puede contener
        el archivo recién subido cuando el formulario se vuelve a mostrar por un
        error de validación, y en ese caso `.url` no existe.
        """
        nombre = (self.initial or {}).get('imagen') or ''
        if not nombre:
            return ''
        try:
            return self.instance.imagen.storage.url(nombre)
        except Exception:
            return ''

    def clean_imagen(self):
        """Reduce la foto y la guarda en la carpeta de la matrícula.

        Solo se procesa un archivo **recién subido**. Una imagen ya guardada
        (FieldFile) se deja como está: volver a leerla falla si el archivo ya no
        existe en disco (el disco de Render se borra en cada despliegue) y era
        la causa del 500 al marcar «Eliminar» en una foto antigua.
        """
        archivo = self.cleaned_data.get('imagen')
        if not isinstance(archivo, UploadedFile):
            return archivo
        # La matrícula se toma del POST (es la que se está guardando); si no
        # llegara, se usa la del vehículo ya cargado.
        matricula = (self.data.get('matricula') if self.data else '') or getattr(
            self.instance.vehiculo, 'matricula', ''
        )
        etiqueta = archivo.name.rsplit('.', 1)[0] if getattr(archivo, 'name', '') else 'foto'
        try:
            return procesar_imagen(archivo, nombre_para(matricula, etiqueta))
        except ImagenInvalida as exc:
            raise forms.ValidationError(str(exc))


class ImagenVehiculoBaseFormSet(BaseInlineFormSet):
    """Formset que descarta las filas sin archivo (imagen='')."""

    def clean(self):
        super().clean()
        # El formset recorta en silencio los formularios que superan max_num;
        # aquí se avisa al usuario en vez de perder fotos sin explicación.
        if self.data:
            try:
                enviadas = int(self.data.get(self.add_prefix('TOTAL_FORMS'), 0))
            except (TypeError, ValueError):
                enviadas = 0
            if enviadas > MAX_IMAGENES:
                raise ValidationError(
                    f'Ha seleccionado {enviadas} imágenes y el máximo es '
                    f'{MAX_IMAGENES}. Quite {enviadas - MAX_IMAGENES} o súbalas '
                    f'en una segunda edición del vehículo.'
                )

    def save(self, commit=True):
        objs = super().save(commit=commit)
        if commit:
            ImagenVehiculo.objects.filter(
                vehiculo=self.instance, imagen=''
            ).delete()
        return [o for o in objs if getattr(o, 'imagen', None)]


ImagenVehiculoFormSet = inlineformset_factory(
    Vehiculo, ImagenVehiculo,
    form=ImagenVehiculoForm,
    formset=ImagenVehiculoBaseFormSet,
    fields=['imagen', 'orden'],
    extra=1,
    max_num=MAX_IMAGENES,
    can_delete=True,
)


class VehiculoComercialForm(forms.ModelForm):
    """Publicación comercial del vehículo.

    Solo estado, precio de venta, descripción e imagen de portada. No incluye
    ningún dato de compra ni coste: así una edición comercial no puede alterar
    la contabilidad ya registrada ni expone márgenes al equipo de ventas.
    """

    precio_venta = ImporteField(label='Precio de venta (€)', required=False)

    class Meta:
        model = Vehiculo
        fields = ['estado', 'precio_venta', 'descripcion_dano', 'imagen_principal']
        widgets = {
            'estado': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
            }),
            'descripcion_dano': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg',
                'rows': '5',
                'placeholder': 'Descripción comercial: equipamiento, estado, extras...',
            }),
        }

    def clean_precio_venta(self):
        return self.cleaned_data.get('precio_venta') or Decimal('0')

    def clean_imagen_principal(self):
        """Reduce y optimiza la portada en la carpeta de la matrícula."""
        archivo = self.cleaned_data.get('imagen_principal')
        if not isinstance(archivo, UploadedFile):
            return archivo
        matricula = self.instance.matricula or ''
        etiqueta = (
            archivo.name.rsplit('.', 1)[0] if getattr(archivo, 'name', '') else 'portada'
        )
        try:
            return procesar_imagen(archivo, nombre_para(matricula, etiqueta))
        except ImagenInvalida as exc:
            raise forms.ValidationError(str(exc))
