#!/bin/sh
set -eu
# The application owns its database, but cannot administer the PostgreSQL
# server or create other roles/databases. The admin secret stays in this service.
APP_PASSWORD=$(cat /run/secrets/db_app_password)
export APP_PASSWORD
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_password APP_PASSWORD
CREATE ROLE braindock LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE braindock OWNER braindock TEMPLATE template0 ENCODING 'UTF8';
REVOKE ALL ON DATABASE braindock FROM PUBLIC;
SQL
