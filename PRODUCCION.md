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

## 6. Riesgos que quedan abiertos

- **Base de datos compartida** entre staging y producción: un `migrate` en
  staging afecta a producción. Separar antes de manejar datos reales.
- **Sin monitorización de errores** (no hay Sentry): los fallos solo se ven en
  los logs de Render.
- **Plan gratuito de Render**: el servicio se suspende por inactividad y las
  bases gratuitas caducan (~30 días).
- **CI** ejecuta tests y comprobaciones, pero el despliegue no depende de que
  pasen: configurar *branch protection* o el chequeo obligatorio en Render.
