# Deployment

One Ubuntu 24.04 host, no containers. Nginx is shared with whatever else the
host serves; BrainDock adds one site to it and three systemd services beside
it.

```
             :80  :443
               │
          ┌────▼─────┐   /                 frontend/dist (the SPA)
          │  nginx   │   /api/, the admin  ──► /run/braindock/gunicorn.sock
          │          │   /static/          backend/staticfiles
          └────┬─────┘   /internal-media/  backend/media, X-Accel-Redirect only
               │
     ┌─────────▼────────┐  ┌──────────────────┐  ┌────────────────┐
     │  braindock-web   │  │ braindock-worker │  │ braindock-beat │
     │    (Gunicorn)    │  │     (Celery)     │  │ (Celery beat)  │
     └─────────┬────────┘  └────────┬─────────┘  └───────┬────────┘
               └────────────────────┼────────────────────┘
                          PostgreSQL 17, Redis
```

| Path | What |
| --- | --- |
| `/srv/braindock/` | Home of the `braindock` system account, `0750` |
| `/srv/braindock/app/` | This repository |
| `/srv/braindock/app/backend/.env` | Configuration, `0600` |
| `/srv/braindock/app/backend/media/` | Attachments |
| `/run/braindock/gunicorn.sock` | Gunicorn, reachable by the `braindock` group only |
| `/var/lib/braindock/` | Celery beat's schedule |
| `/var/backups/braindock/` | Nightly backups, `0700` |

`www-data` is added to the `braindock` group, which is how Nginx reads the
built frontend and the attachments while no other account on the host can.

## First deployment

### 1. System packages

Ubuntu 24.04 ships Python 3.12 and PostgreSQL 16; the project targets 3.13
and 17, so both come from their upstream repositories.

```bash
sudo apt update
sudo apt install -y software-properties-common postgresql-common curl git
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt install -y python3.13 python3.13-venv postgresql-17 redis-server \
    nginx certbot ffmpeg nodejs
```

- `ffmpeg` provides `ffprobe`, which every audio attachment is checked with.
  Without it all audio uploads, Telegram voice messages included, are refused.
- Node.js is only needed to build the frontend.
- If the host already runs another PostgreSQL, `postgresql-17` becomes a
  second cluster on the next free port (`pg_lsclusters` shows which); put
  that port in `DATABASE_URL` below.

### 2. Account and checkout

```bash
sudo adduser --system --group --home /srv/braindock braindock
sudo chmod 750 /srv/braindock
sudo -u braindock git -C /srv/braindock clone https://github.com/manijesmani/Brain-Dock.git app
```

### 3. Database

```bash
sudo locale-gen en_US.UTF-8
sudo -u postgres createuser braindock
sudo -u postgres createdb --owner=braindock --template=template0 \
    --encoding=UTF8 --locale=en_US.UTF-8 braindock
```

The role has no password. It connects over the local socket with peer
authentication, which lets the `braindock` account in as the `braindock` role
and nobody else, so there is no database secret to keep.

`en_US.UTF-8` rather than the server's default `C.UTF-8`: under `C`, Persian
names sort by code point, which puts پ, چ, ژ, گ and ی after the rest of the
alphabet.

Do not create `pg_trgm` by hand. The first migration creates it as the
database owner; one created by `postgres` would belong to `postgres`, and a
restore, which drops and recreates it, would then fail.

### 4. Configuration

The file is created empty and private first, so the secrets are never
readable by anyone else, even for a moment.

```bash
sudo -u braindock install -m 600 /dev/null /srv/braindock/app/backend/.env
sudo -u braindock tee /srv/braindock/app/backend/.env > /dev/null <<EOF
DJANGO_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')
DATABASE_URL=postgres:///braindock
REDIS_URL=redis://127.0.0.1:6379/0
DJANGO_ALLOWED_HOSTS=braindock.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://braindock.example.com
SITE_URL=https://braindock.example.com
DJANGO_ADMIN_URL_PATH=$(python3 -c 'import secrets; print(secrets.token_hex(8))')/
TELEGRAM_BOT_USERNAME=
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
EOF
```

- If other projects on the host use Redis, give BrainDock a database number
  of its own (`/0` → another index). Sharing one would let their Celery
  workers take BrainDock's tasks and the other way round.
- If the second PostgreSQL cluster landed on another port,
  `DATABASE_URL=postgres://:5433/braindock` (with that port).
- `DJANGO_ADMIN_URL_PATH` moves the admin off `/admin/`. The generated value
  is the admin's address: `https://<domain>/<value>`.

### 5. Certificate

```bash
sudo /srv/braindock/app/deploy/nginx.sh
sudo certbot certonly --webroot -w /var/www/letsencrypt -d braindock.example.com \
    --deploy-hook "systemctl reload nginx"
```

The first `nginx.sh` installs only the plain-HTTP half of the site, which is
what Let's Encrypt checks. Certbot's own timer renews the certificate and the
deploy hook makes Nginx pick up each renewal.

### 6. Deploy

```bash
sudo /srv/braindock/app/deploy/deploy.sh
sudo /srv/braindock/app/deploy/manage.sh createsuperuser
```

`deploy.sh` ends by asking Gunicorn for `/api/health/` directly, then
fetching the site through Nginx the way a browser would.

## Updating

```bash
sudo /srv/braindock/app/deploy/deploy.sh
```

It pulls `main`, installs dependencies, runs `check --deploy`, migrates,
builds the frontend beside the live one and swaps it in, reinstalls the
units and the Nginx site, and restarts the services. Every step is safe to
repeat.

## Telegram

The bot needs a token from @BotFather in `TELEGRAM_BOT_TOKEN` and its username
in `TELEGRAM_BOT_USERNAME`. Then:

```bash
sudo systemctl restart braindock-web braindock-worker
sudo /srv/braindock/app/deploy/manage.sh telegram_webhook set
sudo /srv/braindock/app/deploy/manage.sh telegram_webhook info
```

While `TELEGRAM_WEBHOOK_SECRET` is empty the webhook refuses every request.

## Backups

`braindock-backup.timer` runs `deploy/backup.sh` every night: a `pg_dump`
archive and a tar of the attachments in `/var/backups/braindock`, both read
back before they count, kept for 14 days. By hand:

```bash
sudo systemctl start braindock-backup
journalctl -u braindock-backup
```

Copy them off the machine now and then. A backup on the same disk as the
database protects against mistakes, not against the disk.

To restore, which stops the services and asks before overwriting anything:

```bash
sudo /srv/braindock/app/deploy/restore.sh \
    /var/backups/braindock/braindock-db-<stamp>.dump \
    /var/backups/braindock/braindock-media-<stamp>.tar.gz
```

## Operating it

| Task | Command |
| --- | --- |
| Status | `systemctl status 'braindock-*'` |
| Logs | `journalctl -u braindock-web -u braindock-worker -u braindock-beat -f` |
| Restart | `sudo systemctl restart braindock-web braindock-worker braindock-beat` |
| Django command | `sudo /srv/braindock/app/deploy/manage.sh <command>` |
| Next backups | `systemctl list-timers braindock-backup.timer` |

Run exactly one `braindock-beat`. Two schedulers would fire every reminder
twice; the delivery table's unique constraint would stop the second send, but
the correct number is still one.
