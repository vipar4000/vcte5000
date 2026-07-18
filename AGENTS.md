# AGENTS.md

## Architecture

- **`backend/`** — Django 4.2 ERP, server-rendered with HTMX. Main app.
- **`frontend/`** — Vue 3 + Vite public SPA (catalog, contact). Builds into `backend/static/web/` (see `frontend/vite.config.js:6,21`). README's "Nuxt 3" claim is wrong.
- `docker-compose.yml` runs 5 services: `db` (Postgres 15), `redis`, `backend`, `celery_worker`, `nginx`.

Routing (`backend/config/urls.py`): ERP under `/erp/*` (vehicles, taller, ventas, contabilidad, gastos, etc.), API at `/api/` (raw `JsonResponse`, **not** DRF despite `rest_framework` installed). A catch-all `spa_index` at line 20 serves the Vue SPA for every other path — **keep it last**.

Roles (`accounts.User.rol`): `ADMIN`, `OPERARIO`, `VENDEDOR`, `GESTORIA`. Use `user.is_admin` / `is_operario` / `is_vendedor` / `is_gestoria` properties — never raw `rol` string comparisons.

Backend Django apps live under `apps/` — import as `apps.<name>` (e.g. `apps.vehicles`), not top-level.

## Commands

Run from **repo root** unless noted:

| What | Command |
|------|---------|
| Start all services | `docker-compose up -d` |
| Django mgmt (Docker) | `docker-compose exec backend python manage.py <cmd>` |
| Django mgmt (local) | `cd backend && python manage.py <cmd>` (uses `development` settings; falls back to **SQLite** when `DATABASE_URL` unset) |
| Create test users | `python create_test_users.py` (run before tests) |
| Run integration tests | `python test_modules.py` (needs test users + `migrate` first) |
| Frontend dev server | `cd frontend && npm install && npm run dev` (port 3000, proxies `/api` and `/media` → :8000) |
| Build frontend | `cd frontend && npm run build` → `backend/static/web/` |
| Full sample data | `python create_full_test.py` (after test users) |
| Prod users | `python create_users_prod.py` (`config.settings.production`; creates `roger`, `puede_eliminar=False`) |

## Testing

No pytest. `test_modules.py` (root) uses Django `Client`, loads `config.settings.development` (SQLite by default), must run from repo root. **Stale**: it calls root paths (`/vehiculos/`, `/taller/`, `/gastos/`) but ERP views are now under `/erp/`, so those paths hit the SPA catch-all and fail expectations — fix the paths before trusting results (see `config/urls.py:9-20`). It also checks `/accounts/login/` and `/admin/` which still resolve, so partial results are usable.

Test users (from root `create_test_users.py`):

| Username | Role | Password |
|----------|------|----------|
| `admin` | ADMIN | `admin123!` |
| `mecanico1` | OPERARIO (PIN 1234) | `mecanico123!` |
| `mecanico2` | OPERARIO (PIN 5678) | `mecanico123!` |
| `vendedor1` | VENDEDOR | `vendedor123!` |
| `gestoria1` | GESTORIA | `gestoria123!` |

`roger` (ADMIN, `puede_eliminar=False`, `roger123!`) is created only by `create_users_prod.py` and is **not** in the dev suite. That script also sets `gestoria1` password to `vendedor123!` (differs from dev script). `backend/create_test_users.py` is stale — use the root one.

## Production Deploy

Deployed on **Render** (Python runtime, not Docker). Self-hosted Docker alternative via `docker-compose.prod.yml` (`backend/Dockerfile.prod`, `.env.production`, nginx + SSL in `docker/nginx/prod.conf`).

Render one-time setup: Web Service (Python 3) — build `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate`, start `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120`. Env vars: `DATABASE_URL`, `SECRET_KEY`, `DJANGO_SETTINGS_MODULE=config.settings.production`, `DEBUG=False`, `ALLOWED_HOSTS=.onrender.com,localhost`. Postgres Free plan (90-day trial). UptimeRobot pings `https://<app>.onrender.com/api/ping/` every 10 min to avoid cold starts. DB backed up daily by `.github/workflows/backup.yml` (needs `DATABASE_URL` GitHub secret).

- **Auto-Deploy**: enable in Render → Web Service → Settings → **Auto-Deploy = ON**, **Branch = `master`** (NOT `main`). On push to `master`, Render rebuilds automatically. If a push does NOT go live (Events shows an older commit than `git rev-parse HEAD`), the deploy is stale — click **Manual Deploy → Clear build cache & deploy** to force it. This happened in practice: the running instance stayed on `8725630` while `HEAD` was `4036fc8`, hiding the "🛒 Compras" feature until a manual redeploy.

**Render free tier has an ephemeral filesystem** — uploaded media (vehicle images, invoice PDFs) is lost on redeploy. Persist via R2 (below).

## Media Storage (R2)

Backend activates `storages.backends.s3.S3Storage` when `AWS_STORAGE_BUCKET_NAME` is set (`production.py:32`) — no code change needed; `django-storages` + `boto3` already in `requirements.txt`. Bucket `eurocar`, account `987c5b0d48c2071fcb9c5533c7153a7d`. Enable public access + HMAC R2 token. `AWS_QUERYSTRING_AUTH=False` is hardcoded, so the bucket must stay **public** or media 403s.

Render env vars (web + celery_worker): `AWS_STORAGE_BUCKET_NAME=eurocar`, `AWS_S3_ACCESS_KEY_ID`/`AWS_S3_SECRET_ACCESS_KEY` (R2 token), `AWS_S3_ENDPOINT_URL=https://987c5b0d48c2071fcb9c5533c7153a7d.r2.cloudflarestorage.com`, `AWS_S3_REGION_NAME=auto`, `AWS_S3_CUSTOM_DOMAIN=pub-<hash>.r2.dev`.

## Data-entry workflows (non-obvious)

- **Vehicle images**: vehicle must be `EN_VENTA` or images are discarded/deleted (`apps/vehicles/views.py:89-94,132-135`). UI: admin → `/erp/vehiculos/nuevo/` or `<pk>/editar/`, `ImagenVehiculoFormSet` max 8. Command: `python manage.py subir_imagen_vehiculo --matricula 1234ABC --imagen "C:/fotos/golf.jpg" [--principal]`.
- **Expense PDFs** (`GastoEstructura.documento_pdf`, `is_admin` only): UI `/erp/gastos/nuevo/` or edit; command `python manage.py subir_factura_gasto --pk 12 --pdf "C:/facturas/alquiler.pdf"` (expense must already exist). Don't confuse with REBU `FacturaVenta` PDF, which the system **generates**.
- **Workshop inventory stock** is added only via **purchase with invoice** (`CompraMaterial`), never loose manual entry. Access it via the sidebar **`🛒 Compras`** (admin-only) or Inventario → "🛒 Registrar Compra" button — both link to `workshop:compra_material_create`. The "Registrar Compra" button/links are **admin-only** (`is_admin`). On save it increments `stock_actual` and `crear_asiento_contable()` generates **and auto-posts** a balanced entry (DEBE 300/310/320/330 + 472, HABER 410, `estado='POSTEADO'`) so it appears immediately in the ledger/balance/PyG/IVA reports (`views_material.py:119`). A material can be **created inline** from the purchase form (name + unit) instead of pre-creating it. `MaterialUsado` (in an OT) decrements stock and adds to OT `coste_materiales` → REBU account 623. PGC accounts at `apps/accounting/models.py:184-197`; `generar_numero_asiento` at `apps/accounting/views.py:251`.

## Gotchas

- **Custom User** = `accounts.User` (`AUTH_USER_MODEL`). Import from `apps.accounts.models`, never `django.contrib.auth`.
- **`User.puede_eliminar`** (default True) gates delete permission.
- **`rol` has `default='ADMIN'`** and `is_admin`/`is_operario`/`is_vendedor`/`is_gestoria` all fall back to `is_superuser`. But a user created via `createsuperuser` (README's path) stores `rol=''` in the DB, so it is NOT automatically admin until its `rol` is set — fix existing rows with `User.objects.filter(username='admin').update(rol='ADMIN')`.
- **No lint/typecheck/format/CI test gates** exist (eslint, ruff, flake8, pre-commit all absent). Only CI is `.github/workflows/backup.yml`.
- **Keep the `base.py:5-14` monkey-patch** of `BaseContext.__copy__` (Python 3.14 compat) even though we run 3.11.
- **`.env` split**: root `.env` is read by Django (`base.py:23`) for DB/Redis/secret keys — not just docker-compose. There is no `backend/.env` loading path.
- **Account locking twice**: manual (5 attempts → 1h) + `django-axes` (`AXES_*`). Both active.
- **`django-csp`** active — new inline `<script>`/`<style>` must comply with CSP (use nonces or external files).
- **Session** expires in 1h and on browser close (`SESSION_EXPIRE_AT_BROWSER_CLOSE=True`, `SESSION_SAVE_EVERY_REQUEST=True`).
- **`django-cleanup`** auto-deletes orphaned files when records are removed.