# AGENTS.md

Repo root = `vcte5000/`. All path-relative commands below assume this as the working directory.

## Architecture

- **`backend/`** — Django 4.2.8 ERP (server-rendered + HTMX middleware). **`frontend/`** — Vue 3 + Vite 5 + Tailwind CSS 3 SPA → builds into `backend/static/web/` (base path `/static/web/`); dev server :3000 proxies `/api` + `/media` → :8000.
- `docker-compose.yml`: 5 services — `db` (Postgres 15), `redis`, `backend`, `celery_worker`, `nginx`.
- Python 3.11.9 (`.python-version`). 12 backend apps under `apps/` — import as `apps.<name>`. `apps.api` is **not** in `INSTALLED_APPS` but works because its `urls.py` is imported directly. `apps.payroll` also exists (route `/erp/nominas/`).
- `soportes madrid/` — sample PDF/CSV supporting documents (facturas, extractos bancarios) used by test and simulation scripts.
- `backend/manual/` — user manuals (`manual.html` full manual, `roger.html` operator view). The §20 pipeline scripts (`test_pipeline_capitulo20.py`, `simulacion_capitulo20.py`) implement "capítulo 20" of that manual.
- Utility scripts (root unless noted): `create_test_purchase.py` (seeds catalog materials + multi-material `CompraMaterial`), `fix_inversion_banco.py` (one-off `InversionInicial` bank repair; header has the staging variant), `backend/create_missing_warranties.py` (backfills `GarantiaVehiculo` for existing sales), `backend/generate_manual.py` / `generate_manual_xhtml2pdf.py` (regenerate `media/manual_eurocar_erp.pdf`; on this Windows machine weasyprint lacks GTK libs — use `generate_manual_xhtml2pdf.py`), `backend/manual/ejemplos/gen_soportes_madrid.py` (regenerates the `soportes madrid/` capítulo-20 PDFs). CLI uploads: `manage.py subir_factura_gasto --pk <id> --pdf <file>` (adjunta factura de proveedor a un `GastoEstructura`), `manage.py subir_imagen_vehiculo --matricula <m> --imagen <file>` (solo `EN_VENTA`).
- Settings in `config/settings/`: `development` (default; SQLite unless `DATABASE_URL`), `staging` (no Redis: locmem cache, Celery eager, WhiteNoise; media local/ephemeral on purpose), `production` (S3 media only if `AWS_STORAGE_BUCKET_NAME`; Redis optional → locmem + eager fallback). Root test scripts set `DJANGO_SETTINGS_MODULE=config.settings.development` themselves.
- Root `README.md` is generic marketing and partially stale (says `cd eurocar`; repo dir is `vcte5000`) — trust this file and the code over it.

Routing (`backend/config/urls.py:7-28`): ERP under `/erp/*`, API at `/api/`, admin at `/admin/`. **Catch-all `spa_index` must stay last** — serves the Vue SPA for unmatched paths.

Frontend CSS changes require a full `npm run build` (Vite → PostCSS → Tailwind). The dev server uses HMR for JS/Vue but can miss Tailwind-only rebuilds.

Agent instruction sources beyond this file: `.claude/skills/` contains TestSprite skills (`testsprite-onboard`, `testsprite-verify`) for automated test generation and verification workflows.

## Key views

- **`/api/*` dual-mode**: returns HTML when `Accept: text/html`, else JSON (`apps/api/urls.py:11` `is_html_request`). Keep both branches working.
- **`/api/*` is fully anonymous**: no DRF viewsets — hand-rolled function views only (`apps/api/urls.py:197-203`): `health/`, `ping/` (plain "OK", no DB), `vehiculos/`, `vehiculos/<pk>/`, `marcas/` (listings filtered to `EN_VENTA` + `precio_venta>0`). DRF's `IsAuthenticated` default doesn't apply to function views; `test_modules.py` asserts `/api/vehiculos/` → 200 unauthenticated — don't "protect" them.
- **SPA works only after `npm run build`**: `spa_index` serves `STATIC_ROOT/web/index.html`, else 404 "Web pública no construida" (`apps/core/views.py:94-100`). Build artifacts (`backend/static/web/`) are git-ignored but **force-committed** (`git add -f`) so the public catalog works at `/` on Render — after ANY frontend change, rebuild and re-commit them. Deep links (`/catalogo`, `/vehiculo/<id>`, `/tasacion`, `/contacto`) hit the `spa_index` catch-all (vue-router history mode).
- **Roles** (`accounts.User.rol`): `ADMIN`, `OPERARIO`, `VENDEDOR`, `GESTORIA`. Use `user.is_admin` / `is_operario` / `is_vendedor` / `is_gestoria` properties — never raw `rol` comparisons.

## Commands (run from repo root unless noted)

| What | Command |
|------|---------|
| All services | `docker-compose --env-file .env.production up -d` (see Docker gotchas) |
| Django mgmt (Docker) | `docker-compose exec backend python manage.py <cmd>` |
| Django mgmt (local) | `cd backend && python manage.py <cmd>` |
| Create test users | `python create_test_users.py` (required before tests) |
| Django unit tests | `cd backend && python manage.py test` (isolated test DB) |
| Integration tests | `python test_modules.py` (needs test users + `migrate` first) |
| Report data check | `python check_report_data.py` (needs dev data + `migrate`) |
| Frontend deps | `cd frontend && npm install` (required before `dev`/`build`) |
| Frontend dev server | `cd frontend && npm run dev` (port 3000, proxies `/api`, `/media` → :8000) |
| Build frontend | `cd frontend && npm run build` → `backend/static/web/` (**commit the artifacts** with `git add -f` — the public web serves from them) |
| Full sample data | `python create_full_test.py` (after test users) |
| Tester user (staging/prod) | `python create_tester_user.py` (`--reset-password`, `--delete`) — user `tester` / `TestMadrid2024!` |
| Prod users (6, adds `roger`) | `python create_users_prod.py` (sets `config.settings.production` itself; works from repo root) |
| Seed users (Docker) | `docker-compose exec backend python manage.py seed_users` (5 users, same creds/PINs as `create_test_users.py`, no `roger`) |
| Regularización existencias | `cd backend && python manage.py regularizar_existencias --ano 2025` (asiento PGC 300/611) |
| Backfill asientos banco | `cd backend && python manage.py backfill_asientos_banco` (retroactive asientos for INGRESO movements) |
| §20 pipeline (safe) | `python test_pipeline_capitulo20.py` (needs test users only; runs in a rolled-back transaction against the dev DB) |
| §20 full simulation (**destructive**) | `python simulacion_capitulo20.py` — deletes `db.sqlite3`, runs `migrate --run-syncdb`, recreates everything |

**No lint/typecheck/format gates exist**. Only CI: `.github/workflows/backup.yml` (daily pg_dump). `render.yaml` defines the Render deploy; `Procfile` starts gunicorn.

## Testing

No pytest:

- **Django test runner** (`cd backend && python manage.py test`) — isolated test DB, 70 tests (~90s), 1 skipped on SQLite (`workshop/tests.py:72`, in-memory client limitation). Coverage: `accounting/tests.py` = report logic (Diario, Mayor con saldo corrido, Existencias, Balance con cuadre + desglose, PyG, IVA, Comparativa) + all 8 report views; `expenses/tests.py` = `GastoEstructura`; `workshop/tests.py` = OTs, operario dropdown, compras (crédito/contado per `forma_pago`), filtro de búsqueda del listado de OTs (título/descripción). SQLite needs `sales/0004_trigger_inmutabilidad` vendor-aware (skips the Postgres-only trigger). Subaccount `4751.115` (retención IRPF) is in the base PGC (56 cuentas); `expenses/tests.py` seeds it defensively anyway.
- **Integration smoke** (`python test_modules.py`) — Django `Client` vs dev DB, run from root (sets `config.settings.development`, inserts `backend/` into `sys.path`). `/erp/` paths + `FINANCIAL REPORTS` section; 54 checks. Needs test users + `migrate`.
- **Data check** (`python check_report_data.py`) — runs the report generators against real dev data and asserts the Balance squares (Activo = Pasivo + Patrimonio) and that every posted asiento is balanced.
- **Full simulation** (`python simulacion_capitulo20.py`) — **DESTRUCTIVE**: deletes `db.sqlite3`, re-migrates with `--run-syncdb`, runs the complete §20 pipeline (bug fixes #1-#26, payroll, IVA 303, Ley Antifraude gasto editing). No transaction rollback — the DB is nuked; only for clean-slate verification.

Test users from `create_test_users.py`:

| Username | Role | Password |
|----------|------|----------|
| `admin` | ADMIN | `admin123!` |
| `mecanico1` | OPERARIO (PIN 1234) | `mecanico123!` |
| `mecanico2` | OPERARIO (PIN 5678) | `mecanico123!` |
| `vendedor1` | VENDEDOR | `vendedor123!` |
| `gestoria1` | GESTORIA | `gestoria123!` |

`backend/create_test_users.py` delegates to the root script; both use `update_or_create` + password reset, so stale test accounts self-repair.

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

- **Export views** live in `apps/accounting/export_views.py` (not `reports.py`): `exportar/` CSV (303/390) + SII XML, plus `tareas_programadas`/`crear_tareas_por_defecto` (manage the Celery-beat schedule). Generators: `apps/accounting/exports.py` (`generar_modelo_390` BOE flat file, `generar_csv_pre303`, `generar_sii_xml`). The informes list renders 9 cards (8 reports + `tareas`; asserted by `test_informes_list_9_tarjetas`). Periodic tasks: `@shared_task`s in `apps/accounting/tasks.py` (`liquidar_iva_trimestral`, `cierre_anual`, `generar_archivos_fiscales`, `generar_sii`, `generar_cuotas_seguridad_social`) — eager on staging.

## Gotchas

- **Custom User** = `accounts.User` (`AUTH_USER_MODEL`). Import from `apps.accounts.models`, never `django.contrib.auth`.
- **`User.puede_eliminar`** (default True) gates delete permission. `rol` default is `'OPERARIO'` (`accounts/models.py:19`); migration `0003_alter_user_rol` briefly set the DB default to `'ADMIN'` and `0004_alter_user_rol` aligned it back to `'OPERARIO'` — if you add another `AlterField`, keep the model default in sync. The login view auto-repairs empty `rol` to `'ADMIN'` for staff users. `is_admin`/`is_operario`/`is_vendedor`/`is_gestoria` properties also return True for any `is_superuser`, so a `createsuperuser` user passes every role check.
- **Keep `base.py:5-14` monkey-patch** of `BaseContext.__copy__` (Python 3.14 compat even though we run 3.11).
- **`debug_toolbar` removed** — incompatible with Python 3.14. Don't re-add.
- **`.env` split**: `backend/.env` is read by Django (`base.py:23`). Root `.env.example` is for docker-compose only.
- **Spanish number formats**: `base.py` sets `USE_THOUSAND_SEPARATOR=True` + `FORMAT_MODULE_PATH=['config.formats']` (`config/formats/es/formats.py`: `.` thousands, `,` decimals → `8.294,00`). Templates render amounts in this format; tests asserting exact amount strings must match it.
- **Dual account locking**: manual (5 attempts → 1h lock) + `django-axes` (`AXES_FAILURE_LIMIT=5`, `AXES_COOLOFF_TIME=1`). Both active.
- **`django-csp`** in `INSTALLED_APPS` (no custom `CSP_*` settings). Default CSP blocks inline `<script>`/`<style>` — use nonces or external files.
- **Session**: expires in 1h and on browser close. `SESSION_SAVE_EVERY_REQUEST=True`.
- **`django-cleanup`** auto-deletes orphaned files when records are removed.
- **Development** has `AUTH_PASSWORD_VALIDATORS = []` — weak passwords work locally but not in production.
- **`SECRET_KEY` has no default** (`base.py:25`) — local Django runs fail without `backend/.env`; Docker works zero-config (compose supplies an insecure dev fallback). Several migrations (e.g. accounts `0003`, vehicles `0007`) were generated by Django 6.0.7 — never run `makemigrations` with anything newer than the pinned 4.2.8.
- **Production degrades gracefully without Redis** (`production.py`): if the `REDIS_URL` env var is absent, cache falls back to locmem and `CELERY_TASK_ALWAYS_EAGER=True` + broker/result `None` (same pattern as staging). Set `REDIS_URL` on Render only if a Redis instance is actually provisioned.
- **Bank movements** are never created manually — `apps.bank.services.crear_movimiento_banco()` is the single entry point; `BancoCuenta.saldo` is computed on-the-fly. All reconciliation logic (`conciliar_extracto`, `conciliacion_bancaria_sugerencias`, `marcar_conciliado`, `conciliacion_batch`) lives in `apps/bank/services.py`.
- **Vehicle images**: uploads only allowed while `estado='EN_VENTA'`; changing the estado away from `EN_VENTA` deletes `imagen_principal` + all gallery images. Max 8 per vehicle (formset `max_num=8`, `apps/vehicles/forms.py:201`).
- **Workshop stock** in via `CompraMaterial`. `save()` updates stock + invoice amounts, but the view explicitly calls `crear_asiento_contable()` and posts it if balanced (the model doesn't auto-post). Crédito by default: asiento DEBE 300/310/320/330 + 472 / HABER 410, no bank movement. `forma_pago` (FK `CuentaContable`, limited to 410/570/572) switches to contado: 572 → HABER 572 + EGRESO via `crear_movimiento_banco()` (saldo pre-validated in `views_material.py` before the atomic block); 570 → caja, no bank movement. The whole factura is one atomic block — any error rolls back every line.
- **Accounting entries are not auto-generated by `save()`**. Models expose a `crear_asiento_contable()` method that views/services call explicitly. Bank movements are likewise created by explicit calls (`registrar_movimiento_banco()` or `apps.bank.services.crear_movimiento_banco()`), not signals.
- **`GastoEstructura` auto-posts** when balanced (like `InversionInicial`). Other auto-creations: warranty cost transfer (`apps/expenses/services.py:transferir_coste_garantia()`, from `apps/warranty/views.py`); the monthly SS task (`generar_cuotas_seguridad_social`, `apps/accounting/tasks.py`) instead creates a BORRADOR 642/572 with no movements (not auto-posted). Pending in 410 until `pagado=True`, which auto-generates the payment asiento (`PagoGastoEstructura`: DEBE 410 / HABER 570-572, idempotent) + EGRESO via `crear_movimiento_banco()` (572 only, never caja 570). Unmarking reverses it (`AnulacionPagoGasto` + `_anular_asiento_pago`, `apps/expenses/views.py`, which also deletes the linked EGRESO).
- **61x counts in the result** (PyG `variacion_existencias` + Balance `resultado_ejercicio`): OT completion credits 611 for capitalized labor (DEBE 310) and operario payroll is never posted, so excluding 61x descuadra the Balance by the labor amount.
- **Vehicle purchase**: `save()` auto-calculates `coste_inicial` from the cost fields. The create/update view then explicitly calls `crear_asiento_contable()` and `registrar_movimiento_banco()`.
- **Sales payments** (`CobroFraccionado`, migration `sales/0006`): plazos go PENDIENTE→RECIBIDO; `cobro_recibir` calls `CobroFraccionado.recibir()` which generates the asiento. `VentaVehiculo.pagada` auto-flips when `total_cobrado >= precio_venta` (recomputed from RECIBIDO cobros).
- **Stray git-tracked logs**: `backend/server_out.txt` / `server_err.txt` are leftover local runserver output dumps, not config — ignore or delete them. `backend/test_staging.db` is a stray SQLite file (git-ignored), same treatment.
- **Windows console encoding**: repo files are UTF-8 Spanish; PowerShell 5.1 `Get-Content`/console output shows mojibake accents (`García` → `García`). Cosmetic only — don't "repair" the files.
- **Docker Postgres password**: compose substitutes `POSTGRES_*`/`SECRET_KEY` from shell vars or root `.env`; this machine runs `--env-file .env.production` (`POSTGRES_DB=eurocar_prod`, password ≠ compose default `eurocar_dev_2024`). The `pgdata` volume keeps the password from first init — recreating containers with a different env breaks backend auth (FATAL: password authentication failed). Always start/restart with the same env file.
- **Dev nginx** mounts only `docker/nginx/default.conf` — never the whole dir (`prod.conf` is for `docker-compose.prod.yml`, needs SSL certs in `docker/nginx/ssl/`, and crashes dev nginx without them). After recreating `backend`, `docker-compose restart nginx` to re-resolve the upstream IP (else 502).

## Production Deploy

Deployed on **Render** (Python runtime, not Docker). Self-hosted alternative: `docker-compose.prod.yml`. Render build: `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate`. Start: `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120`.

- **Two deploy targets**: `render.yaml` defines the **staging** service (branch `staging`, `DJANGO_SETTINGS_MODULE=config.settings.staging`). `master` is the main branch (`origin/HEAD` → `master`); production deploys from it via the Render dashboard (not in-repo, **no auto-deploy** — push alone does not deploy production). The current repo branch is `staging`.
- **Render URLs + shared DB**: real services are `eurocar-staging-jdx2.onrender.com` (staging; login `tester` / `TestMadrid2024!`) and `eurocar-jdx2.onrender.com` (production). **`eurocar.onrender.com` / `eurocar-staging.onrender.com` (no `-jdx2`) are ghost services with stale `DATABASE_URL`s — any DB endpoint 500s there; never use them.** Both apps share ONE PostgreSQL (`eurocar-db-jdx2`): a `migrate` on either branch affects both — consider splitting when staging data matters. Root `/` serves the committed SPA catalog; the ERP lives under `/erp/`. If a DB endpoint 500s while `/api/ping/` is 200: stale `DATABASE_URL` (free-tier DBs expire ~30 days) or a deploy that didn't apply (Render can show "Live" while serving the old instance) — fix via *Manual Deploy → Clear build cache & deploy* after fixing the env var. Staging auto-deploys from `staging`; production deploys manually from `master`.
- **`docker-compose.prod.yml` (self-hosted)** requires: `.env.production` (see `.env.production.example` — must include `DJANGO_SETTINGS_MODULE=config.settings.production`, else `wsgi.py`/`celery.py` default to development), SSL certs in `docker/nginx/ssl/` (`fullchain.pem` + `privkey.pem`), `docker/nginx/prod.conf` (HTTP→HTTPS redirect). Backend runs `migrate` + `collectstatic` at boot; SPA is built inside `backend/Dockerfile.prod` (no `vue_data` volume — an empty named volume would shadow the built SPA).
- **Env vars by environment**: dev = `backend/.env` (`SECRET_KEY` mandatory). Staging/Render = `SECRET_KEY`, `DATABASE_URL`, `DEBUG`, `ALLOWED_HOSTS` (in `render.yaml`); no `REDIS_URL`/`AWS_*`. Production/Render (manual §12.5-12.6) = same + `AWS_*` (R2 media) + `EMAIL_*` (SMTP); `REDIS_URL` optional (graceful fallback).
- **Staging media stays local/ephemeral intentionally** (cost saving) — `staging.py` has no S3 block; don't "fix" it. The SPA artifacts (`backend/static/web/`) are committed, so the public catalog serves at `/` on staging/prod; keep `collectstatic` in the Render build (it copies `static/web/` into `staticfiles/web/` for `spa_index`).
- **WhiteNoise without manifest**: `STATICFILES_STORAGE = CompressedStaticFilesStorage` (staging + production) — intentional. The Vite `index.html` references assets by name (`/static/web/assets/...`); the manifest storage renames files and would break the SPA. Django's own statics lose hash cache-busting (cosmetic).
- **Staging quirks** (`config/settings/staging.py`): Celery tasks run eagerly/sync — don't assume a Celery worker or Redis-backed cache there.
- **Auto-Deploy**: push to the service's configured branch. If a push doesn't go live, click **Manual Deploy → Clear build cache & deploy**.
- **Ephemeral filesystem**: uploaded media lost on redeploy. Persist via R2 (set `AWS_STORAGE_BUCKET_NAME` to activate `storages.backends.s3.S3Storage` in `production.py:33`). Bucket must be public (`AWS_QUERYSTRING_AUTH=False`).
- UptimeRobot pings `https://<app>.onrender.com/api/ping/` every 10 min to avoid cold starts (`/api/ping/` returns plain-text "OK", no DB access — also Render's `healthCheckPath`). DB backed up daily by `.github/workflows/backup.yml`.
