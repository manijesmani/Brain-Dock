# Backend image: Django, Gunicorn, and the two Celery processes.
#
# The same image runs all three roles. They differ only in the command compose
# gives them, which keeps one build and one set of dependencies rather than
# three that could drift apart.

# --------------------------------------------------------------------------
# Stage 1 -- build the virtual environment
# --------------------------------------------------------------------------
FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# No compiler is installed on purpose. psycopg[binary] bundles libpq and
# Pillow ships manylinux wheels, so nothing in requirements needs building
# from source. If that ever stops being true the build will fail loudly here
# rather than silently pulling a toolchain into the runtime image.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements/ ./requirements/
RUN pip install -r requirements/prod.txt

# --------------------------------------------------------------------------
# Stage 2 -- runtime
# --------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

# DJANGO_SETTINGS_MODULE is set here because manage.py and config/celery.py
# both fall back to the dev settings via setdefault. This one variable
# redirects all three roles at once.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# An unprivileged account. A container that is compromised through the
# application should not also own the files it is serving.
RUN groupadd --system braindock \
    && useradd --system --gid braindock --home-dir /app --no-create-home braindock

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=braindock:braindock . .

# Created and chowned before the volumes are mounted. Docker copies the
# ownership of an image directory into a named volume the first time it is
# created, so doing this here is what makes them writable by a non-root user.
RUN mkdir -p /app/media /app/staticfiles /app/run \
    && chown -R braindock:braindock /app/media /app/staticfiles /app/run

USER braindock

EXPOSE 8000

# Only meaningful for the web role; the worker and beat containers override it
# with their own checks in compose.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["python", "healthcheck.py"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Worker count comes from WEB_CONCURRENCY, which Gunicorn reads by itself, so
# it can be tuned per host without rebuilding.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
