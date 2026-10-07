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

| Account | How it comes about | Ideas | Images and audio | Telegram bot | User panel |
| --- | --- | --- | --- | --- | --- |
| Guest (مهمان) | Opening the site with no session | 2 | No | No | No |
| Regular (عادی) | Signing up with a name, username and password | 2 | No | Yes | No |
| Special (ویژه) | Made or upgraded by the owner in the user panel | No limit | Yes | Yes | No |
| Owner (مالک) | The superuser made with `createsuperuser` | No limit | Yes | Yes | Yes |

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
- Every registered account can connect Telegram from settings using its own
  private, single-use link (valid for 30 minutes), then press Start in the bot.
  One private Telegram chat belongs to one BrainDock account. Reminders and
  stale-idea alerts reach that chat; messages capture ideas with the same plan
  limits as the website. Guests cannot link or use the bot. Settings also offers
  disconnecting, which revokes any outstanding link.
- Only the owner sees the user panel; its endpoints refuse everyone else with
  a 403. Each listed account has a delete button with an explicit permanent
  deletion confirmation. It deletes that account and its ideas (including the
  archive and trash), attachments, avatar, categories, tags, reminders,
  notifications, Telegram links and login sessions. The owner cannot delete
  their own account or another owner here. The owner's account is marked
  «مالک» beside the logo.
- The entry page and successful login/sign-up open «همهٔ ایده‌ها» at `/ideas`.
  The dashboard remains available at `/dashboard`.
- New browsers use the dark theme. A chosen dark/light theme is kept in
  browser local storage and restored before the page is painted.
- Nothing is ever deleted automatically: every idea, a guest's included,
  stays until explicitly deleted. A guest's session cookie is kept for a
  year, since it is the guest's only way back to its ideas.
- Every account but a guest has «دستگاه‌های فعال» in settings: each browser
  signed in to it, with its address and last use, and a way to sign any one
  or all the others out. A password change signs the others out on its own.
- «حذف» moves an idea to «سطل زباله», after asking. There it is out of every
  list, count, search and reminder, and comes back, archived or not, exactly
  where it was; only «حذف دائمی» in the trash removes it, and nothing empties
  the trash on its own.

## Docker deployment

The production setup keeps `database/`, `backend/`, and `frontend/` in this
repository and runs them with Docker Compose. The existing shared host Nginx
keeps ports 80/443; the application exposes only a loopback port. See the
[Persian deployment and replacement guide](deploy/README.md).

```bash
./dock setup --domain braindock.ir
./dock up
./dock owner
```

Configuration is generated locally, with no default account/password. Existing
native installation data is not imported. `./dock bundle` packages the local
source changes for upload without pushing to GitHub or including credentials.

## Native development requirements

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
the same processes run in containers; see [Deployment](#deployment).

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

`.github/workflows/ci.yml` runs three jobs on pushes to `main` and pull requests targeting it: the
backend suite with a PostgreSQL service and ffmpeg plus `ruff` and
`check --deploy`, the frontend's lint, formatting, type-check and build,
and an isolated Docker deployment with backup/restore verification.

## Deployment

[`deploy/README.md`](deploy/README.md) covers Docker setup, replacing the old
BrainDock site while preserving shared Nginx and certificates, owner creation,
Telegram, consistent backups, restore, and optional nightly backups. After
uploading the new source into the existing Docker deployment, update with:

```bash
sudo /srv/braindock-docker/dock up
```

## Layout

```
database/       PostgreSQL image/bootstrap and private Redis configuration
compose.yaml    Services, health checks, private networks, secrets and volumes
dock            Setup, build/start, backup/restore and source packaging
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
deploy/         Docker operations, host Nginx template, verification and guides
.github/        CI workflow
BrainDock.dc.html   Authoritative UI design reference
```

Business logic lives in `services.py` and `selectors.py` inside each app; views
and serializers stay thin.

## Configuration

Docker reads public configuration from the root `.env` and credentials from
`.secrets/`, generated by `./dock setup`. Django supports file-based secrets
with the `_FILE` suffix. Native development uses `backend/.env`; see
`backend/.env.example` for its settings.

`DJANGO_SETTINGS_MODULE` defaults to `config.settings.dev` via `manage.py` and
to `config.settings.prod` via `wsgi.py` and `asgi.py`.

## Status

Implemented: the project skeleton, the idea API with session authentication,
attachments, Persian search, the reminder engine and notification centre, the
interface, the Telegram bot, stale-idea alerts and the dashboard, security
hardening, Docker deployment, a layout that adapts to phones
and tablets, and public use with guest, free, premium and owner accounts.

Release readiness also requires passing the full backend and Docker checks.
See [the validation record](deploy/VALIDATION.md) for completed checks and
remaining environment limitations.

The Telegram client is tested end to end against a local stand-in for the Bot
API, over real HTTP. Talking to the real service still needs a token from
@BotFather and a public HTTPS address.
