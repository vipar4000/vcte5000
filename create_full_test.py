#!/usr/bin/env python
"""
Script completo de datos de prueba para el ERP R Car Rogil.
Crea 6 vehiculos, 8 materiales, OTs, ventas, garantias, asistencia,
contabilidad y gastos cubriendo todos los escenarios posibles.

Uso: python create_full_test.py
"""
import os
import sys
import django
from datetime import datetime, timedelta, date
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.environ.get('DJANGO_SETTINGS_MODULE', 'config.settings.development'))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
django.setup()

from apps.accounts.models import User
from apps.vehicles.models import Vehiculo, ImagenVehiculo
from apps.workshop.models import OrdenTrabajo, Material, MaterialUsado, CompraMaterial
from apps.sales.models import VentaVehiculo
from apps.warranty.models import GarantiaVehiculo, HistorialReparacionGarantia
from apps.attendance.models import Marcaje, ConfiguracionNomina
from apps.accounting.models import CuentaContable, AsientoContable, MovimientoContable, PlanContableDefault
from apps.expenses.models import GastoEstructura

print("=" * 70)
print("  GENERADOR DE DATOS DE PRUEBA COMPLETOS - R CAR ROGIL ERP")
print("=" * 70)
print()

# ============================================================
# 1. USUARIOS (ya existen de create_test_users.py)
# ============================================================
print("[1/10] Verificando usuarios...")
admin = User.objects.get(username='admin')
mecanico1 = User.objects.get(username='mecanico1')
mecanico2 = User.objects.get(username='mecanico2')
vendedor1 = User.objects.get(username='vendedor1')
gestoria1 = User.objects.get(username='gestoria1')
print(f"  admin: {admin.rol}")
print(f"  mecanico1: {mecanico1.rol}, salario={mecanico1.salario_base_mensual}")
print(f"  mecanico2: {mecanico2.rol}, salario={mecanico2.salario_base_mensual}")
print(f"  vendedor1: {vendedor1.rol}")
print(f"  gestoria1: {gestoria1.rol}")
print()

# ============================================================
# 2. MATERIALES (8 materiales con diferentes niveles de stock)
# ============================================================
print("[2/10] Creando materiales...")
materiales_data = [
    {'nombre': 'Aceite motor 5W30', 'descripcion': 'Aceite sintetico para motores diesel y gasolina', 'unidad': 'litros', 'stock_actual': Decimal('50'), 'stock_minimo': Decimal('10'), 'precio_unitario': Decimal('8.50')},
    {'nombre': 'Filtros de aire', 'descripcion': 'Filtro de aire original para vehiculos compactos', 'unidad': 'unidades', 'stock_actual': Decimal('5'), 'stock_minimo': Decimal('2'), 'precio_unitario': Decimal('12.00')},
    {'nombre': 'Pastillas de freno', 'descripcion': 'Juego de pastillas de freno delanteras ceramica', 'unidad': 'juegos', 'stock_actual': Decimal('8'), 'stock_minimo': Decimal('3'), 'precio_unitario': Decimal('35.00')},
    {'nombre': 'Bomba de agua', 'descripcion': 'Bomba de agua con junta para motores TDI', 'unidad': 'unidades', 'stock_actual': Decimal('2'), 'stock_minimo': Decimal('2'), 'precio_unitario': Decimal('85.00')},
    {'nombre': 'Correa distribucion', 'descripcion': 'Kit correa de distribucion con tensor', 'unidad': 'unidades', 'stock_actual': Decimal('1'), 'stock_minimo': Decimal('3'), 'precio_unitario': Decimal('45.00')},
    {'nombre': 'Refrigerante', 'descripcion': 'Refrigerante G12 violeta preparado', 'unidad': 'litros', 'stock_actual': Decimal('3'), 'stock_minimo': Decimal('5'), 'precio_unitario': Decimal('6.50')},
    {'nombre': 'Neumaticos 205/55R16', 'descripcion': 'Neumaticos verano 4 estaciones', 'unidad': 'unidades', 'stock_actual': Decimal('4'), 'stock_minimo': Decimal('4'), 'precio_unitario': Decimal('75.00')},
    {'nombre': 'Limpiaparabrisas', 'descripcion': 'Kit limpiaparabrisas delantero universal', 'unidad': 'unidades', 'stock_actual': Decimal('10'), 'stock_minimo': Decimal('3'), 'precio_unitario': Decimal('8.00')},
]

materiales = {}
for data in materiales_data:
    m, created = Material.objects.get_or_create(nombre=data['nombre'], defaults=data)
    materiales[data['nombre']] = m
    status = 'CREADO' if created else 'YA EXISTE'
    alerta = ' [ALERTA STOCK]' if m.alerta_stock else ''
    print(f"  {m.nombre}: {m.stock_actual} {m.unidad} (min: {m.stock_minimo}) - {status}{alerta}")
print()

# 2b. COMPRAS DE MATERIALES (factura + entrada a inventario + asiento)
print("[2b/10] Registrando compras de materiales (facturas)...")
compras_data = [
    {'material': 'Aceite motor 5W30', 'cantidad': Decimal('20'), 'precio_unitario': Decimal('8.50'),
     'proveedor': 'Distribuciones Auto S.L.', 'cif_nif': 'B11111111', 'tipo_inventario': '300', 'tipo_iva': Decimal('21')},
    {'material': 'Filtros de aire', 'cantidad': Decimal('10'), 'precio_unitario': Decimal('12.00'),
     'proveedor': 'Filtros Ibérica S.A.', 'cif_nif': 'B22222222', 'tipo_inventario': '310', 'tipo_iva': Decimal('21')},
    {'material': 'Neumaticos 205/55R16', 'cantidad': Decimal('4'), 'precio_unitario': Decimal('75.00'),
     'proveedor': 'Neumáticos Express S.L.', 'cif_nif': 'B33333333', 'tipo_inventario': '330', 'tipo_iva': Decimal('21')},
]
for data in compras_data:
    material_obj = materiales[data['material']]
    stock_previo = material_obj.stock_actual
    compra, created = CompraMaterial.objects.get_or_create(
        material=material_obj,
        proveedor=data['proveedor'],
        cif_nif=data['cif_nif'],
        fecha_compra=date(2026, 6, 20),
        defaults={
            'cantidad': data['cantidad'],
            'precio_unitario': data['precio_unitario'],
            'tipo_inventario': data['tipo_inventario'],
            'tipo_iva': data['tipo_iva'],
            'created_by': admin,
        },
    )
    if created:
        material_obj.refresh_from_db()
        compra.crear_asiento_contable()
        print(f"  {compra.material.nombre}: +{compra.cantidad} {compra.material.unidad} "
              f"(stock {stock_previo} -> {material_obj.stock_actual}) - Asiento #{compra.asiento_contable.numero}")
    else:
        print(f"  {compra.material.nombre}: YA EXISTE")
print()

# ============================================================
# 3. VEHICULOS (6 vehiculos en diferentes estados)
# ============================================================
print("[3/10] Creando vehiculos...")

vehiculos_data = [
    # Vehiculo 1: ADQUIRIDO (recien comprado)
    {
        'matricula': '1234ABC', 'bastidor': 'WVWZZZ3CZWE123456',
        'marca': 'Volkswagen', 'modelo': 'Golf VII 1.6 TDI',
        'anio': 2019, 'combustible': 'DIESEL', 'kilometraje': 85000,
        'tipo_dano': 'ACCIDENTAL', 'estado': 'ADQUIRIDO',
        'etiqueta_ambiental': 'C', 'fecha_adquisicion': date(2026, 6, 15),
        'plataforma_subasta': 'BCA', 'precio_subasta': Decimal('8000'),
        'tasas_sala': Decimal('500'), 'logistica_grua': Decimal('300'),
        'descripcion_dano': 'Golpe en paragolpes trasero derecho',
    },
    # Vehiculo 2: TALLER (1 OT en progreso)
    {
        'matricula': '5678DEF', 'bastidor': 'VSSZZZ6KZGY123456',
        'marca': 'Seat', 'modelo': 'Leon 2.0 TDI',
        'anio': 2020, 'combustible': 'DIESEL', 'kilometraje': 62000,
        'tipo_dano': 'ACCIDENTAL', 'estado': 'TALLER',
        'etiqueta_ambiental': 'ECO', 'fecha_adquisicion': date(2026, 5, 20),
        'plataforma_subasta': 'COPART', 'precio_subasta': Decimal('9500'),
        'tasas_sala': Decimal('600'), 'logistica_grua': Decimal('350'),
        'descripcion_dano': 'Golpe frontal, paragolpes y faro derecho',
    },
    # Vehiculo 3: TALLER (2 OTs: 1 completada, 1 pendiente)
    {
        'matricula': '9012GHI', 'bastidor': 'WBA8E9C50JA123456',
        'marca': 'BMW', 'modelo': 'Serie 3 320d',
        'anio': 2018, 'combustible': 'DIESEL', 'kilometraje': 95000,
        'tipo_dano': 'MECANICO', 'estado': 'TALLER',
        'etiqueta_ambiental': 'B', 'fecha_adquisicion': date(2026, 4, 10),
        'plataforma_subasta': 'ADESA', 'precio_subasta': Decimal('12000'),
        'tasas_sala': Decimal('800'), 'logistica_grua': Decimal('400'),
        'descripcion_dano': 'Fallo mecanico en caja de cambios',
    },
    # Vehiculo 4: ACONDICIONADO (reparado, listo para venta)
    {
        'matricula': '3456JKL', 'bastidor': 'WDD176002SN123456',
        'marca': 'Mercedes', 'modelo': 'Clase A 180',
        'anio': 2021, 'combustible': 'GASOLINA', 'kilometraje': 35000,
        'tipo_dano': 'GRANIZO', 'estado': 'ACONDICIONADO',
        'etiqueta_ambiental': 'ECO', 'fecha_adquisicion': date(2026, 3, 5),
        'plataforma_subasta': 'KBC', 'precio_subasta': Decimal('15000'),
        'tasas_sala': Decimal('900'), 'logistica_grua': Decimal('350'),
        'descripcion_dano': 'Danos por granizo en techo y capo',
    },
    # Vehiculo 5: EN_VENTA (publicado en catalogo)
    {
        'matricula': '7890MNO', 'bastidor': 'WF0KXXGBDK123456',
        'marca': 'Ford', 'modelo': 'Focus 1.5 TDCi',
        'anio': 2019, 'combustible': 'DIESEL', 'kilometraje': 78000,
        'tipo_dano': 'ACCIDENTAL', 'estado': 'EN_VENTA',
        'etiqueta_ambiental': 'C', 'fecha_adquisicion': date(2026, 2, 15),
        'plataforma_subasta': 'AUTOVIAS', 'precio_subasta': Decimal('7500'),
        'tasas_sala': Decimal('450'), 'logistica_grua': Decimal('280'),
        'precio_venta': Decimal('14500'),
        'descripcion_dano': 'Golpe lateral izquierdo',
    },
    # Vehiculo 6: VENDIDO (vendido a PARTICULAR)
    {
        'matricula': '1122PQR', 'bastidor': 'JTDKN3DU5A0123456',
        'marca': 'Toyota', 'modelo': 'Yaris Hybrid',
        'anio': 2020, 'combustible': 'HIBRIDO', 'kilometraje': 42000,
        'tipo_dano': 'INUNDACION', 'estado': 'VENDIDO',
        'etiqueta_ambiental': 'ECO', 'fecha_adquisicion': date(2026, 1, 10),
        'plataforma_subasta': 'MANNHEIM', 'precio_subasta': Decimal('11000'),
        'tasas_sala': Decimal('700'), 'logistica_grua': Decimal('320'),
        'precio_venta': Decimal('16500'),
        'descripcion_dano': 'Inundacion parcial, danos en electronica',
    },
]

vehiculos = {}
for data in vehiculos_data:
    data['created_by'] = admin
    matricula = data['matricula']
    v, created = Vehiculo.objects.get_or_create(matricula=matricula, defaults=data)
    vehiculos[matricula] = v
    status = 'CREADO' if created else 'YA EXISTE'
    print(f"  {v.marca} {v.modelo} ({v.matricula}) - {v.estado} - Coste: {v.coste_inicial} EUR - {status}")
print()

# ============================================================
# 4. ORDENES DE TRABAJO (5 OTs en diferentes estados)
# ============================================================
print("[4/10] Creando ordenes de trabajo...")

ots_data = [
    # OT1: Seat Leon - EN_PROGRESO
    {
        'vehiculo': vehiculos['5678DEF'], 'operario': mecanico1,
        'titulo': 'Reparacion paragolpes delantero',
        'descripcion': 'Reparacion y pintura de paragolpes delantero daniado por impacto.',
        'estado': 'EN_PROGRESO', 'horas_estimadas': Decimal('8'),
        'horas_reales': Decimal('5.5'),
        'fecha_inicio': date(2026, 7, 1),
    },
    # OT2: BMW - COMPLETADA
    {
        'vehiculo': vehiculos['9012GHI'], 'operario': mecanico2,
        'titulo': 'Cambio de aceite y filtros',
        'descripcion': 'Cambio de aceite motor 5W30, filtro de aire y filtro de combustible.',
        'estado': 'COMPLETADA', 'horas_estimadas': Decimal('2'),
        'horas_reales': Decimal('1.5'),
        'fecha_inicio': date(2026, 6, 1), 'fecha_fin': date(2026, 6, 1),
    },
    # OT3: BMW - PENDIENTE
    {
        'vehiculo': vehiculos['9012GHI'], 'operario': mecanico1,
        'titulo': 'Reparacion sistema de frenos',
        'descripcion': 'Cambio de pastillas y discos de freno delanteros.',
        'estado': 'PENDIENTE', 'horas_estimadas': Decimal('6'),
        'horas_reales': Decimal('0'),
    },
    # OT4: Mercedes - COMPLETADA
    {
        'vehiculo': vehiculos['3456JKL'], 'operario': mecanico1,
        'titulo': 'Pintura capo y techo',
        'descripcion': 'Reparacion de granizado y pintura completa de capo y techo.',
        'estado': 'COMPLETADA', 'horas_estimadas': Decimal('12'),
        'horas_reales': Decimal('10'),
        'fecha_inicio': date(2026, 5, 15), 'fecha_fin': date(2026, 5, 18),
    },
    # OT5: Mercedes - COMPLETADA
    {
        'vehiculo': vehiculos['3456JKL'], 'operario': mecanico2,
        'titulo': 'Cambio cristales laterales',
        'descripcion': 'Sustitucion de cristales laterales daniados por granizo.',
        'estado': 'COMPLETADA', 'horas_estimadas': Decimal('4'),
        'horas_reales': Decimal('3'),
        'fecha_inicio': date(2026, 5, 20), 'fecha_fin': date(2026, 5, 20),
    },
]

ots = []
for i, data in enumerate(ots_data, 1):
    data['created_by'] = admin
    ot, created = OrdenTrabajo.objects.get_or_create(
        vehiculo=data['vehiculo'], titulo=data['titulo'], defaults=data
    )
    ots.append(ot)
    status = 'CREADA' if created else 'YA EXISTE'
    print(f"  OT{i}: {ot.titulo} - {ot.estado} - {ot.vehiculo.matricula} - {status}")
print()

# ============================================================
# 5. MATERIALES USADOS EN OTs
# ============================================================
print("[5/10] Registrando materiales usados en OTs...")

materiales_usados_data = [
    # OT1 Seat: pastillas de freno
    {'orden_trabajo': ots[0], 'material': materiales['Pastillas de freno'], 'cantidad': Decimal('1')},
    # OT2 BMW: aceite y filtro
    {'orden_trabajo': ots[1], 'material': materiales['Aceite motor 5W30'], 'cantidad': Decimal('5')},
    {'orden_trabajo': ots[1], 'material': materiales['Filtros de aire'], 'cantidad': Decimal('1')},
    # OT4 Mercedes: neumaticos
    {'orden_trabajo': ots[3], 'material': materiales['Neumaticos 205/55R16'], 'cantidad': Decimal('4')},
    # OT5 Mercedes: limpiaparabrisas
    {'orden_trabajo': ots[4], 'material': materiales['Limpiaparabrisas'], 'cantidad': Decimal('2')},
]

for data in materiales_usados_data:
    mu, created = MaterialUsado.objects.get_or_create(
        orden_trabajo=data['orden_trabajo'], material=data['material'],
        defaults={'cantidad': data['cantidad']}
    )
    subtotal = mu.cantidad * mu.material.precio_unitario
    status = 'CREADO' if created else 'YA EXISTE'
    print(f"  {mu.material.nombre}: {mu.cantidad} x {mu.material.precio_unitario} = {subtotal} EUR - {status}")
print()

# ============================================================
# 6. VENTAS (1 venta B2C completada)
# ============================================================
print("[6/10] Registrando ventas...")

# Venta del Toyota Yaris (B2C)
venta_data = {
    'vehiculo': vehiculos['1122PQR'],
    'tipo_cliente': 'PARTICULAR',
    'cliente_nombre': 'Carlos Garcia Lopez',
    'cliente_dni': '54321678K',
    'cliente_direccion': 'Calle Serrano 45, 3oB',
    'cliente_poblacion': 'Madrid',
    'cliente_provincia': 'Madrid',
    'cliente_cp': '28006',
    'cliente_telefono': '612345678',
    'cliente_email': 'carlos.garcia@email.com',
    'fecha_venta': date(2026, 7, 1),
    'metodo_pago': 'TRANSFERENCIA',
    'precio_venta': Decimal('16500'),
    'coste_total': vehiculos['1122PQR'].coste_total,
    'created_by': admin,
}

venta, created = VentaVehiculo.objects.get_or_create(
    vehiculo=venta_data['vehiculo'], defaults=venta_data
)
if created:
    base_imp = venta.precio_venta - venta.coste_total
    cuota_iva = base_imp * Decimal('0.21') if base_imp > 0 else Decimal('0')
    print(f"  Venta Toyota Yaris -> Carlos Garcia Lopez")
    print(f"    Precio: {venta.precio_venta} EUR")
    print(f"    Coste total: {venta.coste_total} EUR")
    print(f"    Base imponible: {base_imp} EUR")
    print(f"    Cuota IVA (21%): {cuota_iva} EUR")
    print(f"    Tipo: {venta.tipo_cliente}")
else:
    print(f"  Venta Toyota Yaris - YA EXISTE")
print()

# ============================================================
# 7. GARANTIAS
# ============================================================
print("[7/10] Verificando garantias...")

garantias = GarantiaVehiculo.objects.all()
for g in garantias:
    vigente = 'VIGENTE' if g.esta_vigente else 'VENCIDA'
    print(f"  Garantia Venta #{g.venta_id}: {g.tipo_cliente} - {g.fecha_inicio} a {g.fecha_fin} - {vigente}")

# Crear reparacion en garantia si existe la garantia del Toyota
if garantias.exists():
    g_toyota = garantias.filter(venta__vehiculo=vehiculos['1122PQR']).first()
    if g_toyota:
        rep, created = HistorialReparacionGarantia.objects.get_or_create(
            garantia=g_toyota,
            descripcion='Ruido anomalo en la transmision al frenar en pendiente',
            defaults={
                'fecha_ingreso_taller': date(2026, 7, 15),
                'estado': 'PROCESO',
                'costo_repuestos_interno': Decimal('180'),
                'costo_mano_obra_interno': Decimal('120'),
            }
        )
        status = 'CREADA' if created else 'YA EXISTE'
        print(f"  Reparacion garantia Toyota: {rep.descripcion[:50]}... - {status}")
print()

# ============================================================
# 8. ASISTENCIA Y NOMINA
# ============================================================
print("[8/10] Configurando asistencia y nomina...")

# Configuracion de nomina
for op in [mecanico1, mecanico2]:
    config, created = ConfiguracionNomina.objects.get_or_create(
        operario=op,
        defaults={
            'salario_base_mensual': op.salario_base_mensual or Decimal('1800'),
            'porcentaje_ss_patronal': Decimal('31.50'),
        }
    )
    status = 'CREADA' if created else 'YA EXISTE'
    print(f"  Nomina {op.username}: {config.salario_base_mensual} EUR/mes - {status}")

# Marcajes de mecanico1 (semana completa)
base_date = date(2026, 6, 30)
marcajes_data = []
for i in range(5):  # Lunes a Viernes
    d = base_date + timedelta(days=i)
    marcajes_data.append({'operario': mecanico1, 'tipo': 'ENTRADA', 'fecha_hora': datetime(d.year, d.month, d.day, 8, 0), 'ip_address': '192.168.1.100', 'validado': True})
    hora_salida = 15 if i == 4 else 17  # Viernes sale a las 15
    marcajes_data.append({'operario': mecanico1, 'tipo': 'SALIDA', 'fecha_hora': datetime(d.year, d.month, d.day, hora_salida, 0), 'ip_address': '192.168.1.100', 'validado': True})

# Marcajes de mecanico2 (miercoles a viernes)
for i in range(2, 5):
    d = base_date + timedelta(days=i)
    marcajes_data.append({'operario': mecanico2, 'tipo': 'ENTRADA', 'fecha_hora': datetime(d.year, d.month, d.day, 9, 0), 'ip_address': '192.168.1.101', 'validado': True})
    marcajes_data.append({'operario': mecanico2, 'tipo': 'SALIDA', 'fecha_hora': datetime(d.year, d.month, d.day, 18, 0), 'ip_address': '192.168.1.101', 'validado': True})

for data in marcajes_data:
    m, created = Marcaje.objects.get_or_create(
        operario=data['operario'], fecha_hora=data['fecha_hora'],
        defaults={'tipo': data['tipo'], 'ip_address': data['ip_address'], 'validado': data['validado']}
    )
    if created:
        print(f"  Marcaje: {m.operario.username} - {m.tipo} - {m.fecha_hora}")
print()

# ============================================================
# 9. CONTABILIDAD
# ============================================================
print("[9/10] Configurando contabilidad...")

# Inicializar plan contable
try:
    PlanContableDefault.crear_plan_base()
    print("  Plan General Contable inicializado (33 cuentas base)")
except Exception as e:
    print(f"  Plan contable: {e}")

# Asiento 1: Compra de material de limpieza
try:
    a1, created = AsientoContable.objects.get_or_create(
        numero='000001',
        defaults={
            'fecha': date(2026, 7, 1),
            'concepto': 'Compra material de limpieza',
            'estado': 'POSTEADO',
            'created_by': admin,
        }
    )
    if created:
        cuenta_620 = CuentaContable.objects.get(codigo='620')
        cuenta_572 = CuentaContable.objects.get(codigo='572')
        MovimientoContable.objects.create(asiento=a1, cuenta=cuenta_620, debe=Decimal('150'), descripcion='Material limpieza')
        MovimientoContable.objects.create(asiento=a1, cuenta=cuenta_572, haber=Decimal('150'), descripcion='Pago banco')
        print(f"  Asiento 000001: Compra limpieza - 150 EUR")
except Exception as e:
    print(f"  Asiento 000001: {e}")

# Asiento 2: Alquiler con retencion IRPF
try:
    a2, created = AsientoContable.objects.get_or_create(
        numero='000002',
        defaults={
            'fecha': date(2026, 7, 5),
            'concepto': 'Alquiler julio 2026 con retencion IRPF',
            'estado': 'POSTEADO',
            'created_by': admin,
        }
    )
    if created:
        cuenta_621 = CuentaContable.objects.get(codigo='621')
        cuenta_472 = CuentaContable.objects.get(codigo='472')
        cuenta_4751 = CuentaContable.objects.get(codigo='4751.115')
        cuenta_410 = CuentaContable.objects.get(codigo='410')
        MovimientoContable.objects.create(asiento=a2, cuenta=cuenta_621, debe=Decimal('2000'), descripcion='Alquiler galpon')
        MovimientoContable.objects.create(asiento=a2, cuenta=cuenta_472, debe=Decimal('420'), descripcion='IVA soportado 21%')
        MovimientoContable.objects.create(asiento=a2, cuenta=cuenta_4751, haber=Decimal('380'), descripcion='Retencion IRPF 19%')
        MovimientoContable.objects.create(asiento=a2, cuenta=cuenta_410, haber=Decimal('2040'), descripcion='Propietario galpon')
        print(f"  Asiento 000002: Alquiler julio - 2040 EUR (con IRPF)")
except Exception as e:
    print(f"  Asiento 000002: {e}")
print()

# ============================================================
# 10. GASTOS DE ESTRUCTURA (8 gastos cubriendo todas las categorias)
# ============================================================
print("[10/10] Creando gastos de estructura...")

gastos_data = [
    {'fecha_factura': date(2026, 7, 1), 'proveedor_acreedor': 'Propietario Galpon S.L.', 'cif_nif': 'B12345678', 'categoria': 'ARRENDAMIENTO', 'base_imponible': Decimal('2000'), 'tipo_iva': Decimal('21'), 'retencion_irpf': Decimal('19')},
    {'fecha_factura': date(2026, 7, 5), 'proveedor_acreedor': 'Endesa Energia S.A.U.', 'cif_nif': 'B12345678', 'categoria': 'SUMINISTROS', 'base_imponible': Decimal('350'), 'tipo_iva': Decimal('21'), 'retencion_irpf': Decimal('0')},
    {'fecha_factura': date(2026, 7, 10), 'proveedor_acreedor': 'Distrilimpia S.L.', 'cif_nif': 'B87654321', 'categoria': 'LIMPIEZA_PROD', 'base_imponible': Decimal('180'), 'tipo_iva': Decimal('21'), 'retencion_irpf': Decimal('0')},
    {'fecha_factura': date(2026, 7, 15), 'proveedor_acreedor': 'CleanPro Servicios S.A.', 'cif_nif': 'B12345678', 'categoria': 'LIMPIEZA_SERV', 'base_imponible': Decimal('450'), 'tipo_iva': Decimal('21'), 'retencion_irpf': Decimal('0')},
    {'fecha_factura': date(2026, 7, 20), 'proveedor_acreedor': 'Ayuntamiento de Alcala de Henares', 'cif_nif': 'P00000000', 'categoria': 'IMPUESTOS_ESTR', 'base_imponible': Decimal('320'), 'tipo_iva': Decimal('0'), 'retencion_irpf': Decimal('0')},
    {'fecha_factura': date(2026, 7, 25), 'proveedor_acreedor': 'Jardines y Paisajismo S.L.', 'cif_nif': 'B11223344', 'categoria': 'OTROS', 'base_imponible': Decimal('120'), 'tipo_iva': Decimal('21'), 'retencion_irpf': Decimal('0')},
]

for data in gastos_data:
    data['created_by'] = admin
    g, created = GastoEstructura.objects.get_or_create(
        fecha_factura=data['fecha_factura'],
        proveedor_acreedor=data['proveedor_acreedor'],
        defaults=data
    )
    status = 'CREADO' if created else 'YA EXISTE'
    print(f"  {g.categoria}: {g.proveedor_acreedor} - {g.total_factura} EUR - {status}")
print()

# ============================================================
# RESUMEN FINAL
# ============================================================
print("=" * 70)
print("  RESUMEN DE DATOS CREADOS")
print("=" * 70)
print()
print(f"  Usuarios:     {User.objects.count()}")
print(f"  Vehiculos:    {Vehiculo.objects.count()}")
print(f"  Materiales:   {Material.objects.count()}")
print(f"  OTs:          {OrdenTrabajo.objects.count()}")
print(f"  MaterialesUsados: {MaterialUsado.objects.count()}")
print(f"  Ventas:       {VentaVehiculo.objects.count()}")
print(f"  Garantias:    {GarantiaVehiculo.objects.count()}")
print(f"  Reparaciones Garantia: {HistorialReparacionGarantia.objects.count()}")
print(f"  Marcajes:     {Marcaje.objects.count()}")
print(f"  Config Nomina: {ConfiguracionNomina.objects.count()}")
print(f"  Cuentas Contables: {CuentaContable.objects.count()}")
print(f"  Asientos:     {AsientoContable.objects.count()}")
print(f"  Movimientos:  {MovimientoContable.objects.count()}")
print(f"  Gastos:       {GastoEstructura.objects.count()}")
print()
print("=" * 70)
print("  DATOS DE PRUEBA CREADOS EXITOSAMENTE!")
print("=" * 70)
print()
print("  Acceda al ERP: https://<app>.onrender.com/erp/")
print("  Acceda al Admin: https://<app>.onrender.com/admin/")
print("  Acceda al API: https://<app>.onrender.com/api/vehiculos/")
print()
