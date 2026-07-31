# Manual de Pruebas — Eurocar ERP

## 1. Información General

| Ítem | Detalle |
|------|---------|
| **Sistema** | R Car Rogil ERP |
| **Entorno** | Staging en Render |
| **URL** | `https://eurocar-staging.onrender.com` |
| **Usuario** | `tester` |
| **Contraseña** | `TestMadrid2024!` |
| **Rol** | ADMIN (acceso completo, puede eliminar) |
| **Fecha pruebas** | _________________________ |
| **Tester** | _________________________ |

> **Nota**: El sistema está desplegado en servidores de Render (Oregón, EE.UU.). La latencia esperada desde Madrid es de 130-160 ms, perfectamente navegable.

---

## 2. Pruebas de Acceso y Autenticación

### 2.1 Acceso al sistema
1. Abrir navegador (Chrome/Edge/Firefox)
2. Ir a `https://eurocar-staging.onrender.com`
3. **Esperado**: Redirige a la página de login (ruta `/erp/accounts/login/`)

### 2.2 Login como ADMIN
1. Ingresar usuario: `tester`
2. Ingresar contraseña: `TestMadrid2024!`
3. Hacer clic en "Iniciar sesión"
4. **Esperado**: Accede al dashboard principal (`/erp/`)

### 2.3 Cierre de sesión
1. Hacer clic en el menú de usuario (esquina superior derecha)
2. Seleccionar "Cerrar sesión"
3. **Esperado**: Redirige al login

### 2.4 Recordar sesión
1. Marcar "Recordar sesión" al hacer login
2. Cerrar y reabrir el navegador
3. **Esperado**: La sesión se mantiene activa

### 2.5 Sesión expirada
1. Dejar el sistema inactivo por 60 minutos (la sesión expira en 1h)
2. Intentar navegar a cualquier página
3. **Esperado**: Redirige al login

---

## 3. Dashboard (Inicio)

### 3.1 Vista general
1. Iniciar sesión como `tester`
2. **Esperado**: El dashboard carga con:
   - Resumen de vehículos en venta
   - Órdenes de trabajo activas
   - Ventas recientes
   - Alertas/avisos (si los hay)

### 3.2 Navegación por módulos
Hacer clic en cada enlace de la barra lateral y verificar que cargan:
- [ ] **🚗 Vehículos** → `/erp/vehiculos/`
- [ ] **🔧 Taller** → `/erp/taller/`
- [ ] **💰 Ventas** → `/erp/ventas/`
- [ ] **⏰ Asistencia** → `/erp/asistencia/`
- [ ] **🛡️ Garantías** → `/erp/garantias/`
- [ ] **📊 Contabilidad** → `/erp/contabilidad/`
- [ ] **💸 Gastos** → `/erp/gastos/`
- [ ] **🏦 Banco** → `/erp/banco/`

---

## 4. Módulo Vehículos

### 4.1 Listado de vehículos
1. Ir a **🚗 Vehículos**
2. **Esperado**: Tabla con los vehículos existentes (o mensaje "Sin vehículos" si está vacío)

### 4.2 Crear vehículo nuevo
1. Hacer clic en "Nuevo vehículo"
2. Rellenar campos mínimos:
   - Matrícula: `TEST001` (o una única)
   - Marca: `Test`
   - Modelo: `Pruebas`
   - Año: `2024`
   - Kilometraje: `0`
   - Combustible: `Gasolina`
   - Precio venta: `10000`
   - Estado: `EN_VENTA`
3. Guardar
4. **Esperado**: Vehículo creado, redirige al detalle con mensaje de éxito

### 4.3 Editar vehículo
1. Desde el listado, hacer clic en el vehículo creado
2. Clic en "Editar"
3. Cambiar precio a `12000`
4. Guardar
5. **Esperado**: Precio actualizado correctamente

### 4.4 Subir imágenes (requiere estado EN_VENTA)
1. Editar el vehículo con estado `EN_VENTA`
2. En la sección "Imágenes", seleccionar un archivo de imagen (máx 8)
3. Marcar como "Principal" si se desea
4. Guardar
5. **Esperado**: La imagen aparece asociada al vehículo
6. **Verificar**: Cambiar el estado del vehículo a otro (ej. `VENDIDO`) y subir otra imagen — la imagen debería descartarse

### 4.5 Eliminar vehículo (admin: puede_eliminar=True)
1. Desde el detalle del vehículo, hacer clic en "Eliminar"
2. Confirmar
3. **Esperado**: Vehículo eliminado (o mensaje de confirmación)

### 4.6 Compra de vehículo (factura)
1. Crear o editar vehículo
2. Rellenar sección "Factura de compra":
   - Proveedor: `Proveedor Test`
   - CIF/NIF: `12345678A`
   - Número factura: `FAC-TEST-001`
   - Base imponible: `8000`
   - IVA: `21%`
   - Forma pago: `Transferencia`
3. Guardar
4. **Esperado**: Se genera asiento contable automático + movimiento bancario

---

## 5. Módulo Taller

### 5.1 Listado de órdenes de trabajo
1. Ir a **🔧 Taller**
2. **Esperado**: Listado de OTs (vacío si no hay datos)

### 5.2 Crear orden de trabajo
1. Clic en "Nueva OT"
2. Seleccionar vehículo (debe existir uno)
3. Rellenar descripción: `Prueba de taller`
4. Asignar operario (ej. `mecanico1`)
5. Guardar
6. **Esperado**: OT creada, visible en el listado

### 5.3 Añadir material usado
1. Abrir la OT creada
2. Ir a sección "Materiales"
3. Seleccionar un material existente (si hay stock) o crear uno nuevo
4. Indicar cantidad
5. Guardar
6. **Esperado**: Stock del material se decrementa, coste se añade a la OT

### 5.4 Inventario — Registrar compra de material
1. Ir a **Inventario** → **🛒 Registrar Compra**
2. Seleccionar material (o crear nuevo inline)
3. Rellenar:
   - Proveedor: `Proveedor Test`
   - CIF/NIF: `12345678A`
   - Número factura: `FAC-MAT-TEST`
   - Base imponible y cuota IVA
4. Guardar
5. **Esperado**: Stock se incrementa, se genera asiento contable auto-posteado

### 5.5 Completar OT
1. Abrir la OT
2. Cambiar estado a `COMPLETADA`
3. Guardar
4. **Esperado**: OT marcada como completada

---

## 6. Módulo Ventas

### 6.1 Listado de ventas
1. Ir a **💰 Ventas**
2. **Esperado**: Listado de ventas realizadas

### 6.2 Crear venta (contrato)
1. Clic en "Nueva venta"
2. Seleccionar vehículo (debe estar `EN_VENTA`)
3. Seleccionar cliente (o crear nuevo)
4. Rellenar precio de venta, forma de pago
5. Guardar
6. **Esperado**: Venta creada, vehículo pasa a estado `VENDIDO`, se generan asientos contables

### 6.3 Ver factura REBU
1. Desde la venta, hacer clic en "Ver factura" o "Generar PDF"
2. **Esperado**: PDF de factura se genera y descarga

---

## 7. Módulo Asistencia

### 7.1 Kiosco (marcaje con PIN)
1. Ir a **⏰ Asistencia** → **Kiosco**
2. Ingresar PIN de un operario (ej. `1234` para mecánico1)
3. **Esperado**: Marcaje registrado (entrada/salida según corresponda)

### 7.2 Registro manual de marcaje
1. Ir a **Nuevo marcaje**
2. Seleccionar usuario, fecha, hora, tipo (entrada/salida)
3. Guardar
4. **Esperado**: Marcaje registrado

### 7.3 Nóminas
1. Ir a **Nóminas**
2. Hacer clic en "Nueva nómina"
3. Seleccionar mes y año
4. **Esperado**: Nómina generada (si hay datos de asistencia y salario)

---

## 8. Módulo Garantías

### 8.1 Listado de garantías
1. Ir a **🛡️ Garantías**
2. **Esperado**: Listado de garantías activas

### 8.2 Registrar reparación en garantía
1. Abrir una garantía existente
2. Añadir historial de reparación
3. Guardar
4. **Esperado**: Reparación registrada

---

## 9. Módulo Contabilidad

### 9.1 Inicializar plan contable
1. Ir a **📊 Contabilidad** → **Cuentas** → **Inicializar plan contable**
2. **Esperado**: Se crean las cuentas del PGC (Plan General Contable)

### 9.2 Ver asientos contables
1. Ir a **Asientos**
2. **Esperado**: Listado de asientos generados automáticamente (ventas, compras, gastos, etc.)

### 9.3 Crear asiento manual
1. Clic en "Nuevo asiento"
2. Fecha, concepto
3. Añadir movimientos: cuenta DEBE y cuenta HABER
4. Guardar
5. **Esperado**: Asiento creado

---

## 10. Módulo Gastos

### 10.1 Listado de gastos
1. Ir a **💸 Gastos**
2. **Esperado**: Listado de gastos registrados

### 10.2 Crear gasto de estructura
1. Clic en "Nuevo gasto"
2. Rellenar:
   - Proveedor/acreedor
   - CIF/NIF
   - Categoría (ej. Alquiler, Suministros)
   - Base imponible
   - IVA
3. Guardar
4. **Esperado**: Gasto creado, asiento contable generado

### 10.3 Subir PDF de factura (admin)
1. Editar un gasto existente
2. En sección "Documento PDF", seleccionar archivo
3. Guardar
4. **Esperado**: PDF asociado al gasto

---

## 11. Módulo Banco

### 11.1 Cuentas bancarias
1. Ir a **🏦 Banco** → **Cuentas**
2. **Esperado**: Listado de cuentas bancarias registradas

### 11.2 Ver movimientos
1. Ir a **Movimientos**
2. **Esperado**: Movimientos generados automáticamente por cada transacción (venta, compra, gasto, etc.)

### 11.3 Conciliación bancaria
1. Ir a **Conciliación**
2. Subir un archivo CSV con extracto bancario
3. **Esperado**: El sistema intenta emparejar movimientos

### 11.4 Reservas bancarias
1. Ir a **Reservas**
2. **Esperado**: Listado de reservas

---

## 12. API Pública

### 12.1 Health check
- URL: `https://eurocar-staging.onrender.com/api/ping/`
- **Esperado**: Responde `OK`

### 12.2 Catálogo público (JSON)
- URL: `https://eurocar-staging.onrender.com/api/vehiculos/`
- **Esperado**: JSON con vehículos en venta

### 12.3 Catálogo público (HTML)
- Navegar a la URL anterior con navegador
- Cabecera `Accept: text/html`
- **Esperado**: Lista HTML de vehículos

### 12.4 Marcas disponibles
- URL: `https://eurocar-staging.onrender.com/api/marcas/`
- **Esperado**: JSON con marcas de vehículos disponibles

---

## 13. Web Pública (SPA Vue)

### 13.1 Página principal
1. Ir a `https://eurocar-staging.onrender.com/` (sin `/erp/`)
2. **Esperado**: Si el build de frontend está disponible, carga el SPA de catálogo público
3. Si no está construido: muestra "Web pública no construida" (404)

### 13.2 Navegación SPA
1. Navegar por las secciones del SPA (catálogo, contacto, etc.)
2. **Esperado**: Las rutas funcionan sin recargar la página

---

## 14. Pruebas de Roles y Permisos

> **Nota**: Para estas pruebas se necesitan los usuarios de prueba (creados con `create_test_users.py`)

### 14.1 VENDEDOR
- Usuario: `vendedor1` / `vendedor123!`
- Accede a: Dashboard, Vehículos, Ventas
- **NO accede**: Taller, Asistencia, Gastos, Contabilidad, Banco

### 14.2 OPERARIO
- Usuario: `mecanico1` / `mecanico123!` (PIN: `1234`)
- Accede a: Dashboard, Taller, Inventario, Asistencia (kiosco)
- **NO accede**: Ventas, Gastos, Contabilidad, Banco, Admin Django

### 14.3 GESTORIA
- Usuario: `gestoria1` / `gestoria123!`
- Accede a: Dashboard, Contabilidad (solo lectura), Gastos
- **NO accede**: Vehículos, Taller, Ventas, Asistencia

---

## 15. Checklist Rápido (para verificación diaria)

- [ ] Login funciona
- [ ] Dashboard carga con datos
- [ ] Se puede crear un vehículo
- [ ] Se puede crear una OT en taller
- [ ] Se puede registrar un marcaje
- [ ] API `/api/ping/` responde OK
- [ ] API `/api/vehiculos/` devuelve datos
- [ ] Los asientos contables se generan automáticamente al crear ventas/compras
- [ ] El cierre de sesión funciona
- [ ] La navegación entre módulos es fluida

---

## 16. Reporte de Incidencias

Para reportar un error, incluir:

1. **Módulo**: ¿Dónde ocurrió?
2. **Pasos para reproducir**: Números de paso del manual
3. **Resultado esperado**: Lo que debería pasar
4. **Resultado obtenido**: Lo que realmente pasó
5. **Captura de pantalla**: (si aplica)
6. **Fecha y hora**: _________________________

---

*Fin del manual de pruebas — R Car Rogil ERP*
*Generado para pruebas en entorno staging Render*
