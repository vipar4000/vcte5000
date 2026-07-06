# AGENTS.md

## Architecture

Two separate apps running side by side:

- **`backend/`** — Django 4.2 ERP (server-rendered with HTMX). Main application.
- **`frontend/`** — Vue 3 + Vite public website (catalog, contact). Builds into `backend/static/web/`.

Backend serves ERP pages at `/` via Django templates. The public Vue site is a separate concern.

`docker-compose.yml` runs five services: `db` (Postgres), `redis`, `backend`, `celery_worker`, and `nginx`. The backend service auto-migrates then runs `runserver`.

## Key Commands

All run from **repo root** unless noted:

| What | Command |
|------|---------|
| Start all services | `docker-compose up -d` |
| Django management | `docker-compose exec backend python manage.py <cmd>` |
| Create test users | `python create_test_users.py` |
| Run integration tests | `python test_modules.py` (requires test users to exist first) |
| Generate PDF manual | `cd backend && python generate_manual.py` |
| Frontend dev server | `cd frontend && npm install && npm run dev` |
| Build frontend | `cd frontend && npm run build` (outputs to `backend/static/web/`) |

Django management **outside Docker**:
```bash
cd backend
DJANGO_SETTINGS_MODULE=config.settings.development python manage.py <cmd>
```

## Project Structure

```
backend/
  apps/
    accounts/    — Custom User model, auth, role-based access
    vehicles/    — Vehicle inventory (auction purchases)
    workshop/    — Work orders, materials/inventory
    sales/       — Sales contracts
    attendance/  — Clock-in/out, payroll
    accounting/  — Ledger entries (uses django-ledger)
    warranty/    — Legal warranties (Real Decreto-ley 7/2021)
    expenses/    — Expense tracking and export
    core/        — Shared utilities, home view
    api/         — Public JSON endpoints (no DRF, plain JsonResponse)
  config/
    settings/
      base.py          — Shared settings, reads backend/.env
      development.py   — SQLite fallback, DEBUG=True, CORS open
      production.py    — HTTPS, SMTP, WhiteNoise
  templates/     — Django HTML templates (HTMX-driven)
  tasks/         — Celery tasks (currently empty)
  services/      — Business logic services (currently empty)
```

URL routing is in `config/urls.py` — all ERP apps are nested under `/erp/` (`/erp/vehiculos/`, `/erp/taller/`, `/erp/ventas/`, `/erp/asistencia/`, `/erp/contabilidad/`, `/erp/gastos/`, `/erp/garantias/`, `/erp/accounts/`). The API is at `/api/`. No DRF routers.

## Important Conventions

- **Custom User model** is `accounts.User` (`AUTH_USER_MODEL = 'accounts.User'`). Always import from `apps.accounts.models`, never from `django.contrib.auth`.
- **Roles** are string choices on `User.rol`: `ADMIN`, `OPERARIO`, `VENDEDOR`, `GESTORIA`. Use `User.is_admin` / `is_operario` / `is_vendedor` / `is_gestoria` properties, not raw string comparisons.
- **Role redirect URLs**: `/operario/` → `attendance:kiosco`, `/vendedor/` → `sales:list`, `/gestoria/` → `accounting:asientos`. Defined in `core/urls.py` and `core/views.py`.
- **Template tags** for roles: `{% load role_tags %}` (lives in `apps/accounts/templatetags/`). Provides `{% is_admin user %}`, `{% is_operario user %}`, `{% is_vendedor user %}`, `{% is_gestoria user %}`, and generic `{% has_role user 'ADMIN' %}`.
- **Context processor** `apps.accounts.context_processors.user_roles` injects `is_admin`, `is_operario`, `is_vendedor`, `is_gestoria` into all templates automatically.
- **Settings split**: `base.py` is imported by both `development.py` and `production.py`. Never put env-specific logic in `base.py`.
- **`.env` files**: `base.py` reads `backend/.env` (`BASE_DIR` is `backend/`). Root `.env` is only used by docker-compose for service variables (POSTGRES_*, REDIS_URL). The root `.env.example` includes both docker and Django vars; `backend/.env` contains just the Django subset.
- **Timezone** is `Europe/Madrid`, locale `es-es`.
- **API endpoints** in `apps/api/` use raw `JsonResponse` (no DRF serializers), despite DRF being installed. Endpoints are defined directly in `urls.py` (no `views.py`).
- **Frontend build** outputs to `backend/static/web/` — served by Django in debug mode, Nginx in production.
- **ERP sidebar navigation** (defined in `templates/base.html`): "Inventario" → `workshop:material_list`. The "Nuevo Material" button is on that list page, visible only to ADMIN users. The `workshop/` app handles both work orders ("Taller") and inventory ("Inventario") as separate sidebar entries.

## Testing

There is **no pytest or formal test runner** configured. The repo uses:

- `test_modules.py` (root) — Django `Client`-based integration tests covering all modules and roles. Run with `python test_modules.py` from root (it manually adds `backend/` to `sys.path`). **Requires test users to exist first** — run `python create_test_users.py` before first test run.
- `create_test_users.py` (root) — Seeds 5 test users (admin, 2 mecanicos, vendedor, gestoria) with known passwords. Run from root. This is the canonical version (includes PINs and salary data).
- `backend/create_test_users.py` — A simpler, older variant (4 users, no PINs, hardcodes SQLite path). **Use the root version instead.**

Test user credentials:

| Username | Role | Password |
|----------|------|----------|
| `admin` | ADMIN | `admin123!` |
| `mecanico1` | OPERARIO (PIN: 1234) | `mecanico123!` |
| `mecanico2` | OPERARIO (PIN: 5678) | `mecanico123!` |
| `vendedor1` | VENDEDOR | `vendedor123!` |
| `gestoria1` | GESTORIA | `vendedor123!` |

## Gotchas

- The root-level `test_modules.py` and `create_test_users.py` set up `sys.path` manually to find `apps.*`. They must be run from repo root, not from `backend/`.
- `requirements.txt` includes `django-ledger==0.5.4` for accounting — do not remove.
- `django-csp` (Content Security Policy) and `django-axes` (brute force) are active. If adding new inline scripts/styles, they must comply with CSP.
- Session timeout is 1 hour (`SESSION_COOKIE_AGE = 3600`), sessions expire on browser close.
- In production, `django-cleanup` handles orphaned media files on model delete.
- No linting, typechecking, or CI is configured. There is no `eslint`, `ruff`, `flake8`, `.github/workflows/`, or pre-commit hooks.
- The frontend is vanilla Vue 3 + Vite (no Nuxt, no SSR). It proxies `/api` and `/media` to the backend in dev (port 3000 → 8000).
- `README.md` mentions "Nuxt 3" for the frontend — this is incorrect. It is a plain Vue 3 SPA.
- `whitenoise` is used in `production.py` middleware and **is listed in `backend/requirements.txt`** (v6.6.0). `gunicorn` is also listed there (v21.2.0).
- Account locking is implemented twice: once manually in the User model (5 attempts → 1 hour lock) and again via `django-axes`. Both are active.
- The `backend/Dockerfile` CMD runs `runserver` (dev server), not gunicorn — only suitable for development. The `docker-compose.yml` backend service also runs `runserver` (after `migrate`). A production Dockerfile (`backend/Dockerfile.prod`) exists: multi-stage build that compiles the Vue frontend and runs `gunicorn`. Use `docker-compose.prod.yml` for production deploys.
- Locally runs on Python 3.14 (`debug_toolbar` was removed for compatibility), while Docker uses Python 3.11. A monkey-patch in `config/settings/base.py:6-14` fixes `BaseContext.__copy__` for Python 3.14 + Django 4.2 compatibility — do not remove it.
- **Docker persistence**: PostgreSQL data is stored in a named volume `eurocar_pgdata`. **Never** use `docker-compose down -v` — the `-v` flag destroys all data. Always use `docker-compose down` (no `-v`) to preserve the database. If containers are rebuilt with `docker-compose up -d --build`, data persists.
