# AGENTS.md

Repo root = `vcte5000/`. All path-relative commands below assume this as the working directory.

## Architecture

- **`backend/`** — Django 4.2.8 ERP (server-rendered + HTMX, `django-htmx` middleware active). **`frontend/`** — Vue 3 + Vite 5 + Tailwind CSS 3 SPA, builds into `backend/static/web/` via `vite build`. Vite base path `/static/web/`; dev server on :3000 proxies `/api` + `/media` → :8000.
- `docker-compose.yml`: 5 services — `db` (Postgres 15), `redis`, `backend`, `celery_worker`, `nginx`.
- Python 3.11.9 (`.python-version`). 12 backend apps under `apps/` — import as `apps.<name>`. `apps.api` is **not** in `INSTALLED_APPS` but works because its `urls.py` is imported directly. `apps.payroll` also exists (route `/erp/nominas/`).
- `soportes madrid/` — sample PDF/CSV supporting documents (facturas, extractos bancarios) used by test and simulation scripts.
- `backend/manual/` — user manuals (`manual.html` full manual, `roger.html` operator view). The §20 pipeline scripts (`test_pipeline_capitulo20.py`, `simulacion_capitulo20.py`) implement "capítulo 20" of that manual.
- Utility scripts (run from repo root unless noted): `create_test_purchase.py` seeds catalog materials + a multi-material `CompraMaterial`; `fix_inversion_banco.py` is a one-off `InversionInicial` bank-movement repair (see its header for the staging variant); `backend/create_missing_warranties.py` backfills `GarantiaVehiculo` for existing sales; `backend/generate_manual.py` and `backend/generate_manual_xhtml2pdf.py` regenerate the user-manual PDF (`media/manual_eurocar_erp.pdf`).
- Settings modules in `config/settings/`: `development` (default; SQLite unless `DATABASE_URL` set), `staging` (Render staging: no Redis — locmem cache, Celery eager/sync, WhiteNoise; media local/ephemeral on purpose), `production` (S3 media only when `AWS_STORAGE_BUCKET_NAME` set; Redis optional — falls back to locmem + Celery eager). Root test scripts set `DJANGO_SETTINGS_MODULE=config.settings.development` themselves.
- Root `README.md` is generic marketing and partially stale (says `cd eurocar`; repo dir is `vcte5000`) — trust this file and the code over it.

Routing (`backend/config/urls.py:7-28`): ERP under `/erp/*`, API at `/api/`, admin at `/admin/`. **Catch-all `spa_index` must stay last** — serves the Vue SPA for unmatched paths.

Frontend CSS changes require a full `npm run build` (Vite → PostCSS → Tailwind). The dev server uses HMR for JS/Vue but can miss Tailwind-only rebuilds.

Agent instruction sources beyond this file: `.claude/skills/` contains TestSprite skills (`testsprite-onboard`, `testsprite-verify`) for automated test generation and verification workflows.

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
| Frontend deps | `cd frontend && npm install` (required before `dev`/`build`) |
| Frontend dev server | `cd frontend && npm run dev` (port 3000, proxies `/api`, `/media` → :8000) |
| Build frontend | `cd frontend && npm run build` → `backend/static/web/` |
| Full sample data | `python create_full_test.py` (after test users) |
| Tester user (staging/prod) | `python create_tester_user.py` (`--reset-password`, `--delete`) — user `tester` / `TestMadrid2024!` |
| Prod users (6, adds `roger`) | `DJANGO_SETTINGS_MODULE=config.settings.production python create_users_prod.py` |
| §20 pipeline (safe) | `python test_pipeline_capitulo20.py` (needs Docker Postgres + test users) |
| §20 full simulation (**destructive**) | `python simulacion_capitulo20.py` — deletes `db.sqlite3`, runs `migrate --run-syncdb`, recreates everything |

**No lint/typecheck/format gates exist**. Only CI: `.github/workflows/backup.yml` (daily pg_dump). `render.yaml` defines the Render deploy; `Procfile` starts gunicorn.

## Testing

No pytest. Three layers:

- **Django test runner** (`cd backend && python manage.py test`) — isolated test DB, 63 tests (1 skipped, ~70s). `apps/accounting/tests.py` covers the report logic (Diario, Mayor con saldo corrido, Existencias, Balance con cuadre + desglose, PyG, IVA, Comparativa) and all 8 report views; `apps/expenses/tests.py` covers `GastoEstructura`; `apps/workshop/tests.py` covers la creación de OTs y el desplegable de operarios. For the runner to work on SQLite: `sales/0004_trigger_inmutabilidad` is vendor-aware (skips the Postgres-only trigger on non-Postgres). Subaccount `4751.115` (retención IRPF) is part of the base PGC (54 cuentas) — `expenses/tests.py` still seeds it defensively with `get_or_create`.
- **Integration smoke** (`python test_modules.py`) — Django `Client` against the dev DB, runs from repo root (sets `DJANGO_SETTINGS_MODULE=config.settings.development`, inserts `backend/` into `sys.path`). Uses `/erp/`-prefixed paths plus a `FINANCIAL REPORTS` section; 54 checks. Needs test users + `migrate` first.
- **Data check** (`python check_report_data.py`) — runs the report generators against real dev data and asserts the Balance squares (Activo = Pasivo + Patrimonio) and that every posted asiento is balanced.
- **Full simulation** (`python simulacion_capitulo20.py`) — **DESTRUCTIVE**: deletes `db.sqlite3`, runs `migrate --run-syncdb` from scratch, then executes the complete §20 pipeline covering all bug fixes #1-#26 plus payroll, IVA 303, and Ley Antifraude gasto editing. Does NOT use transaction rollback — the DB is nuked. Use only when you need a clean-slate verification.

Test users from `create_test_users.py`:

| Username | Role | Password |
|----------|------|----------|
| `admin` | ADMIN | `admin123!` |
| `mecanico1` | OPERARIO (PIN 1234) | `mecanico123!` |
| `mecanico2` | OPERARIO (PIN 5678) | `mecanico123!` |
| `vendedor1` | VENDEDOR | `vendedor123!` |
| `gestoria1` | GESTORIA | `gestoria123!` |

`backend/create_test_users.py` is a thin wrapper that delegates to the root `create_test_users.py`; both now use `update_or_create` and reset the password, so stale test accounts are repaired automatically.

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

**Key functions in `reports.py`:** `obtener_saldo_cuenta()`, `obtener_asientos_diario()`, `obtener_movimientos_cuenta()`, `obtener_valor_existencias()`, `calcular_balance()`, `calcular_pyg()`, `calcular_libro_iva()`, `calcular_comparativa()`.

**Balance template** (`balance.html`) has expandable `<details>` sections showing individual account balances under each category.

Accounting also has **export views** in `apps/accounting/export_views.py` (not `reports.py`): `exportar/` CSV for 303/390 + SII XML, plus `tareas_programadas`/`crear_tareas_por_defecto` views that manage the Celery-beat schedule. The periodic tasks themselves are Celery `@shared_task`s in `apps/accounting/tasks.py` (`liquidar_iva_trimestral`, `cierre_anual`, `generar_archivos_fiscales`, `generar_sii`, `generar_cuotas_seguridad_social`) — on staging they run eagerly.

## Gotchas

- **Custom User** = `accounts.User` (`AUTH_USER_MODEL`). Import from `apps.accounts.models`, never `django.contrib.auth`.
- **`User.puede_eliminar`** (default True) gates delete permission. `rol` default is inconsistent: model field says `'OPERARIO'` (`accounts/models.py:19`) but migration `0003_alter_user_rol` sets the DB default to `'ADMIN'` — update both together if you change it. The login view auto-repairs empty `rol` to `'ADMIN'` for staff users. `is_admin`/`is_operario`/`is_vendedor`/`is_gestoria` properties also return True for any `is_superuser`, so a `createsuperuser` user passes every role check.
- **Keep `base.py:5-14` monkey-patch** of `BaseContext.__copy__` (Python 3.14 compat even though we run 3.11).
- **`debug_toolbar` removed** — incompatible with Python 3.14. Don't re-add.
- **`.env` split**: `backend/.env` is read by Django (`base.py:23`). Root `.env.example` is for docker-compose only.
- **Spanish number formats**: `base.py` sets `USE_THOUSAND_SEPARATOR=True` + `FORMAT_MODULE_PATH=['config.formats']` (`config/formats/es/formats.py`: `.` thousands, `,` decimals → `8.294,00`). Templates render amounts in this format; tests asserting exact amount strings must match it.
- **Dual account locking**: manual (5 attempts → 1h lock) + `django-axes` (`AXES_FAILURE_LIMIT=5`, `AXES_COOLOFF_TIME=1`). Both active.
- **`django-csp`** in `INSTALLED_APPS` (no custom `CSP_*` settings). Default CSP blocks inline `<script>`/`<style>` — use nonces or external files.
- **Session**: expires in 1h and on browser close. `SESSION_SAVE_EVERY_REQUEST=True`.
- **`django-cleanup`** auto-deletes orphaned files when records are removed.
- **Development** has `AUTH_PASSWORD_VALIDATORS = []` — weak passwords work locally but not in production.
- **`SECRET_KEY` has no default** (`base.py:25` `env('SECRET_KEY')`) — local Django runs fail without `backend/.env`. Docker works zero-config because `docker-compose.yml` supplies an insecure dev fallback. Note: migration `0003_alter_user_rol` was generated by Django 6.0.7 — never run `makemigrations` with a newer Django than the pinned 4.2.8.
- **Production degrades gracefully without Redis** (`production.py`): if the `REDIS_URL` env var is absent, cache falls back to locmem and `CELERY_TASK_ALWAYS_EAGER=True` + broker/result `None` (same pattern as staging). Set `REDIS_URL` on Render only if a Redis instance is actually provisioned.
- **Bank movements** are never created manually — `apps.bank.services:crear_movimiento_banco()` is the single entry point. `BancoCuenta.saldo` is computed on-the-fly. Bank reconciliation logic (`conciliar_extracto`, `conciliacion_bancaria_sugerencias`, `marcar_conciliado`, `conciliacion_batch`) also lives in `apps/bank/services.py`.
- **Vehicle images**: vehicle must be `EN_VENTA` or images are deleted. Max 8 per vehicle.
- **Workshop stock** changes via `CompraMaterial` (stock input path). `save()` updates stock and computes invoice amounts, but the view explicitly calls `crear_asiento_contable()` and posts it if balanced; the model does not auto-post.
- **Accounting entries are not auto-generated by `save()`**. Models expose a `crear_asiento_contable()` method that views/services call explicitly. Bank movements are likewise created by explicit calls (`registrar_movimiento_banco()` or `apps.bank.services.crear_movimiento_banco()`), not signals.
- **`GastoEstructura` auto-posts** its asiento when balanced (like `InversionInicial`). The only other `GastoEstructura` auto-creation is the warranty cost transfer (`apps/expenses/services.py:transferir_coste_garantia()`, called from `apps/warranty/views.py`); the monthly SS task (`generar_cuotas_seguridad_social` in `apps/accounting/tasks.py`) instead creates a BORRADOR asiento 642/572 with no movements (not auto-posted). Gastos stay pending in account 410 until marked `pagado=True`; that transition auto-generates the payment asiento (`PagoGastoEstructura`: DEBE 410 / HABER 570-572, idempotent) plus an EGRESO bank movement via `crear_movimiento_banco()` (572 only, not caja 570). Unmarking pagado anula the payment asiento (`AnulacionPagoGasto` reversal) and deletes the linked EGRESO (`_anular_asiento_pago` in `apps/expenses/views.py`).
- **61x counts in the result** (PyG `variacion_existencias` + Balance `resultado_ejercicio`): OT completion credits 611 for capitalized labor (DEBE 310) and operario payroll is never posted, so excluding 61x descuadra the Balance by the labor amount.
- **Vehicle purchase**: `save()` auto-calculates `coste_inicial` from the cost fields. The create/update view then explicitly calls `crear_asiento_contable()` and `registrar_movimiento_banco()`.
- **Stray git-tracked logs**: `backend/server_out.txt` / `server_err.txt` are leftover local runserver output dumps, not config — ignore or delete them.

## Production Deploy

Deployed on **Render** (Python runtime, not Docker). Self-hosted alternative: `docker-compose.prod.yml`. Render build: `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate`. Start: `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120`.

- **Two deploy targets**: `render.yaml` defines the **staging** service `eurocar-staging` (branch `staging`, `DJANGO_SETTINGS_MODULE=config.settings.staging`, free plan). `master` is the main branch (`origin/HEAD` → `master`); production deploys from it via the Render dashboard (not in-repo). The current repo branch is `staging`.
- **`docker-compose.prod.yml` (self-hosted alternative)** requires: `.env.production` (see `.env.production.example` — must include `DJANGO_SETTINGS_MODULE=config.settings.production`, otherwise `wsgi.py`/`celery.py` default to development), SSL certs in `docker/nginx/ssl/` (`fullchain.pem` + `privkey.pem`), and `docker/nginx/prod.conf` (HTTP→HTTPS redirect). The backend `command` runs `migrate` + `collectstatic` at boot; the SPA is built inside `Dockerfile.prod` (no `vue_data` volume — an empty named volume would shadow the built SPA).
- **Env var requirements by environment**: dev reads `backend/.env` (`SECRET_KEY` mandatory). Staging/Render panel needs `SECRET_KEY`, `DATABASE_URL`, `DEBUG`, `ALLOWED_HOSTS` (defined in `render.yaml`); `REDIS_URL` and `AWS_*` are NOT set there. Production/Render panel (per `backend/manual/manual.html` §12.5-12.6) needs the same plus `AWS_*` for R2 media and `EMAIL_*` for SMTP; `REDIS_URL` optional (graceful fallback).
- **Staging media stays local/ephemeral intentionally** (cost saving) — `staging.py` has no S3 block; don't "fix" it. The SPA is also never built on Render (`backend/static/web/` is git-ignored and the Render build has no `npm run build` step), so `spa_index` returns 404 "Web pública no construida" on staging/prod unless the build artifacts are committed.
- **Staging quirks** (`config/settings/staging.py`): no Redis — locmem cache, Celery tasks run eagerly/sync, WhiteNoise serves statics. Don't assume a Redis-backed cache or a Celery worker there.
- **Auto-Deploy**: push to the service's configured branch. If a push doesn't go live, click **Manual Deploy → Clear build cache & deploy**.
- **Ephemeral filesystem**: uploaded media lost on redeploy. Persist via R2 (set `AWS_STORAGE_BUCKET_NAME` to activate `storages.backends.s3.S3Storage` in `production.py:33`). Bucket must be public (`AWS_QUERYSTRING_AUTH=False`).
- UptimeRobot pings `https://<app>.onrender.com/api/ping/` every 10 min to avoid cold starts (`/api/ping/` returns plain-text "OK", no DB access — also Render's `healthCheckPath`). DB backed up daily by `.github/workflows/backup.yml`.
