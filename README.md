# BrainDock

An idea inbox with configurable reminders and stale-idea alerts, open to
anyone: it can be used straight away without an account.

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

## Accounts

What someone may do depends only on the kind of account they use. The server
decides it from the account itself, never from anything the client sends; the
rules live in `backend/apps/users/plans.py` and the interface only reflects
them.

| Account | How it comes about | Ideas | Images and audio | Telegram bot, user panel |
| --- | --- | --- | --- | --- |
| Guest (مهمان) | Opening the site with no session | 2 | No | No |
| Regular (عادی) | Signing up with a name, username and password | 2 | No | No |
| Special (ویژه) | Made or upgraded by the owner in the user panel | No limit | Yes | No |
| Owner (مالک) | The superuser made with `createsuperuser` | No limit | Yes | Yes |

- Every account signs in on one page, `/panel`.
- A guest works like anyone else and sees a permanent banner asking it to
  sign up; signing up turns the guest into the account, ideas and all.
- Everything else, reminders included, is open to every account. The idea
  limit counts archived ideas too, but not the trash: deleting an idea frees
  its place, and taking it back out of the trash needs a free place again.
  `FREE_IDEA_LIMIT` changes it.
- There is no public sign-up for special accounts and no payment. The owner's
  settings page has a «پنل یوزر» button that makes special accounts and
  turns an account regular or special, either way, after asking; the admin's
  user list can tick «کاربر ویژه» too.
  Guests and regular accounts have a «خرید اشتراک» item at the foot of the
  sidebar, and sign-up an «ارتقا به کاربر ویژه» button; both open a Telegram
  chat with the owner, `OWNER_TELEGRAM_USERNAME` (`manijesmani` by default).
- The Telegram section and the user panel are rendered for the owner alone,
  and their endpoints answer everyone else with a 403. The owner's account is
  marked «مالک» beside the logo.
- Nothing is ever deleted automatically: every idea, a guest's included,
  stays in the database for good. A guest's session cookie is kept for a
  year, since it is the guest's only way back to its ideas.
- Every account but a guest has «دستگاه‌های فعال» in settings: each browser
  signed in to it, with its address and last use, and a way to sign any one
  or all the others out. A password change signs the others out on its own.
- «حذف» moves an idea to «سطل زباله», after asking. There it is out of every
  list, count, search and reminder, and comes back, archived or not, exactly
  where it was; only «حذف دائمی» in the trash removes it, and nothing empties
  the trash on its own.

## Requirements

- Python 3.13
- Node.js 22 LTS
- PostgreSQL 17 with the `pg_trgm` extension
- Redis 7 or later
- ffmpeg, for `ffprobe`: every audio attachment is checked with it, and
  without it all audio is refused -- Telegram voice messages included

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

In development nothing starts on its own. The app is available only while you
run it: start Django and the Vite dev server, each in its own terminal, plus
the Celery worker and scheduler when reminders should be delivered.
PostgreSQL and Redis have to be running for the backend to start. On a server
the same processes run under systemd; see [Deployment](#deployment).

### Backend (from `backend/`)

| Command | Purpose |
| --- | --- |
| `python manage.py runserver` | Development server |
| `celery -A config worker -l info` | Reminder worker |
| `celery -A config beat -l info` | Reminder scheduler |
| `pytest` | Test suite |
| `python manage.py remove_users_except_owner` | Development databases only (`DEBUG` on): moves every other account's ideas to the owner, then deletes those accounts. `--dry-run` only reports |
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
backend suite with a PostgreSQL service and ffmpeg plus `ruff` and
`check --deploy`, and the frontend's lint, formatting, type-check and build.

## Deployment

[`deploy/README.md`](deploy/README.md) sets BrainDock up on one Ubuntu 24.04
host without containers: an Nginx site beside any others the host serves,
Gunicorn and the two Celery processes under systemd, PostgreSQL 17, Redis,
a Let's Encrypt certificate and nightly backups. After the first deployment,
every update is one command:

```bash
sudo /srv/braindock/app/deploy/deploy.sh
```

## Layout

```
backend/
  config/       Split settings, URLs, WSGI/ASGI entry points
  core/         Abstract model bases, permissions, pagination, error handling
  apps/
    users/          User model, guests, sign-up and account plans
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
deploy/         Server setup: Nginx site, systemd units, deploy and backup scripts
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
interface, the Telegram bot, stale-idea alerts and the dashboard, security
hardening, a deployment without containers, a layout that adapts to phones
and tablets, and public use with guest, free, premium and owner accounts.

The Telegram client is tested end to end against a local stand-in for the Bot
API, over real HTTP. Talking to the real service still needs a token from
@BotFather and a public HTTPS address.
