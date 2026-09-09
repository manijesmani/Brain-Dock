# Deployment

Six containers on one host: PostgreSQL, Redis, Gunicorn, a Celery worker, a
Celery beat scheduler, and Nginx. Only Nginx publishes ports.

```
            :80  :443
              │
         ┌────▼─────┐   /            the built SPA
         │  nginx   │   /api/        ──► gunicorn
         │          │   /static/     collectstatic output
         └────┬─────┘   /internal-media/  X-Accel-Redirect only
              │
      ┌───────┼────────┬──────────┐
      │       │        │          │
  ┌───▼──┐ ┌──▼───┐ ┌──▼──┐   ┌───▼───┐
  │ web  │ │worker│ │beat │   │       │
  └───┬──┘ └──┬───┘ └──┬──┘   │       │
      └───────┴────────┴──────► db, redis
```

`web`, `worker` and `beat` are the same image running different commands.

## First deployment

```bash
cp .env.example .env
# Fill in DJANGO_SECRET_KEY, POSTGRES_PASSWORD, and the four host settings.
# The stack refuses to start while any of them is empty.

./deploy/make-dev-cert.sh your.domain    # placeholder, replaced below
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Migrations and `collectstatic` run automatically, in the `web` container only.

## TLS

`make-dev-cert.sh` writes a self-signed certificate so the stack can be
brought up and tested without a domain. Browsers will warn about it. For a
real address, replace it with one from Let's Encrypt:

```bash
./deploy/cert.sh issue your.domain you@example.com
```

That runs certbot against the challenge Nginx is already serving, copies the
result into the two filenames the configuration names, and reloads. The stack
has to be up first -- the self-signed certificate is what lets it start, and
this replaces it.

The HTTP server block keeps `/.well-known/acme-challenge/` reachable without
TLS, which is what makes renewal work without downtime. A certificate is only
re-read when the configuration is loaded, so renewal has to reload Nginx;
`cert.sh renew` does both. From the host's crontab:

```cron
15 3 * * 1 cd /srv/braindock && ./deploy/cert.sh renew >> /var/log/braindock-cert.log 2>&1
```

Let's Encrypt certificates last 90 days and renew inside the last 30, so a
weekly run leaves several chances to recover from a failed one.

## Telegram

The bot needs a public HTTPS address, so it can only be registered once the
domain and certificate are real:

```bash
docker compose exec web python manage.py telegram_webhook set
docker compose exec web python manage.py telegram_webhook info
```

`TELEGRAM_WEBHOOK_SECRET` must be set. While it is empty the webhook rejects
every request rather than accepting them unauthenticated.

## Backups

```bash
./deploy/backup.sh
```

Writes two files into `backups/`: a compressed `pg_dump` archive and a tar of
the attachments. Both are verified after being written -- the dump is parsed
back with `pg_restore --list`, the archive with `gzip --test` -- because a
backup nobody has read is not a backup.

Files older than 14 days are deleted; override with `BRAINDOCK_RETENTION_DAYS`.
Nightly, from the host's crontab:

```cron
30 2 * * * cd /srv/braindock && ./deploy/backup.sh >> /var/log/braindock-backup.log 2>&1
```

Copy them off the machine. A backup on the same disk as the database only
protects against the mistakes, not the disk.

## Restoring

```bash
./deploy/restore.sh backups/braindock-db-<stamp>.dump backups/braindock-media-<stamp>.tar.gz
```

It stops `web`, `worker` and `beat` first, so nothing writes between the drop
and the reload, and asks for confirmation because it overwrites the live
database. The database restore runs in a single transaction: a failure part
way through rolls back rather than leaving half a schema.

## Operational notes

**Logs.** `docker compose logs -f web worker beat`. Gunicorn's access log and
Django's logging both go to stdout, which is where Docker expects them.

**Updating.** `docker compose up -d --build` rebuilds and replaces. Migrations
run as `web` starts.

**Rolling back.** Images are tagged from `BRAINDOCK_TAG` in `.env`. Build a
release under a tag, and rolling back is changing that value and running
`docker compose up -d`. A migration that dropped a column is not undone by
this; that is what the backups are for.

**Scaling.** `WEB_CONCURRENCY` sets Gunicorn workers, `CELERY_CONCURRENCY` the
worker processes. Do not run a second `beat`: two schedulers would fire every
reminder twice. The delivery table's unique constraint would keep the second
one from sending, but the correct number of schedulers is still one.
