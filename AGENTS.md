# AGENTS.md

## Architecture

- **`backend/`** — Django 4.2.8 ERP (server-rendered + HTMX). **`frontend/`** — Vue 3 + Vite SPA, builds into `backend/static/web/`. README wrongly says "Nuxt 3".
- `docker-compose.yml`: 5 services — `db` (Postgres 15), `redis`, `backend`, `celery_worker`, `nginx`.
- Python 3.11.9 (`.python-version`). Backend apps under `apps/` — import as `apps.<name>`. `apps.api` is **not** in `INSTALLED_APPS` but works because its `urls.py` is imported directly.

Routing (`backend/config/urls.py:7-27`): ERP under `/erp/*`, API at `/api/`, admin at `/admin/`. **Catch-all `spa_index` must stay last** — serves the Vue SPA for unmatched paths.

## Key views

- **`/api/*` dual-mode**: returns HTML when `Accept: text/html`, else JSON (`apps/api/urls.py:11` `is_html_request`). Keep both branches working.
- **SPA only after `npm run build`**: `spa_index` reads `STATIC_ROOT/web/index.html` and 404s "Web pública no construida" otherwise (`apps/core/views.py:94-100`).
- **Roles** (`accounts.User.rol`): `ADMIN`, `OPERARIO`, `VENDEDOR`, `GESTORIA`. Use `user.is_admin` / `is_operario` / `is_vendedor` / `is_gestoria` properties — never raw `rol` comparisons.

## Commands (run from repo root unless noted)

| What | Command |
|------|---------|
| All services | `docker-compose up -d` |
| Django mgmt (Docker) | `docker-compose exec backend python manage.py <cmd>` |
| Django mgmt (local) | `cd backend && python manage.py <cmd>` |
| Create test users | `python create_test_users.py` (required before tests) |
| Django unit tests | `cd backend && python manage.py test` (isolated test DB) |
| Integration tests | `python test_modules.py` (needs test users + `migrate` first) |
| Report data check | `python check_report_data.py` (needs dev data + `migrate`) |
| File I/O tests | `python -m unittest test_io.py` |
| §20 pipeline test | `python test_pipeline_capitulo20.py` (needs Docker Postgres + test users) |
| Frontend dev server | `cd frontend && npm run dev` (port 3000, proxies `/api`, `/media` → :8000) |
| Build frontend | `cd frontend && npm run build` → `backend/static/web/` |
| Full sample data | `python create_full_test.py` (after test users) |

**No lint/typecheck/format gates exist**. Only CI: `.github/workflows/backup.yml` (daily pg_dump). `render.yaml` defines the Render deploy; `Procfile` starts gunicorn.

## Testing

No pytest. Three layers:

- **Django test runner** (`cd backend && python manage.py test`) — isolated test DB, 45 tests. `apps/accounting/tests.py` covers the report logic (Diario, Mayor con saldo corrido, Existencias, Balance con cuadre + desglose, PyG, IVA, Comparativa) and all 9 report views; `apps/expenses/tests.py` covers `GastoEstructura`. For the runner to work on SQLite: `sales/0004_trigger_inmutabilidad` is vendor-aware (skips the Postgres-only trigger on non-Postgres) and `expenses/tests.py` seeds subaccount `4751.115` for the retención branch.
- **Integration smoke** (`python test_modules.py`) — Django `Client` against the dev DB, runs from repo root (sets `DJANGO_SETTINGS_MODULE=config.settings.development`, inserts `backend/` into `sys.path`). Uses `/erp/`-prefixed paths plus a `FINANCIAL REPORTS` section; 54 checks. Needs test users + `migrate` first.
- **Data check** (`python check_report_data.py`) — runs the report generators against real dev data and asserts the Balance squares (Activo = Pasivo + Patrimonio) and that every posted asiento is balanced.

Test users from `create_test_users.py`:

| Username | Role | Password |
|----------|------|----------|
| `admin` | ADMIN | `admin123!` |
| `mecanico1` | OPERARIO (PIN 1234) | `mecanico123!` |
| `mecanico2` | OPERARIO (PIN 5678) | `mecanico123!` |
| `vendedor1` | VENDEDOR | `vendedor123!` |
| `gestoria1` | GESTORIA | `gestoria123!` |

`backend/create_test_users.py` is stale (hardcoded SQLite path); use the root one.

## Financial Reports

All report logic lives in `apps/accounting/reports.py`; views are in `apps/accounting/report_views.py`. URLs are `/erp/contabilidad/informes/<name>/`.

| Report | URL | Generator function | Template |
|--------|-----|-------------------|----------|
| PyG | `pyg/` | `calcular_pyg()` | `pyg.html` |
| Balance | `balance/` | `calcular_balance()` | `balance.html` |
| IVA / Modelo 303 | `iva/` | `calcular_libro_iva()` | `iva.html` |
| Comparativa anual | `comparativa/` | `calcular_comparativa()` | `comparativa.html` |
| Facturas de compra | `facturas-compras/` | (view logic) | `facturas_compras.html` |
| Libro Diario | `libro-diario/` | `obtener_asientos_diario()` | `libro_diario.html` |
| Libro Mayor | `libro-mayor/` | `obtener_movimientos_cuenta()` | `libro_mayor.html` |
| Valoración existencias | `existencias/` | `obtener_valor_existencias()` | `existencias.html` |

**Key functions in `reports.py`:**
- `obtener_saldo_cuenta(codigo, fecha_desde, fecha_hasta)` — core helper, returns `(debe, haber)` for any account prefix, filtered by date and posted status.
- `obtener_asientos_diario(fecha_desde, fecha_hasta)` — returns all posted `AsientoContable` with their `MovimientoContable` rows, ordered chronologically.
- `obtener_movimientos_cuenta(codigo_cuenta, fecha_desde, fecha_hasta)` — returns all movements for a specific `CuentaContable` with running balance (saldo corrido).
- `obtener_valor_existencias()` — values stock at `stock_actual × precio_unitario` for each `Material`, compares against accounting balance in accounts 300-330.
- `calcular_balance()` — now also passes `cuentas_balance` context with per-account detail for activo no corriente, existencias, clientes, and proveedores.

**Balance template** (`balance.html`) has expandable `<details>` sections showing individual account balances under each category.

## Gotchas

- **Custom User** = `accounts.User` (`AUTH_USER_MODEL`). Import from `apps.accounts.models`, never `django.contrib.auth`.
- **`User.puede_eliminar`** (default True) gates delete permission. `rol` defaults to `'ADMIN'`; `is_admin`/`is_operario`/`is_vendedor`/`is_gestoria` properties fall back to `is_superuser`. A `createsuperuser` user stores `rol=''` — not admin until set.
- **Keep `base.py:5-14` monkey-patch** of `BaseContext.__copy__` (Python 3.14 compat even though we run 3.11).
- **`debug_toolbar` removed** — incompatible with Python 3.14. Don't re-add.
- **`.env` split**: `backend/.env` is read by Django (`base.py:23`). Root `.env.example` is for docker-compose only.
- **Dual account locking**: manual (5 attempts → 1h lock) + `django-axes` (`AXES_FAILURE_LIMIT=5`, `AXES_COOLOFF_TIME=1`). Both active.
- **`django-csp`** in `INSTALLED_APPS` (no custom `CSP_*` settings). Default CSP blocks inline `<script>`/`<style>` — use nonces or external files.
- **Session**: expires in 1h and on browser close. `SESSION_SAVE_EVERY_REQUEST=True`.
- **`django-cleanup`** auto-deletes orphaned files when records are removed.
- **Development** has `AUTH_PASSWORD_VALIDATORS = []` — weak passwords work locally but not in production.
- **Bank movements** are never created manually — `apps.bank.services:crear_movimiento_banco()` is the single entry point. Every financial transaction auto-creates a `BancoMovimiento`. `BancoCuenta.saldo` is computed on-the-fly.
- **Vehicle images**: vehicle must be `EN_VENTA` or images are deleted. Max 8 per vehicle.
- **Workshop stock** only via purchase with invoice (`CompraMaterial`). Auto-posts accounting entry on save.
- **Vehicle purchase**: filling `factura_compra` fields auto-calculates `coste_inicial` and triggers accounting + bank movement.

## Production Deploy

Deployed on **Render** (Python runtime, not Docker). Self-hosted alternative: `docker-compose.prod.yml`. Render build: `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate`. Start: `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120`.

- **Auto-Deploy**: branch must be `master`. Click **Manual Deploy → Clear build cache & deploy** if push doesn't go live.
- **Ephemeral filesystem**: uploaded media lost on redeploy. Persist via R2 (set `AWS_STORAGE_BUCKET_NAME` to activate `storages.backends.s3.S3Storage` in `production.py:32`). Bucket must be public (`AWS_QUERYSTRING_AUTH=False`).
- UptimeRobot pings `https://<app>.onrender.com/api/ping/` every 10 min to avoid cold starts. DB backed up daily by `.github/workflows/backup.yml`.
