FROM python:3.13-slim-bookworm AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements/ requirements/
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install -r requirements/prod.txt

FROM python:3.13-slim-bookworm AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 braindock \
    && useradd --uid 10001 --gid 10001 --no-create-home braindock
COPY --from=dependencies /opt/venv /opt/venv
WORKDIR /app
COPY apps/ apps/
COPY config/ config/
COPY core/ core/
COPY container/ container/
COPY manage.py ./
RUN mkdir -p /app/media /app/staticfiles /var/lib/braindock \
    && chown -R 10001:10001 /app/media /app/staticfiles /var/lib/braindock
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--no-control-socket", "--workers", "2", "--timeout", "60", "--graceful-timeout", "30", "--worker-tmp-dir", "/tmp", "--max-requests", "1000", "--max-requests-jitter", "100", "--access-logfile", "-", "--error-logfile", "-"]
