import os

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import (
    Q, Sum, Count, F, Max, Min, ExpressionWrapper, DecimalField,
)
from django.db import transaction
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.forms import formset_factory
from django.http import Http404
from datetime import date
from decimal import Decimal
from uuid import uuid4
from .models import (
    Material, MaterialUsado, OrdenTrabajo, CompraMaterial,
    _anular_asiento_pago_compra, nuevo_grupo_factura,
)
from .forms import (
    MaterialForm, CompraFacturaForm, CompraMaterialLineaForm,
    CompraMaterialLineaFormSet, UNIDADES_SUGERIDAS,
)
from apps.accounting.models import AsientoContable, CuentaContable
from apps.bank.models import BancoCuenta
from apps.bank.services import obtener_cuenta_banco_default
from apps.core.formatting import format_euros


def _contexto_compra(header_form, linea_formset):
    """Contexto de la pantalla de compras.

    Incluye la lista de materiales (para el autocompletado del campo Material)
    y las unidades habituales más las ya usadas en el inventario.
    """
    unidades = {m.unidad for m in Material.objects.exclude(unidad='')}
    unidades.update(UNIDADES_SUGERIDAS)
    return {
        'header_form': header_form,
        'linea_formset': linea_formset,
        'materiales': Material.objects.all().order_by('nombre'),
        'unidades': sorted(unidades),
    }


def _mensaje_falta_cuenta(codigo):
    return (
        f'Falta la cuenta contable {codigo} en el plan contable. '
        f'El plan se crea solo al desplegar; si falta, ejecute '
        f'"python manage.py migrate".'
    )


def _lineas_validas(formset):
    """Formularios de línea con datos y no marcados para borrar."""
    return [
        form for form in formset
        if form.cleaned_data and not form.cleaned_data.get('DELETE')
    ]


def _resolver_forma_pago(header_form):
    """Devuelve (cuenta_contrapartida, cuenta_pago, pagar_ahora, error)."""
    datos = header_form.cleaned_data
    forma_pago_code = datos.get('forma_pago') or ''
    pagado = datos.get('pagado', False)
    cuenta_pago_code = datos.get('cuenta_pago') or ''

    forma_pago_cuenta = None
    if forma_pago_code:
        forma_pago_cuenta = CuentaContable.objects.filter(codigo=forma_pago_code).first()
        if forma_pago_cuenta is None:
            return None, None, False, _mensaje_falta_cuenta(forma_pago_code)

    # "Pagar ahora" solo aplica al crédito (410); en contado el pago ya está
    # registrado en el asiento de compra.
    pagar_ahora = pagado and (not forma_pago_code or forma_pago_code == '410')
    cuenta_pago = None
    if pagar_ahora and cuenta_pago_code:
        cuenta_pago = CuentaContable.objects.filter(codigo=cuenta_pago_code).first()
        if cuenta_pago is None:
            return None, None, False, _mensaje_falta_cuenta(cuenta_pago_code)

    return forma_pago_cuenta, cuenta_pago, pagar_ahora, None


def _error_saldo_banco(formset, tipo_iva, forma_pago_code, pagar_ahora, cuenta_pago_code, fecha=None):
    """Valida el saldo del banco antes de pagar al contado. Devuelve texto o None."""
    paga_con_banco = pagar_ahora and (not cuenta_pago_code or cuenta_pago_code == '572')
    if forma_pago_code != '572' and not paga_con_banco:
        return None

    total = Decimal('0')
    for linea in _lineas_validas(formset):
        cantidad = linea.cleaned_data.get('cantidad')
        precio = linea.cleaned_data.get('precio_unitario')
        if cantidad is None or precio is None:
            continue
        total += cantidad * precio * (
            Decimal('1') + Decimal(tipo_iva) / Decimal('100')
        )

    banco_cuenta = BancoCuenta.objects.filter(cuenta_contable__codigo='572').first()
    if not banco_cuenta:
        banco_cuenta = obtener_cuenta_banco_default()
    if not banco_cuenta:
        return None

    from django.core.exceptions import ValidationError
    from apps.bank.services import validar_saldo_egreso

    try:
        # El saldo se mira a la fecha del pago, no al saldo de hoy: no se puede
        # pagar con dinero que todavía no había entrado en la cuenta.
        validar_saldo_egreso(banco_cuenta, fecha, total)
    except ValidationError as error:
        return error.messages[0]
    return None


def _nombre_pdf_sin_colision(pdf_file, nombres_antiguos):
    """Evita reutilizar el nombre de un PDF que se va a borrar.

    `django-cleanup` borra los archivos de las líneas eliminadas al confirmar
    la transacción. Si el PDF nuevo se guardara con el mismo nombre (caso
    típico: el operador vuelve a subir el mismo archivo), esa limpieza
    borraría también el recién subido y la factura quedaría sin adjunto. Por
    eso se renombra cuando choca con un nombre que está pendiente de borrar.
    """
    nombre = os.path.basename(getattr(pdf_file, 'name', '') or '')
    if nombre and nombre in nombres_antiguos:
        base, extension = os.path.splitext(nombre)
        pdf_file.name = f'{base}_corregida_{uuid4().hex[:6]}{extension}'
    return pdf_file


def _crear_lineas_factura(header_form, formset, grupo, forma_pago_cuenta,
                          pagar_ahora, fecha_pago, cuenta_pago, pdf_file, user):
    """Crea las líneas de la factura con sus asientos y pagos.

    Debe llamarse dentro de una transacción: si algo falla, el llamador
    revierte todo (stock, asientos y movimientos bancarios).
    """
    datos = header_form.cleaned_data
    lineas_creadas = asientos_ok = pagos_ok = 0

    for linea_form in _lineas_validas(formset):
        # Material existente o nuevo: se resuelve (y crea si hace falta) dentro
        # de la transacción, para no dejar materiales sueltos si algo falla.
        material = linea_form.resolver_material()
        cantidad = linea_form.cleaned_data.get('cantidad')
        precio_unitario = linea_form.cleaned_data.get('precio_unitario')
        if not material or cantidad is None or precio_unitario is None:
            continue

        compra = CompraMaterial(
            material=material,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            proveedor=datos['proveedor'],
            cif_nif=datos['cif_nif'],
            fecha_compra=datos['fecha_compra'],
            fecha_vencimiento=datos.get('fecha_vencimiento'),
            numero_factura=datos.get('numero_factura', ''),
            factura_grupo=grupo,
            tipo_inventario=datos['tipo_inventario'],
            tipo_iva=datos['tipo_iva'],
            forma_pago=forma_pago_cuenta,
            created_by=user,
        )
        if lineas_creadas == 0 and pdf_file:
            compra.documento_pdf = pdf_file
        compra.save()
        lineas_creadas += 1

        asiento = compra.crear_asiento_contable()
        if asiento.esta_cuadrado:
            asiento.estado = 'POSTEADO'
            asiento.save()
            asientos_ok += 1

        if pagar_ahora:
            compra.pagado = True
            compra.fecha_pago = fecha_pago
            compra.cuenta_pago = cuenta_pago
            compra.crear_asiento_pago()
            compra.save(update_fields=['pagado', 'fecha_pago', 'cuenta_pago'])
            pagos_ok += 1

    return lineas_creadas, asientos_ok, pagos_ok


@login_required
def material_list(request):
    """Lista de materiales con gestión de stock."""
    materiales = Material.objects.all()
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    alerta = request.GET.get('alerta', '')
    
    if busqueda:
        materiales = materiales.filter(
            Q(nombre__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )
    
    if alerta == '1':
        materiales = materiales.filter(alerta_stock=True)
    
    # Estadísticas
    valor_total_expr = ExpressionWrapper(
        F('stock_actual') * F('precio_unitario'),
        output_field=DecimalField()
    )
    stats = {
        'total': Material.objects.count(),
        'con_alerta': Material.objects.filter(alerta_stock=True).count(),
        'valor_total': Material.objects.aggregate(
            total=Sum(valor_total_expr)
        )['total'] or 0,
    }
    
    # Materiales con alerta para el panel
    materiales_con_alerta = Material.objects.filter(alerta_stock=True)[:5]
    
    context = {
        'materiales': materiales,
        'stats': stats,
        'materiales_con_alerta': materiales_con_alerta,
        'busqueda': busqueda,
        'mostrar_alertas': alerta == '1',
    }
    return render(request, 'workshop/material_list.html', context)


@login_required
def material_detail(request, pk):
    """Detalle de un material con historial de uso."""
    material = get_object_or_404(Material, pk=pk)
    
    # Historial de uso del material
    usos = MaterialUsado.objects.filter(
        material=material
    ).select_related(
        'orden_trabajo', 'orden_trabajo__vehiculo', 'orden_trabajo__operario'
    ).order_by('-orden_trabajo__created_at')[:20]
    
    # Estadísticas de uso
    stats = {
        'total_usado': usos.aggregate(total=Sum('cantidad'))['total'] or 0,
        'veces_usado': usos.count(),
        'valor_stock': material.stock_actual * material.precio_unitario,
    }

    compras = material.compras.select_related('asiento_contable').all()
    
    context = {
        'material': material,
        'usos': usos,
        'stats': stats,
        'compras': compras,
    }
    return render(request, 'workshop/material_detail.html', context)


@login_required
def material_create(request):
    """Crear nuevo material."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para crear materiales.')
        return redirect('workshop:material_list')
    
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            material = form.save()
            messages.success(
                request, 
                f'Material "{material.nombre}" creado correctamente.'
            )
            if 'guardar_otro' in request.POST:
                messages.info(request, 'Puede crear el siguiente material.')
                return redirect('workshop:material_create')
            return redirect('workshop:material_detail', pk=material.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = MaterialForm()
    
    context = {
        'form': form,
        'action': 'crear',
    }
    return render(request, 'workshop/material_form.html', context)


@login_required
def compra_material_create(request):
    """Registrar compra de material(es) en una misma factura (cabecera + líneas)."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para registrar compras de material.')
        return redirect('workshop:material_list')

    if request.method == 'POST':
        header_form = CompraFacturaForm(request.POST, request.FILES)
        linea_formset = CompraMaterialLineaFormSet(request.POST, prefix='lineas')

        if header_form.is_valid() and linea_formset.is_valid():
            pdf_file = header_form.cleaned_data.get('documento_pdf')
            fecha_pago = header_form.cleaned_data.get('fecha_pago') or None
            forma_pago_code = header_form.cleaned_data.get('forma_pago') or ''
            cuenta_pago_code = header_form.cleaned_data.get('cuenta_pago') or ''

            forma_pago_cuenta, cuenta_pago, pagar_ahora, error_cuenta = (
                _resolver_forma_pago(header_form)
            )
            if error_cuenta:
                messages.error(request, error_cuenta)
                return render(
                    request,
                    'workshop/material_compra_form.html',
                    _contexto_compra(header_form, linea_formset),
                )

            # Validar saldo disponible ANTES de crear nada (evita errores a
            # mitad de la transacción si el banco no cubre el total a pagar).
            error_saldo = _error_saldo_banco(
                linea_formset, header_form.cleaned_data['tipo_iva'],
                forma_pago_code, pagar_ahora, cuenta_pago_code,
                fecha=header_form.cleaned_data.get('fecha_pago')
                or header_form.cleaned_data.get('fecha_compra'),
            )
            if error_saldo:
                messages.error(request, error_saldo)
                return render(
                    request,
                    'workshop/material_compra_form.html',
                    _contexto_compra(header_form, linea_formset),
                )

            grupo = nuevo_grupo_factura()
            try:
                with transaction.atomic():
                    lineas_creadas, asientos_ok, pagos_ok = _crear_lineas_factura(
                        header_form, linea_formset, grupo, forma_pago_cuenta,
                        pagar_ahora, fecha_pago, cuenta_pago, pdf_file, request.user,
                    )
            except Exception as error:
                # Toda la factura es una transacción: si una línea falla se
                # revierten el stock, los asientos y los movimientos bancarios.
                messages.error(
                    request,
                    f'Error al registrar la factura: {error}. '
                    f'No se guardó ninguna línea.'
                )
                return render(
                    request,
                    'workshop/material_compra_form.html',
                    _contexto_compra(header_form, linea_formset),
                )

            descripcion_pago = {
                '': 'Crédito (pendiente en 410)',
                '572': 'Contado banco (EGRESO registrado)',
                '570': 'Contado caja',
            }.get(forma_pago_code, 'Crédito (pendiente en 410)')
            if pagar_ahora:
                descripcion_pago = (
                    'Crédito pagado (asiento de pago DEBE 410 / HABER tesorería'
                    ' generado por línea)'
                )
            if header_form.cleaned_data.get('pagado') and not pagar_ahora:
                descripcion_pago += ' — el checkbox "Pagar ahora" no aplica al contado'
            messages.success(
                request,
                f'Factura registrada: {lineas_creadas} material(es) comprado(s), '
                f'{asientos_ok} asiento(s) posteado(s)'
                f'{" y " + str(pagos_ok) + " pago(s) registrado(s)" if pagos_ok else ""}. '
                f'{descripcion_pago}.'
            )

            # "Guardar y registrar otra": vuelve al formulario vacío para cargar
            # la siguiente factura sin pasar por el menú.
            if request.POST.get('guardar_y_otra'):
                messages.info(
                    request,
                    'Puede cargar la siguiente factura. La anterior queda en '
                    'Compras → Historial.',
                )
                return redirect('workshop:compra_material_create')

            return redirect('workshop:compra_detail', grupo=grupo)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        header_form = CompraFacturaForm()
        linea_formset = CompraMaterialLineaFormSet(prefix='lineas')

    context = _contexto_compra(header_form, linea_formset)
    return render(request, 'workshop/material_compra_form.html', context)


@login_required
def compra_list(request):
    """Historial de facturas de compra (agrupadas por factura)."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para ver las compras.')
        return redirect('workshop:material_list')

    busqueda = request.GET.get('busqueda', '').strip()
    filas = CompraMaterial.objects.all()
    if busqueda:
        filas = filas.filter(
            Q(proveedor__icontains=busqueda)
            | Q(numero_factura__icontains=busqueda)
            | Q(cif_nif__icontains=busqueda)
        )

    grupos = (
        filas.values('factura_grupo')
        .annotate(
            proveedor=Max('proveedor'),
            cif_nif=Max('cif_nif'),
            numero_factura=Max('numero_factura'),
            fecha_compra=Max('fecha_compra'),
            vencimiento=Max('fecha_vencimiento'),
            lineas=Count('id'),
            base=Sum('base_imponible'),
            cuota=Sum('cuota_iva'),
            forma_pago=Max('forma_pago__codigo'),
            pagadas=Count('id', filter=Q(pagado=True)),
            primera=Min('pk'),
        )
        .order_by('-fecha_compra', '-primera')
    )

    facturas = []
    hoy = date.today()
    for grupo in grupos:
        grupo['total'] = (grupo['base'] or Decimal('0')) + (grupo['cuota'] or Decimal('0'))
        grupo['pagada'] = grupo['pagadas'] == grupo['lineas']
        grupo['vencida'] = bool(
            grupo['vencimiento']
            and grupo['vencimiento'] < hoy
            and not grupo['pagada']
        )
        grupo['dias_para_vencer'] = (
            (grupo['vencimiento'] - hoy).days if grupo['vencimiento'] else None
        )
        facturas.append(grupo)

    return render(request, 'workshop/compra_list.html', {
        'facturas': facturas,
        'busqueda': busqueda,
        'vencidas': sum(1 for factura in facturas if factura['vencida']),
    })


def _lineas_de_factura(grupo):
    """Líneas de una factura, ordenadas."""
    return list(
        CompraMaterial.objects.filter(factura_grupo=grupo)
        .select_related('material', 'forma_pago', 'cuenta_pago', 'asiento_contable')
        .order_by('pk')
    )


@login_required
def compra_detail(request, grupo):
    """Hoja resumen de una factura de compra: datos, líneas y asientos."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para ver las compras.')
        return redirect('workshop:material_list')

    lineas = _lineas_de_factura(grupo)
    if not lineas:
        raise Http404('Factura de compra no encontrada')

    cabecera = lineas[0]
    total_base = sum((linea.base_imponible for linea in lineas), Decimal('0'))
    total_iva = sum((linea.cuota_iva for linea in lineas), Decimal('0'))

    asientos = []
    for linea in lineas:
        if linea.asiento_contable:
            asientos.append(linea.asiento_contable)
        asientos.extend(
            AsientoContable.objects.filter(
                tipo_documento='PagoCompraMaterial', documento_id=linea.pk,
            ).exclude(estado='ANULADO')
        )

    pagada = all(linea.pagado for linea in lineas)
    hoy = date.today()
    vencida = bool(
        cabecera.fecha_vencimiento
        and cabecera.fecha_vencimiento < hoy
        and not pagada
    )

    # Puede haber referencia en BD a un PDF que ya no existe (disco efímero):
    # en ese caso no se muestra el enlace, sino un aviso.
    pdf_disponible = False
    if cabecera.documento_pdf:
        try:
            pdf_disponible = default_storage.exists(cabecera.documento_pdf.name)
        except Exception:
            pdf_disponible = False

    return render(request, 'workshop/compra_detail.html', {
        'lineas': lineas,
        'cabecera': cabecera,
        'grupo': grupo,
        'total_base': total_base,
        'total_iva': total_iva,
        'total_factura': total_base + total_iva,
        'asientos': asientos,
        'pagada': pagada,
        'vencida': vencida,
        'hoy': hoy,
        'pdf_disponible': pdf_disponible,
    })


@login_required
def compra_edit(request, grupo):
    """Corrige una factura de compra.

    Revierte (stock, asientos y movimientos bancarios) y vuelve a registrar la
    factura con los datos corregidos, conservando el mismo grupo: así el
    historial y los informes muestran la factura buena y la traza de la
    anulación.
    """
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para editar compras.')
        return redirect('workshop:material_list')

    lineas = _lineas_de_factura(grupo)
    if not lineas:
        raise Http404('Factura de compra no encontrada')
    cabecera = lineas[0]

    LineaFormSet = formset_factory(
        CompraMaterialLineaForm, extra=len(lineas), can_delete=True,
        min_num=1, validate_min=True,
    )

    if request.method == 'POST':
        header_form = CompraFacturaForm(request.POST, request.FILES)
        linea_formset = LineaFormSet(request.POST, prefix='lineas')

        if header_form.is_valid() and linea_formset.is_valid():
            fecha_pago = header_form.cleaned_data.get('fecha_pago') or None
            forma_pago_code = header_form.cleaned_data.get('forma_pago') or ''
            cuenta_pago_code = header_form.cleaned_data.get('cuenta_pago') or ''

            forma_pago_cuenta, cuenta_pago, pagar_ahora, error_cuenta = (
                _resolver_forma_pago(header_form)
            )
            error_saldo = None
            if not error_cuenta:
                error_saldo = _error_saldo_banco(
                    linea_formset, header_form.cleaned_data['tipo_iva'],
                    forma_pago_code, pagar_ahora, cuenta_pago_code,
                )

            if error_cuenta or error_saldo:
                messages.error(request, error_cuenta or error_saldo)
            else:
                try:
                    with transaction.atomic():
                        pdf_nuevo = header_form.cleaned_data.get('documento_pdf')
                        pdf_contenido = None
                        pdf_nombre = None
                        pdf_perdido = False

                        # Si el usuario ya sube un PDF nuevo no se toca el
                        # anterior: se usa el nuevo directamente.
                        if not pdf_nuevo:
                            for linea in lineas:
                                if not linea.documento_pdf:
                                    continue
                                try:
                                    with linea.documento_pdf.open('rb') as archivo:
                                        pdf_contenido = archivo.read()
                                    pdf_nombre = os.path.basename(linea.documento_pdf.name)
                                except (FileNotFoundError, OSError):
                                    # El disco de Render se borra en cada
                                    # despliegue: la corrección sigue sin adjunto.
                                    pdf_contenido = None
                                    pdf_nombre = None
                                    pdf_perdido = True
                                break

                        # Nombres que django-cleanup borrará al confirmar.
                        nombres_antiguos = {
                            os.path.basename(linea.documento_pdf.name)
                            for linea in lineas
                            if linea.documento_pdf
                        }

                        for linea in lineas:
                            linea.revertir(request.user)
                            linea.delete()

                        pdf_file = pdf_nuevo
                        if not pdf_file and pdf_contenido:
                            pdf_file = ContentFile(pdf_contenido, name=pdf_nombre)
                        if pdf_file:
                            pdf_file = _nombre_pdf_sin_colision(
                                pdf_file, nombres_antiguos
                            )

                        _crear_lineas_factura(
                            header_form, linea_formset, grupo, forma_pago_cuenta,
                            pagar_ahora, fecha_pago, cuenta_pago, pdf_file,
                            request.user,
                        )
                except Exception as error:
                    messages.error(
                        request,
                        f'No se pudo corregir la factura: {error}. '
                        f'No se cambió nada.'
                    )
                else:
                    messages.success(
                        request,
                        'Factura corregida. Los asientos anteriores quedaron '
                        'anulados con su contrapartida y se registraron los nuevos.'
                    )
                    if pdf_perdido:
                        messages.warning(
                            request,
                            'El PDF de la factura ya no estaba en el servidor '
                            '(se perdió en un despliegue), así que se guardó sin '
                            'adjunto. Puede volver a subirlo con «Editar».'
                        )
                    return redirect('workshop:compra_detail', grupo=grupo)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        header_form = CompraFacturaForm(initial={
            'proveedor': cabecera.proveedor,
            'cif_nif': cabecera.cif_nif,
            'fecha_compra': cabecera.fecha_compra,
            'fecha_vencimiento': cabecera.fecha_vencimiento,
            'numero_factura': cabecera.numero_factura,
            'tipo_inventario': cabecera.tipo_inventario,
            'tipo_iva': cabecera.tipo_iva,
            'forma_pago': cabecera.forma_pago.codigo if cabecera.forma_pago else '',
            'cuenta_pago': cabecera.cuenta_pago.codigo if cabecera.cuenta_pago else '',
        })
        linea_formset = LineaFormSet(prefix='lineas', initial=[
            {
                'material': linea.material.nombre,
                'unidad': linea.material.unidad,
                'cantidad': linea.cantidad,
                'precio_unitario': linea.precio_unitario,
            }
            for linea in lineas
        ])

    contexto = _contexto_compra(header_form, linea_formset)
    contexto.update({
        'modo_edicion': True,
        'grupo': grupo,
        'cabecera': cabecera,
    })
    return render(request, 'workshop/material_compra_form.html', contexto)


@login_required
def compra_pagar(request, pk):
    """Marcar como pagada una compra de material a crédito (asiento + EGRESO)."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para pagar compras.')
        return redirect('workshop:material_list')

    compra = get_object_or_404(CompraMaterial, pk=pk)

    if request.method != 'POST':
        return redirect('workshop:material_detail', pk=compra.material.pk)

    if not compra.es_credito:
        messages.error(
            request,
            'La compra se registró al contado: su pago ya quedó reflejado '
            'en el asiento de compra.'
        )
        return redirect('workshop:material_detail', pk=compra.material.pk)

    if compra.pagado:
        messages.info(request, 'La compra ya está marcada como pagada.')
        return redirect('workshop:material_detail', pk=compra.material.pk)

    fecha_pago = request.POST.get('fecha_pago') or None
    if fecha_pago:
        try:
            fecha_pago = date.fromisoformat(fecha_pago)
        except ValueError:
            fecha_pago = None
    cuenta_pago_code = request.POST.get('cuenta_pago') or ''
    cuenta_pago = None
    if cuenta_pago_code in ('570', '572'):
        cuenta_pago = CuentaContable.objects.filter(
            codigo=cuenta_pago_code
        ).first()
        if not cuenta_pago:
            messages.error(
                request,
                f'Falta la cuenta contable {cuenta_pago_code} en el plan '
                f'contable. El plan se crea solo al desplegar; si falta, ejecute '
                f'"python manage.py migrate".'
            )
            return redirect('workshop:material_detail', pk=compra.material.pk)

    compra.pagado = True
    compra.fecha_pago = fecha_pago
    compra.cuenta_pago = cuenta_pago
    compra.save(update_fields=['pagado', 'fecha_pago', 'cuenta_pago'])

    try:
        pago = compra.crear_asiento_pago()
        codigo = pago.movimientos.filter(haber__gt=0).first()
        codigo_pago = codigo.cuenta.codigo if codigo else 'tesorería'
        messages.success(
            request,
            f'Compra pagada. Asiento de pago #{pago.numero} '
            f'(DEBE 410 / HABER {codigo_pago}) generado automáticamente.'
        )
    except Exception as e:
        messages.error(
            request,
            f'No se pudo generar el asiento de pago: {e}'
        )
        return redirect('workshop:material_detail', pk=compra.material.pk)

    return redirect('workshop:material_detail', pk=compra.material.pk)


@login_required
def compra_deshacer_pago(request, pk):
    """Desmarcar el pago de una compra (anula el asiento y elimina el EGRESO)."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para modificar compras.')
        return redirect('workshop:material_list')

    compra = get_object_or_404(CompraMaterial, pk=pk)

    if request.method != 'POST':
        return redirect('workshop:material_detail', pk=compra.material.pk)

    if not compra.pagado:
        messages.info(request, 'La compra no está marcada como pagada.')
        return redirect('workshop:material_detail', pk=compra.material.pk)

    with transaction.atomic():
        _anular_asiento_pago_compra(compra, request.user)
        compra.pagado = False
        compra.fecha_pago = None
        compra.cuenta_pago = None
        compra.save(update_fields=['pagado', 'fecha_pago', 'cuenta_pago'])

    messages.success(
        request,
        'Pago deshecho: asiento de pago anulado (Ley Antifraude) y EGRESO '
        'bancario eliminado. La compra vuelve a quedar pendiente en 410.'
    )
    return redirect('workshop:material_detail', pk=compra.material.pk)


@login_required
def material_update(request, pk):
    """Actualizar un material."""
    material = get_object_or_404(Material, pk=pk)
    
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para editar materiales.')
        return redirect('workshop:material_detail', pk=pk)
    
    if request.method == 'POST':
        form = MaterialForm(request.POST, instance=material)
        if form.is_valid():
            material = form.save()
            messages.success(
                request, 
                f'Material "{material.nombre}" actualizado correctamente.'
            )
            return redirect('workshop:material_detail', pk=material.pk)
        else:
            messages.error(request, 'Por favor, corrija los errores del formulario.')
    else:
        form = MaterialForm(instance=material)
    
    context = {
        'form': form,
        'material': material,
        'action': 'editar',
    }
    return render(request, 'workshop/material_form.html', context)


@login_required
def material_delete(request, pk):
    """Eliminar un material (confirmación)."""
    material = get_object_or_404(Material, pk=pk)
    
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para eliminar materiales.')
        return redirect('workshop:material_detail', pk=pk)
    
    if not request.user.puede_eliminar:
        messages.error(request, 'No tiene permisos para eliminar registros.')
        return redirect('workshop:material_detail', pk=pk)
    
    if request.method == 'POST':
        nombre = material.nombre
        material.delete()
        messages.success(
            request, 
            f'Material "{nombre}" eliminado correctamente.'
        )
        return redirect('workshop:material_list')
    
    context = {
        'material': material,
    }
    return render(request, 'workshop/material_delete.html', context)


@login_required
def alertas_stock(request):
    """Panel de alertas de stock bajo."""
    materiales_con_alerta = Material.objects.filter(alerta_stock=True).order_by('stock_actual')
    
    # Calcular déficit y coste de reposición para cada material
    materiales_con_datos = []
    total_reposicion = 0
    
    for material in materiales_con_alerta:
        deficit = material.stock_minimo - material.stock_actual
        coste_reposicion = deficit * material.precio_unitario
        material.deficit = deficit
        material.coste_reposicion = coste_reposicion
        total_reposicion += coste_reposicion
        materiales_con_datos.append(material)
    
    context = {
        'materiales': materiales_con_datos,
        'total_alertas': materiales_con_alerta.count(),
        'total_reposicion': total_reposicion,
    }
    return render(request, 'workshop/alertas_stock.html', context)
