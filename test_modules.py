import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
django.setup()

from django.test import Client
from apps.accounts.models import User

results = []

def test(name, response_code, expected):
    ok = response_code == expected
    tag = '[OK]' if ok else '[FAIL]'
    results.append((tag, name, response_code, expected))
    print(f'  {tag} {name}: {response_code} (expected {expected})')

c = Client()

# 1. Public pages
print('--- PUBLIC PAGES ---')
test('Login page', c.get('/erp/accounts/login/').status_code, 200)
test('API vehiculos', c.get('/api/vehiculos/').status_code, 200)

# 2. Unauthenticated -> redirect
print('\n--- REDIRECTS (need login) ---')
test('Home -> redirect', c.get('/erp/').status_code, 302)
test('Vehiculos -> redirect', c.get('/erp/vehiculos/').status_code, 302)
test('Taller -> redirect', c.get('/erp/taller/').status_code, 302)
test('Ventas -> redirect', c.get('/erp/ventas/').status_code, 302)
test('Asistencia -> redirect', c.get('/erp/asistencia/').status_code, 302)
test('Garantias -> redirect', c.get('/erp/garantias/').status_code, 302)
test('Contabilidad -> redirect', c.get('/erp/contabilidad/').status_code, 302)

# 3. Login as admin
print('\n--- ADMIN LOGIN ---')
admin = User.objects.get(username='admin')
c.force_login(admin)
test('Dashboard (admin)', c.get('/erp/').status_code, 200)

# 4. Vehicles
print('\n--- VEHICLES ---')
test('Vehiculos list', c.get('/erp/vehiculos/').status_code, 200)
test('Vehiculo create', c.get('/erp/vehiculos/nuevo/').status_code, 200)

# 5. Workshop
print('\n--- WORKSHOP ---')
test('Taller list', c.get('/erp/taller/').status_code, 200)
test('Taller OT create', c.get('/erp/taller/nueva/').status_code, 200)
test('Inventario', c.get('/erp/taller/materiales/').status_code, 200)
test('Material create', c.get('/erp/taller/materiales/nuevo/').status_code, 200)

# 6. Sales
print('\n--- SALES ---')
test('Ventas list', c.get('/erp/ventas/').status_code, 200)
test('Venta create', c.get('/erp/ventas/nueva/').status_code, 200)

# 7. Attendance
print('\n--- ATTENDANCE ---')
test('Asistencia list', c.get('/erp/asistencia/').status_code, 200)
test('Marcaje create', c.get('/erp/asistencia/nuevo/').status_code, 200)
test('Kiosco', c.get('/erp/asistencia/kiosco/').status_code, 200)
test('Nomina list', c.get('/erp/asistencia/nomina/').status_code, 200)
test('Nomina create', c.get('/erp/asistencia/nomina/nueva/').status_code, 200)

# 8. Warranty
print('\n--- WARRANTY ---')
test('Garantias list', c.get('/erp/garantias/').status_code, 200)

# 9. Accounting
print('\n--- ACCOUNTING ---')
test('Contabilidad list', c.get('/erp/contabilidad/').status_code, 200)
test('Asiento create', c.get('/erp/contabilidad/nuevo/').status_code, 200)
test('Cuentas', c.get('/erp/contabilidad/cuentas/').status_code, 200)
test('Cuenta create', c.get('/erp/contabilidad/cuentas/nueva/').status_code, 200)
test('Init plan contable', c.get('/erp/contabilidad/cuentas/inicializar/').status_code, 302)

# 9.1 Financial Reports
print('\n--- FINANCIAL REPORTS ---')
test('Informes list', c.get('/erp/contabilidad/informes/').status_code, 200)
test('PyG', c.get('/erp/contabilidad/informes/pyg/').status_code, 200)
test('Balance', c.get('/erp/contabilidad/informes/balance/').status_code, 200)
test('IVA', c.get('/erp/contabilidad/informes/iva/').status_code, 200)
test('Comparativa', c.get('/erp/contabilidad/informes/comparativa/').status_code, 200)
test('Facturas compras', c.get('/erp/contabilidad/informes/facturas-compras/').status_code, 200)
test('Libro Diario', c.get('/erp/contabilidad/informes/libro-diario/').status_code, 200)
test('Libro Mayor', c.get('/erp/contabilidad/informes/libro-mayor/').status_code, 200)
test('Existencias', c.get('/erp/contabilidad/informes/existencias/').status_code, 200)

# 9.2 Expenses (Module 8)
print('\n--- EXPENSES (Module 8) ---')
test('Gastos list', c.get('/erp/gastos/').status_code, 200)
test('Gasto create', c.get('/erp/gastos/nuevo/').status_code, 200)
test('Gastos export', c.get('/erp/gastos/exportar/').status_code, 200)

# 10. Django admin
print('\n--- ADMIN ---')
test('Django admin', c.get('/admin/').status_code, 200)

# 11. Test vendedor role
print('\n--- VENDEDOR ROLE ---')
c.logout()
vendedor = User.objects.get(username='vendedor1')
c.force_login(vendedor)
test('Dashboard (vendedor)', c.get('/erp/').status_code, 200)
test('Vehiculos (vendedor)', c.get('/erp/vehiculos/').status_code, 200)
test('Ventas (vendedor)', c.get('/erp/ventas/').status_code, 200)
test('Admin (vendedor blocked)', c.get('/admin/').status_code, 302)

# 12. Test operario role
print('\n--- OPERARIO ROLE ---')
c.logout()
operario = User.objects.get(username='mecanico1')
c.force_login(operario)
test('Dashboard (operario)', c.get('/erp/').status_code, 200)
test('Taller (operario)', c.get('/erp/taller/').status_code, 200)
test('Inventario (operario)', c.get('/erp/taller/materiales/').status_code, 200)

# 13. Test gestoria role
print('\n--- GESTORIA ROLE ---')
c.logout()
gestoria = User.objects.get(username='gestoria1')
c.force_login(gestoria)
test('Dashboard (gestoria)', c.get('/erp/').status_code, 200)
test('Contabilidad (gestoria)', c.get('/erp/contabilidad/').status_code, 200)
test('Cuentas (gestoria)', c.get('/erp/contabilidad/cuentas/').status_code, 200)
test('Gastos (gestoria)', c.get('/erp/gastos/').status_code, 200)
test('Gastos export (gestoria)', c.get('/erp/gastos/exportar/').status_code, 200)

# Summary
print('\n' + '=' * 60)
print('  TEST RESULTS SUMMARY')
print('=' * 60)
ok = sum(1 for r in results if r[0] == '[OK]')
fail = sum(1 for r in results if r[0] == '[FAIL]')
for tag, name, got, expected in results:
    if tag == '[FAIL]':
        print(f'  {tag} {name}: got {got}, expected {expected}')

print('=' * 60)
print(f'  Total: {ok + fail} | OK: {ok} | FAIL: {fail}')
if fail == 0:
    print('  ALL TESTS PASSED!')
print('=' * 60)
