# AGENTS.md

## Architecture

Two apps side by side:

- **`backend/`** — Django 4.2 ERP (server-rendered with HTMX). Main app.
- **`frontend/`** — Vue 3 + Vite public website (catalog, contact). Builds into `backend/static/web/`.

`docker-compose.yml` runs 5 services: `db` (Postgres 15), `redis`, `backend`, `celery_worker`, `nginx`.

All ERP routes are nested under `/erp/` (see `backend/config/urls.py:6-18`). API at `/api/` uses raw `JsonResponse` (no DRF) despite DRF being installed.

Roles (`accounts.User.rol`): `ADMIN`, `OPERARIO`, `VENDEDOR`, `GESTORIA`. Use `user.is_admin` / `is_operario` / `is_vendedor` / `is_gestoria` properties, never raw string comparisons.

## Commands

Run from **repo root** unless noted:

| What | Command |
|------|---------|
| Start all services | `docker-compose up -d` |
| Django management (Docker) | `docker-compose exec backend python manage.py <cmd>` |
| Django management (local) | `cd backend && python manage.py <cmd>` (defaults to `development` settings, falls back to SQLite) |
| Create test users | `python create_test_users.py` (run before tests) |
| Run integration tests | `python test_modules.py` (needs test users) |
| Frontend dev server | `cd frontend && npm install && npm run dev` (port 3000, proxies `/api` and `/media` to :8000) |
| Build frontend | `cd frontend && npm run build` → `backend/static/web/` |

## Production Deploy

Deployed on **Render** (Python runtime, not Docker).

Before pushing to GitHub for deployment:
1. Ensure `Procfile` exists at repo root (gunicorn entrypoint)
2. Ensure `dj-database-url` is in `requirements.txt`
3. `SECRET_KEY` and `DATABASE_URL` are set via Render env vars — never committed

**Render setup** (one-time manual):
- **Web Service**: connect GitHub repo, Python 3 runtime
  - Build command: `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate`
  - Start command: `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120`
- **PostgreSQL**: plan Free (90-day trial; upgrade to Basic $7/mo before expiry)
- **Env vars**: `DATABASE_URL`, `SECRET_KEY`, `DJANGO_SETTINGS_MODULE=config.settings.production`, `DEBUG=False`, `ALLOWED_HOSTS=.onrender.com,localhost`
- **UptimeRobot**: monitor `https://<app>.onrender.com/ping/` every 10 min to prevent cold starts
- **Backups**: GitHub Actions workflow (`.github/workflows/backup.yml`) dumps DB daily — needs `DATABASE_URL` secret in GitHub repo

**Important**: Render free tier has ephemeral filesystem — uploaded media (vehicle images, invoice PDFs) are lost on redeploy. Configure `django-storages` + S3-compatible storage for persistence when needed.

## Testing

No pytest. Root-level `test_modules.py` uses Django `Client` (manually adds `backend/` to `sys.path`). Must be run from repo root. Test users from `create_test_users.py`:

| Username | Role | Password |
|----------|------|----------|
| `admin` | ADMIN | `admin123!` |
| `roger` | ADMIN (puede_eliminar=False) | `roger123!` |
| `mecanico1` | OPERARIO (PIN: 1234) | `mecanico123!` |
| `mecanico2` | OPERARIO (PIN: 5678) | `mecanico123!` |
| `vendedor1` | VENDEDOR | `vendedor123!` |
| `gestoria1` | GESTORIA | `vendedor123!` |

## Gotchas

- **Custom User** is `accounts.User` (`AUTH_USER_MODEL = 'accounts.User'`). Import from `apps.accounts.models`, never `django.contrib.auth`.
- **`User.puede_eliminar`** (boolean, default True) controls delete permission. Roger is created with `puede_eliminar=False`.
- **No linting, typechecking** exists. `eslint`, `ruff`, `flake8`, pre-commit hooks are all absent. CI exists only as `.github/workflows/backup.yml` (DB backup).
- **README.md** says "Nuxt 3" for frontend — incorrect. It's plain Vue 3 SPA + Tailwind.
- **Python 3.14 locally** (Docker uses 3.11). A monkey-patch in `config/settings/base.py:6-14` fixes `BaseContext.__copy__` — do not remove.
- **`.env` split**: root `.env` is for docker-compose vars. `backend/.env` is for Django (`config/settings/base.py` reads it).
- **Account locking** is implemented twice: manual (5 attempts → 1h lock on User model) + `django-axes`. Both active.
- **`django-csp`** and **`django-axes`** are active. New inline scripts/styles must comply with CSP.
- **Session timeout** is 1h (`SESSION_COOKIE_AGE = 3600`), expires on browser close.
- **`backend/create_test_users.py`** is older/stale. Use root `python create_test_users.py` instead.
- **`django-cleanup`** auto-deletes orphaned files when model records are removed.
- **`remote_deploy.py`** and all VPS-specific scripts (fix_*, debug_*, etc.) have been removed — replaced by Render deployment.