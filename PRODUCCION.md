# Puesta en producción

Guía para llevar este repositorio a producción. Lo que depende de accesos
externos (Render, Cloudflare R2, GitHub) está marcado como **[manual]**.

## Estado del código

| Comprobación | Comando | Estado |
|---|---|---|
| Tests | `cd backend && python manage.py test` | 82 tests OK (1 skip) |
| Seguridad y ajustes | `cd backend && python manage.py check --deploy --fail-level WARNING` | Limpio |
| Modelos vs migraciones | `cd backend && python manage.py makemigrations --check --dry-run` | Sin cambios |
| Entorno desplegado | `cd backend && python manage.py verificar_produccion` | Falla mientras no haya bucket |

`verificar_produccion` es la puerta final: devuelve código 1 si el entorno no
está listo (DEBUG activo, SECRET_KEY débil, SQLite, sin almacenamiento
persistente, sin HTTPS obligatorio). Añadir `--estricto` para tratar también
los avisos como fallo.

## 1. Almacenamiento de archivos (bloqueante) [manual]

Sin almacenamiento remoto, **las facturas, fotos de vehículos y contratos se
borran en cada despliegue**: el sistema de archivos de Render es efímero.

1. Crear un bucket en Cloudflare R2 (o S3).
2. Hacerlo público para lectura (`AWS_QUERYSTRING_AUTH=False` ya está puesto).
3. Definir en Render:

```
AWS_STORAGE_BUCKET_NAME=<bucket>
AWS_S3_ACCESS_KEY_ID=<key>
AWS_S3_SECRET_ACCESS_KEY=<secret>
AWS_S3_ENDPOINT_URL=https://<id>.r2.cloudflarestorage.com
AWS_S3_REGION_NAME=auto
AWS_S3_CUSTOM_DOMAIN=pub-<hash>.r2.dev
```

`backend/config/settings/production.py` solo activa S3 si existe
`AWS_STORAGE_BUCKET_NAME`; con el dominio personalizado, `MEDIA_URL` apunta
ahí y los enlaces de descarga del ERP siguen funcionando.

## 2. Variables de entorno en Render [manual]

```
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<50+ caracteres aleatorios, sin prefijo django-insecure->
DEBUG=False
ALLOWED_HOSTS=eurocar-jdx2.onrender.com
DATABASE_URL=<cadena de PostgreSQL>
```

Opcionales pero recomendadas: `REDIS_URL` (sin ella la caché es local y
Celery pasa a ejecución síncrona), `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
`DEFAULT_FROM_EMAIL`.

**No** subir `backend/.env` ni `.env.production`: ya no están versionados.

## 3. Despliegue [manual]

Build:

```
pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate
```

Start:

```
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120
```

`/api/ping/` no toca base de datos: es el `healthCheckPath` correcto.
Si el servicio responde 404 en `/api/ping/`, el servicio no está sirviendo la
aplicación (no es un problema de datos).

## 4. Verificación tras el despliegue

```bash
python manage.py verificar_produccion --estricto
curl -fsS https://<dominio>/api/ping/   # debe devolver OK
curl -fsS -o /dev/null -w '%{http_code}\n' https://<dominio>/erp/   # 200
```

Y en la aplicación: entrar con un usuario real, abrir una venta y **generar un
contrato en PDF** (valida el motor de PDF y el almacenamiento de media).

## 5. Respaldos y restauración [manual]

`.github/workflows/backup.yml` hace `pg_dump` diario a las 04:00 UTC, verifica
que el volcado sea legible (`pg_restore --list`) y lo guarda como artifact de
GitHub con 90 días de retención.

Requisito: el secreto `DATABASE_URL` del repositorio debe apuntar a la base de
producción.

Restauración (probar al menos una vez, sobre una base de pruebas):

```bash
pg_restore --clean --if-exists --no-owner -d "$DATABASE_URL" backup_django_YYYYMMDD.sql
```

> Los artifacts de GitHub no son un plan de recuperación completo: **descargar
> una copia periódica fuera de GitHub** y probar la restauración.

## 6. Riesgos que quedan abiertos- **Base de datos compartida** entre staging y producción: un `migrate` en
  staging afecta a producción. Separar antes de manejar datos reales.
- **Sin monitorización de errores** (no hay Sentry): los fallos solo se ven en
  los logs de Render.
- **Plan gratuito de Render**: el servicio se suspende por inactividad y las
  bases gratuitas caducan (~30 días).
- **CI** ejecuta tests y comprobaciones, pero el despliegue no depende de que
  pasen: configurar *branch protection* o el chequeo obligatorio en Render.

## 7. Cambiar de dominio

Se puede cambiar de dominio **sin tocar la base de datos, los asientos, las
facturas emitidas ni las fotos**: los archivos se guardan con rutas relativas y
el código no contiene ningún dominio escrito a mano. El coste es de
configuración y DNS, no de migración.

### Qué no cambia

- Datos contables, ventas, vehículos, facturas ya emitidas y usuarios.
- Archivos subidos: se guardan como `vehiculos/<matricula>/...` y similares.
- Código: `ALLOWED_HOSTS` se lee del entorno.

### Qué hay que cambiar

1. **Render → Settings → Custom Domain**: añadir el dominio nuevo. Mientras se
   convive con el anterior, dejar los dos.
2. **DNS**: el registro que indique Render (CNAME a `onrender.com` para `www`,
   ALIAS/ANAME o A para el dominio raíz). El certificado TLS lo emite Render.
3. **`ALLOWED_HOSTS`** en Render: añadir el dominio nuevo separado por comas,
   p. ej. `rogil.co,www.rogil.co`.
4. **`CSRF_TRUSTED_ORIGINS`** (solo si se sirve desde varios dominios a la vez):
   `https://rogil.co,https://www.rogil.co`.
5. **Redirecciones 301** del dominio viejo al nuevo para no perder enlaces ni
   posicionamiento, y actualizar los enlaces de los portales (Coches.net,
   AutoScout24) y de UptimeRobot.
6. **Correo**: si se envía desde el dominio nuevo, actualizar
   `DEFAULT_FROM_EMAIL` y los registros SPF/DKIM del dominio.

### Dos avisos importantes

- **HSTS preload**: el sistema envía HSTS de un año. Mientras el dominio sea
  temporal, poner `HSTS_PRELOAD=false`. Meter un dominio en la lista de preload
  de los navegadores es prácticamente irreversible durante un año.
- **Dominio de los archivos (R2)**: si la media se sirve con un subdominio
  propio (p. ej. `media.rogil.co`), cambiarlo implica actualizar
  `AWS_S3_CUSTOM_DOMAIN` y reiniciar el servicio. Los archivos **no se mueven**;
  solo cambia la URL base con la que se sirven.

### Orden recomendado

1. Registrar/desbloquear el dominio definitivo.
2. Dejar el temporal (`rogil.co`) funcionando y **sin preload de HSTS**.
3. Cuando llegue el definitivo: añadirlo en Render, DNS, `ALLOWED_HOSTS` y
   `CSRF_TRUSTED_ORIGINS`; convivir unos días con ambos.
4. Poner la redirección 301 del temporal al definitivo y, cuando esté
   verificada, retirar el temporal de Render.

## 8. Dominio rogil.co — puesta en marcha

### Estado detectado

`rogil.co` está delegado a los servidores de nombres de **AWS Route 53**
(205.251.192.139, 205.251.195.69, 205.251.196.64, 205.251.199.227), pero esos
servidores responden **REFUSED**: la zona DNS no existe o no está publicada.
Por eso el dominio no resuelve todavía.

**Conclusión: el primer paso es publicar la zona DNS, no tocar la aplicación.**
Hasta que el dominio no resuelva, Render no puede emitir el certificado.

### Opción A (recomendada): DNS en Cloudflare

Motivo: es gratis, da CDN y es el mismo sitio donde irá R2 para las fotos.

1. Añadir `rogil.co` a Cloudflare (plan Free) y copiar los dos servidores de
   nombres que asigna.
2. Cambiar los servidores de nombres en el registrador (donde se compró el
   dominio) por los de Cloudflare.
3. Crear estos registros:

   | Nombre | Tipo | Destino | Proxy |
   |---|---|---|---|
   | `rogil.co` | CNAME | `eurocar-jdx2.onrender.com` | Nube gris al principio |
   | `www` | CNAME | `eurocar-jdx2.onrender.com` | Nube gris al principio |
   | `staging` | CNAME | `eurocar-staging-jdx2.onrender.com` | Nube gris |
   | `media` | CNAME | (cuando exista R2) | Nube naranja |

   Cloudflare permite CNAME en el dominio raíz (CNAME flattening), así que no
   hace falta dirección IP fija.

4. Dejar el proxy **desactivado** (nube gris) hasta que Render emita el
   certificado. Después se puede activar con SSL/TLS en *Full (strict)*.

### Opción B: seguir en Route 53

Crear o reparar la hosted zone de `rogil.co`, copiar sus 4 servidores de nombres
al registrador y añadir allí los mismos registros de la tabla.

### En Render

1. **Settings → Custom Domain**: añadir `rogil.co` y `www.rogil.co` al servicio
   de producción, y `staging.rogil.co` al de staging.
2. Esperar a que el certificado aparezca como emitido (minutos).
3. En el servicio de **producción**, variables de entorno:

   ```
   ALLOWED_HOSTS=rogil.co,www.rogil.co,eurocar-jdx2.onrender.com
   CSRF_TRUSTED_ORIGINS=https://rogil.co,https://www.rogil.co,https://eurocar-jdx2.onrender.com
   HSTS_PRELOAD=false
   ```

   Mantener los hosts de `onrender.com` evita quedarse fuera si algo falla con
   el dominio nuevo. `HSTS_PRELOAD=false` porque `rogil.co` es temporal.

4. Redeploy (Manual Deploy) para aplicar las variables.

### Orden importante

Las variables `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` deben estar puestas
**antes** de apuntar el DNS al servicio. Si se invierte el orden, el dominio
responde `400 Bad Request` (DisallowedHost) y parece que está roto.

### Verificación

```bash
curl -I https://rogil.co                     # 200 o 301, con TLS válido
curl -fsS https://rogil.co/api/ping/         # OK
curl -fsS -o /dev/null -w '%{http_code}\n' https://www.rogil.co/erp/   # 200
```

Y en el navegador: entrar al ERP con `admin`, subir una foto a un vehículo
(paso 8 del protocolo) y comprobar que la imagen se ve en el catálogo.

### Staging primero

`render.yaml` ya deja `staging.rogil.co` en `ALLOWED_HOSTS` y
`CSRF_TRUSTED_ORIGINS` del servicio de staging, para probar el dominio sin
tocar producción. Cuando funcione en staging, se replica en producción.

## 9. Servidores: Render en Fráncfort

**Decisión: Render, región `frankfurt`, con PostgreSQL gestionado y R2 para la
media.** Es lo que define `render.yaml`.

### Por qué Fráncfort y no Oregón

Madrid → Oregón son ~150 ms por petición y este ERP **renderiza en servidor**:
cada clic paga ese peaje. Fráncfort está a ~30-40 ms, y los datos quedan en la UE.

### Por qué Render y no un VPS

El repositorio ya está construido para Render: `Procfile`, `render.yaml`, CI,
WhiteNoise sin manifest y el respaldo `xhtml2pdf` para el runtime nativo (que no
trae Pango/Cairo). Render aporta TLS y despliegues automáticos, rollback y cero
administración de sistema operativo.

Un VPS (Hetzner ~5,49 €, o IONOS en España) es más barato, pero exige parchear
el sistema, emitir y renovar certificados (hoy `docker/nginx/ssl/` está vacío, así
que el compose de producción no arrancaría), vigilar el disco y probar
restauraciones. Con un equipo no técnico en Madrid, el ahorro no compensa el
riesgo de una caída sin nadie que la atienda.

### Planes

- **Producción: plan de pago.** El gratuito suspende el servicio por inactividad
  y su base caduca a los ~30 días; eso ya provocó una caída.
- **Staging: gratuito** a propósito. Se suspende y su base caduca, pero para
  pruebas puntuales se vuelve a sembrar con `create_test_users.py`.

Coste orientativo: producción son dos recursos de pago (servicio web + base de
datos). Confirma el precio actual en el dashboard antes de contratar.

### Migración desde Oregón

La **región de un servicio ya creado no se puede cambiar**. Hay que crear los
servicios nuevos en `frankfurt` y retirar los viejos:

1. Crear el servicio de producción en `frankfurt` (o sincronizar el blueprint).
2. Crear una base de datos nueva en `frankfurt` y apuntar `DATABASE_URL`.
3. Si hay datos que conservar del entorno anterior: `pg_dump` → `pg_restore`.
4. Comprobar `/api/ping/` y el login.
5. Retirar el servicio antiguo de Oregón.

### Dos bases de datos separadas

Hoy staging y producción comparten una sola PostgreSQL: un `migrate` en staging
afecta a producción. Al recrear en Fráncfort, crear **dos bases independientes**.

### Sin método de pago (situación actual)

Render retiró la tarjeta del workspace: **no se pueden crear servicios de pago
y no queda ningún servicio activo** (las URL antiguas devuelven 404).

Mientras eso no se resuelva, hay una vía que no necesita tarjeta y cubre lo
inmediato: **desplegar solo staging gratuito** para que Madrid ejecute la prueba.

- `render.yaml` define únicamente el servicio `eurocar-staging` (plan free); el
  bloque de producción está comentado al final del archivo, listo para
  reactivar.
- Hace falta **una base de datos gratuita** y un servicio web gratuito, ambos en
  Fráncfort. Comprueba cuántas bases gratuitas permite tu workspace; si solo
  permite una, esa es la de staging.
- Límites que hay que tener presentes: el servicio **se duerme** por inactividad
  (el primer acceso tarda 30-60 s) y la base gratuita **caduca a los ~30 días**.

### Reactivar producción cuando haya tarjeta

1. Añadir el método de pago en Render. Si el panel no deja («temporarily
   prevents adding a new card»), abrir un ticket a soporte de Render: es un
   bloqueo de la cuenta, no del proyecto.
2. Crear una base de datos **de pago** en Fráncfort (`rogil-db`).
3. Descomentar el bloque de producción en `render.yaml` y aplicar el blueprint.
4. Si la base gratuita tuviera datos que conservar:
   `pg_dump` de la gratuita → `pg_restore` en la de pago.
5. No se puede saltar el paso 2: una base gratuita caduca y no debe sostener
   datos reales.

### Datos reales solo con base de pago

La prueba de Madrid puede correr en staging gratuito. **Los datos del negocio
—ventas, facturas, asientos— no deben vivir en una base gratuita**, porque a los
~30 días desaparece.
