"""Database extensions the project depends on.

These live in `core` rather than in the app that happens to need them first,
because an extension is a property of the database, not of one app.

Declaring them as a migration rather than as a manual setup step is what makes
the test database -- which pytest recreates from scratch on every run -- and
any fresh deployment work without somebody remembering to run psql first.

pg_trgm has been a trusted extension since PostgreSQL 13, so the database
owner can create it; no superuser connection is required.
"""

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        TrigramExtension(),
    ]
