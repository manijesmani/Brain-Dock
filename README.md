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
the browser stays on a single origin and session cookies behave the same way
they would behind a reverse proxy.

### Telegram bot

The bot runs inside Django on a webhook; there is no second service.

```bash
# In backend/.env
TELEGRAM_BOT_TOKEN=<from @BotFather>
TELEGRAM_BOT_USERNAME=<the bot's username, without @>
TELEGRAM_WEBHOOK_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
SITE_URL=https://<public address>

python manage.py telegram_webhook set     # register the webhook
python manage.py telegram_webhook info    # check it
python manage.py telegram_webhook delete  # remove it
```

Telegram delivers only to HTTPS, so registering a webhook needs a public
address. In development, point one at the local server with a tunnel and pass
it explicitly:

```bash
python manage.py telegram_webhook set --base-url https://<tunnel address>
```

An account is linked from the settings page: it issues a one-time `t.me` link
that hands a token to the bot, which binds the chat to the account.

### Git hooks

```bash
pip install pre-commit   # or use backend/.venv
pre-commit install
```

## Commands

Nothing starts on its own. The app is available only while you run it: start
Django and the Vite dev server, each in its own terminal, plus the Celery
worker and scheduler when reminders should be delivered. PostgreSQL and Redis
have to be running for the backend to start.

### Backend (from `backend/`)

| Command | Purpose |
| --- | --- |
| `python manage.py runserver` | Development server |
| `celery -A config worker -l info` | Reminder worker |
| `celery -A config beat -l info` | Reminder scheduler |
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

## Continuous integration

`.github/workflows/ci.yml` runs two jobs on every push and pull request: the
backend suite with a PostgreSQL service plus `ruff` and `check --deploy`, and
the frontend's lint, formatting, type-check and build.

## Layout

```
backend/
  config/       Split settings, URLs, WSGI/ASGI entry points
  core/         Abstract model bases, permissions, pagination, error handling
  apps/
    users/          Custom user model
    ideas/          Idea, Category, Tag, Attachment, search
    reminders/      Reminder engine and its periodic tick
    notifications/  Notification centre and delivery channels
    telegrambot/    Webhook, handlers, account linking
  tests/
frontend/
  src/
    app/        Router and providers
    features/   One directory per product area
    shared/     ui, api, lib, hooks
    styles/     Design tokens
    types/
.github/        CI workflow
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

Complete. The project skeleton, the idea API with session authentication,
attachments, Persian search, the reminder engine and notification centre, the
interface, the Telegram bot, stale-idea alerts and the dashboard, and security
hardening.

The Telegram bot is the one part not proven against the real service: it needs
a token from @BotFather and a public HTTPS address, and is covered by tests
against a stubbed client instead.
