"""Adds the search columns and the trigger that keeps them current.

The normalisation implemented here must stay identical to
`apps.ideas.persian.normalize_persian`. `tests/test_search.py` compares the two
against a corpus of awkward strings, so drift fails the suite rather than
quietly degrading search results.
"""

import django.contrib.postgres.indexes
import django.contrib.postgres.search
from django.conf import settings
from django.db import migrations, models

# Folds the letter forms, digits, diacritics and zero-width characters that
# make the same Persian word look different to the database. Marked IMMUTABLE
# so it can be used inside an index expression and a trigger.
CREATE_NORMALISE_FUNCTION = r"""
CREATE OR REPLACE FUNCTION braindock_normalize_fa(input text)
RETURNS text AS $$
  SELECT btrim(
    regexp_replace(
      regexp_replace(
        regexp_replace(
          translate(
            lower(coalesce(input, '')),
            -- Arabic kaf/yeh/alef/teh-marbuta forms, then Arabic-Indic and
            -- extended Arabic-Indic digits.
            E'كيىأإآٱةۀ'
            || E'٠١٢٣٤٥٦٧٨٩'
            || E'۰۱۲۳۴۵۶۷۸۹',
            E'کییااااهه'
            || '0123456789'
            || '0123456789'
          ),
          -- Diacritics and tatweel carry no meaning for matching.
          '[ً-ْٰـ]', '', 'g'
        ),
        -- Zero-width and bidirectional controls become a space, so a compound
        -- written with a ZWNJ matches one written with a plain space.
        '[​-‏‪-‮⁠﻿]', ' ', 'g'
      ),
      '\s+', ' ', 'g'
    )
  )
$$ LANGUAGE sql IMMUTABLE;
"""

DROP_NORMALISE_FUNCTION = "DROP FUNCTION IF EXISTS braindock_normalize_fa(text);"

# The title is weighted above the body so a term in the title ranks first.
CREATE_TRIGGER = r"""
CREATE OR REPLACE FUNCTION braindock_idea_search_update()
RETURNS trigger AS $$
BEGIN
  NEW.search_text :=
    braindock_normalize_fa(coalesce(NEW.title, ''))
    || ' '
    || braindock_normalize_fa(coalesce(NEW.plain_text, ''));

  NEW.search_vector :=
    setweight(
      to_tsvector('simple', braindock_normalize_fa(coalesce(NEW.title, ''))),
      'A'
    ) ||
    setweight(
      to_tsvector('simple', braindock_normalize_fa(coalesce(NEW.plain_text, ''))),
      'B'
    );

  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER braindock_idea_search_trigger
BEFORE INSERT OR UPDATE OF title, plain_text ON ideas_idea
FOR EACH ROW EXECUTE FUNCTION braindock_idea_search_update();
"""

DROP_TRIGGER = """
DROP TRIGGER IF EXISTS braindock_idea_search_trigger ON ideas_idea;
DROP FUNCTION IF EXISTS braindock_idea_search_update();
"""

# Rows that already exist predate the trigger; a no-op update fires it.
BACKFILL = "UPDATE ideas_idea SET title = title;"


class Migration(migrations.Migration):
    dependencies = [
        ("ideas", "0002_attachment"),
        # The trigram index below cannot be built until pg_trgm exists.
        ("core", "0001_extensions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="idea",
            name="search_text",
            field=models.TextField(blank=True, default="", editable=False),
        ),
        migrations.AddField(
            model_name="idea",
            name="search_vector",
            field=django.contrib.postgres.search.SearchVectorField(
                editable=False, null=True
            ),
        ),
        migrations.RunSQL(
            sql=CREATE_NORMALISE_FUNCTION,
            reverse_sql=DROP_NORMALISE_FUNCTION,
        ),
        migrations.RunSQL(
            sql=CREATE_TRIGGER,
            reverse_sql=DROP_TRIGGER,
        ),
        migrations.RunSQL(
            sql=BACKFILL,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddIndex(
            model_name="idea",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_vector"], name="idea_search_vector_gin"
            ),
        ),
        migrations.AddIndex(
            model_name="idea",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_text"],
                name="idea_search_text_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
