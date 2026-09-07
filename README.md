# BrainDock

A personal idea inbox with configurable reminders and stale-idea alerts.

Ideas are captured quickly — from the web app or by messaging a Telegram bot —
and then actively brought back to the user, so they do not get buried and
forgotten the way notes in a private channel do.

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Django 5.2 LTS, Django REST Framework, PostgreSQL 17 |
| Queue | Celery, Celery Beat, Redis |
| Frontend | React 19, Vite, TypeScript, Tailwind CSS v4, TanStack Query |
| Bot | python-telegram-bot, served by Django via webhook |
| Deployment | Docker, Nginx, Gunicorn |

The interface is fully right-to-left and Persian, and all dates are shown in
the Jalali calendar. Timestamps are stored in UTC and converted only for
display.

## Requirements

- Python 3.13
- Node.js 22 LTS
- PostgreSQL 17 with the `pg_trgm` extension
- Redis 8

## Setup

### Database

```bash
sudo -u postgres psql -c "CREATE USER braindock WITH PASSWORD 'braindock' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE braindock OWNER braindock;"
sudo -u postgres psql -d braindock -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

`CREATEDB` is required so the test suite can create its throwaway database.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt

cp .env.example .env
# Set DJANGO_SECRET_KEY in .env:
#   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API is then available at `http://127.0.0.1:8000/api/`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on `http://localhost:5173` and proxies `/api` to Django, so
the browser stays on a single origin and session cookies behave exactly as they
will behind Nginx in production.

### Git hooks

```bash
pip install pre-commit   # or use backend/.venv
pre-commit install
```

## Commands

### Backend (from `backend/`)

| Command | Purpose |
| --- | --- |
| `python manage.py runserver` | Development server |
| `pytest` | Test suite |
| `ruff check .` | Lint |
| `ruff format .` | Format |

### Frontend (from `frontend/`)

| Command | Purpose |
| --- | --- |
| `npm run dev` | Development server |
| `npm run build` | Type-check and production build |
| `npm run lint` | Lint |
| `npm run format` | Format |
| `npm run typecheck` | Type-check only |

## Layout

```
backend/
  config/       Split settings, URLs, WSGI/ASGI entry points
  core/         Abstract model bases, permissions, pagination, error handling
  apps/
    users/      Custom user model
  tests/
frontend/
  src/
    app/        Router and providers
    features/   One directory per product area
    shared/     ui, api, lib, hooks
    styles/     Design tokens
    types/
BrainDock.dc.html   Authoritative UI design reference
```

Business logic lives in `services.py` and `selectors.py` inside each app; views
and serializers stay thin.

## Configuration

All configuration is read from `backend/.env`. See `backend/.env.example` for
the full list.

`DJANGO_SETTINGS_MODULE` defaults to `config.settings.dev` via `manage.py` and
to `config.settings.prod` via `wsgi.py` and `asgi.py`.

## Status

Phase 0 complete: project skeleton, split settings, custom user model, health
endpoint, linting and Git hooks.
