"""
Exportación fiscal: BOE Modelo 390, CSV Pre-303, SII XML.
Formatos oficiales de la Agencia Tributaria española.
"""
from datetime import date
from decimal import Decimal
import csv
import io


def generar_modelo_390(anio):
    """
    Genera el fichero plano del Modelo 390 (Declaración Informativa).
    Formato BOE: cada registro es una línea de texto con campos fijos.
    
    https://sede.agenciatributaria.gob.es/Sede/procedimientos/ia/390.shtml
    
    Registro Tipo 0: Cabecera
    Registro Tipo 1: Datos del declarante
    Registro Tipo 2: Datos de la liquidación
    Registro Tipo 3: Operaciones intracomunitarias
    Registro Tipo 9: Registro final
    """
    from apps.accounting.reports import calcular_libro_iva
    
    desde = date(anio, 1, 1)
    hasta = date(anio, 12, 31)
    libro = calcular_libro_iva(desde, hasta)
    
    lineas = []
    
    # Registro Tipo 0 - Cabecera
    # NIF, Nombre, Año, Tipo (390)
    cabecera = (
        f"{'0':>2}"           # Tipo registro
        f"{'B26729731':>9}"   # NIF
        f"{'RCAR ROGIL':<40}"  # Nombre (40 chars)
        f"{anio:>4}"          # Año
        f"{'390':>3}"         # Modelo
        f"{' ':>12}"          # Reservado
    )
    lineas.append(cabecera)
    
    # Registro Tipo 1 - Datos del declarante
    base_repercutido = libro['iva_repercutido']['base_imponible']
    cuota_repercutido = libro['iva_repercutido']['total']
    base_soportado = libro['iva_soportado']['base_imponible']
    cuota_soportado = libro['iva_soportado']['total']
    
    registro_1 = (
        f"{'1':>2}"                              # Tipo registro
        f"{'B26729731':>9}"                       # NIF
        f"{str(int(base_repercutido * 100)).rjust(14)}"  # Base IVA repercutido
        f"{str(int(cuota_repercutido * 100)).rjust(14)}" # Cuota IVA repercutido
        f"{str(int(base_soportado * 100)).rjust(14)}"    # Base IVA soportado
        f"{str(int(cuota_soportado * 100)).rjust(14)}"   # Cuota IVA soportado
        f"{' ':>2}"                              # Reservado
    )
    lineas.append(registro_1)
    
    # Registro Tipo 2 - Liquidación por trimestre
    from apps.accounting.reports import calcular_trimestre
    
    for t in range(1, 5):
        desde_t, hasta_t = calcular_trimestre(t, anio)
        libro_t = calcular_libro_iva(desde_t, hasta_t)
        
        base_t = libro_t['iva_repercutido']['base_imponible']
        cuota_t = libro_t['iva_repercutido']['total']
        base_s = libro_t['iva_soportado']['base_imponible']
        cuota_s = libro_t['iva_soportado']['total']
        liquidar = libro_t['cuota_liquidar']
        
        registro_2 = (
            f"{'2':>2}"                              # Tipo registro
            f"{'B26729731':>9}"                       # NIF
            f"{t:>1}"                                 # Trimestre
            f"{str(int(base_t * 100)).rjust(14)}"     # Base repercutido trimestral
            f"{str(int(cuota_t * 100)).rjust(14)}"    # Cuota repercutido trimestral
            f"{str(int(base_s * 100)).rjust(14)}"     # Base soportado trimestral
            f"{str(int(cuota_s * 100)).rjust(14)}"    # Cuota soportado trimestral
            f"{str(int(liquidar * 100)).rjust(14)}"   # Cuota a liquidar
            f"{' ':>2}"                               # Reservado
        )
        lineas.append(registro_2)
    
    # Registro Tipo 9 - Final
    registro_9 = (
        f"{'9':>2}"                              # Tipo registro
        f"{'B26729731':>9}"                       # NIF
        f"{str(len(lineas) + 1).rjust(6)}"        # Total registros
        f"{' ':>49}"                             # Reservado
    )
    lineas.append(registro_9)
    
    return '\n'.join(lineas)


def generar_csv_pre303(anio, trimestre):
    """
    Genera CSV para la pre-declaración del Modelo 303.
    Formato compatible con el portal de Hacienda (clave de operación 05).
    
    https://sede.agenciatributaria.gob.es/Sede/procedimientos/ia/303.shtml
    """
    from apps.accounting.reports import calcular_libro_iva, calcular_trimestre
    
    desde, hasta = calcular_trimestre(trimestre, anio)
    libro = calcular_libro_iva(desde, hasta)
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    
    # Cabecera CSV
    writer.writerow([
        'NIF', 'Nombre', 'Modelo', 'Periodo', 'Año',
        'Clave Operación',
        'Base Imponible 21%', 'Cuota 21%',
        'Base Imponible 10%', 'Cuota 10%',
        'Base Imponible 4%', 'Cuota 4%',
        'Total Base Imponible', 'Total Cuota',
        'Cuota a Deducir', 'Resultado Liquidación'
    ])
    
    # Datos (simplificado: solo 21% IVA general)
    base_21 = libro['iva_repercutido']['base_imponible']
    cuota_21 = libro['iva_repercutido']['total']
    
    writer.writerow([
        'B26729731',
        'RCAR ROGIL',
        '303',
        f'T{trimestre}',
        anio,
        '05',  # Clave operación: Liquidación corriente
        f'{base_21:.2f}',
        f'{cuota_21:.2f}',
        '0.00', '0.00',
        '0.00', '0.00',
        f'{base_21:.2f}',
        f'{cuota_21:.2f}',
        f'{libro["iva_soportado"]["total"]:.2f}',
        f'{libro["cuota_liquidar"]:.2f}',
    ])
    
    return output.getvalue()


def generar_sii_xml(anio, trimestre):
    """
    Genera XML para el Suministro Inmediato de Información (SII).
    Formato: Lote de facturas emitidas (RegistroLRFacturasEmitidas)
    
    https://sede.agenciatributaria.gob.es/Sede/procedimientos/ia/suministro-inmediato-informacion-sii.shtml
    
    Estructura simplificada para una empresa con pocas operaciones REBU.
    """
    from apps.accounting.reports import calcular_trimestre
    from apps.sales.models import FacturaVenta
    from decimal import Decimal
    from lxml import etree
    
    desde, hasta = calcular_trimestre(trimestre, anio)
    
    # NS de SII
    nsmap = {
        'sum': 'https://sede.agenciatributaria.gob.es/Sede/procedimientos/ia/suministroInmediatoInformacion/siiLocVentas/1.0',
    }
    
    # Elemento raí
    lote = etree.Element('SuministroLRFacturasEmitidas', nsmap=nsmap)
    
    # Cabecera
    cabecera = etree.SubElement(lote, 'Cabecera')
    etree.SubElement(cabecera, 'IdeSujetoObligado').text = 'B26729731'
    etree.SubElement(cabecera, 'NumSerieFacturaEmisor').text = 'RCSII'
    etree.SubElement(cabecera, 'NombreRazon').text = 'R CAR ROGIL'
    etree.SubElement(cabecera, 'PeriodoImpositivo').text = f'{anio}T{trimestre}'
    
    # Facturas emitidas del trimestre
    facturas = FacturaVenta.objects.filter(
        fecha_operacion__gte=desde,
        fecha_operacion__lte=hasta,
        tipo_factura__in=['F1', 'F2']
    )
    
    for factura in facturas:
        registro = etree.SubElement(lote, 'RegistroLRFacturasEmitidas')
        
        # Encabezado
        enc = etree.SubElement(registro, 'Encabezamiento')
        
        ident = etree.SubElement(enc, 'IDFactura')
        etree.SubElement(ident, 'IDEmisorFactura').text = 'B26729731'
        etree.SubElement(ident, 'NumSerieFacturaEmisor').text = factura.codigo_factura
        etree.SubElement(ident, 'FechaExpedicionFacturaEmisor').text = factura.fecha_operacion.strftime('%d-%m-%Y')
        
        # Datos factura
        datos = etree.SubElement(enc, 'DatosFacturaEmitida')
        datos.set('TipoFactura', factura.tipo_factura)
        
        if factura.tipo_cliente == 'EMPRESA':
            datos.set('ClaveRegimenEspecialOTrascendencia', '01')
        else:
            datos.set('ClaveRegimenEspecialOTrascendencia', '01')
        
        etree.SubElement(datos, 'ImporteTotal').text = str(factura.precio_venta_total)
        etree.SubElement(datos, 'BaseImponible').text = str(factura.base_imponible_rebu)
        etree.SubElement(datos, 'CuotaRepercutida').text = str(factura.iva_repercutido)
        etree.SubElement(datos, 'TipoImpositivo').text = '21.00'
        
        # Contraparte
        contraparte = etree.SubElement(registro, 'Contraparte')
        etree.SubElement(contraparte, 'NombreRazon').text = factura.cliente_nombre
        etree.SubElement(contraparte, 'NIF').text = factura.cliente_nif
    
    xml_string = etree.tostring(lote, pretty_print=True, xml_declaration=True, encoding='UTF-8')
    
    return xml_string.decode('UTF-8')
