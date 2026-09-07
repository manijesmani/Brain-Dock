"""Persian text normalisation for search.

PostgreSQL ships no Persian dictionary, so the `simple` configuration is used
and no stemming happens. That makes normalisation the part that actually
decides whether a search succeeds, because the same Persian word is routinely
written several ways:

  * Arabic kaf and yeh (U+0643, U+064A) instead of the Persian ones (U+06A9,
    U+06CC) -- most keyboards and a great deal of copied text use the Arabic
    forms, and the two look nearly identical.
  * Persian and Arabic-Indic digits alongside ASCII ones.
  * A zero-width non-joiner inside compounds, where the same person may type a
    plain space instead.
  * Optional diacritics and tatweel, which carry no meaning for matching.

Every one of those is folded away before text is indexed and before a query is
run, so the two sides meet on the same ground.

The identical transformation exists as a PostgreSQL function, created in
migration 0003, because the search columns are maintained by a database
trigger. `tests/test_search.py` asserts the two implementations agree on a
corpus of awkward strings; if this module changes, the SQL function has to
change with it.

Normalisation applies to searching only. Stored titles and documents keep
exactly the characters the user typed.

Every character below is written as an escape rather than pasted literally:
half of them are invisible, and a source file nobody can proof-read is a
liability in the one module where an unnoticed character changes behaviour.
"""

import re

# Letter forms that differ only in provenance, not in meaning.
LETTER_FOLDING = {
    "ك": "ک",  # ARABIC KAF            -> PERSIAN KEHEH
    "ي": "ی",  # ARABIC YEH            -> FARSI YEH
    "ى": "ی",  # ALEF MAKSURA          -> FARSI YEH
    "أ": "ا",  # ALEF WITH HAMZA ABOVE -> ALEF
    "إ": "ا",  # ALEF WITH HAMZA BELOW -> ALEF
    "آ": "ا",  # ALEF WITH MADDA ABOVE -> ALEF
    "ٱ": "ا",  # ALEF WASLA            -> ALEF
    "ة": "ه",  # TEH MARBUTA           -> HEH
    "ۀ": "ه",  # HEH WITH YEH ABOVE    -> HEH
}

DIGIT_FOLDING = {
    **{chr(0x0660 + n): str(n) for n in range(10)},  # Arabic-Indic
    **{chr(0x06F0 + n): str(n) for n in range(10)},  # Extended Arabic-Indic
}

_TRANSLATION = str.maketrans({**LETTER_FOLDING, **DIGIT_FOLDING})

# Diacritics (fathatan through sukun, plus superscript alef) and tatweel:
# decorative, never distinguishing for search.
_STRIPPED = re.compile("[\u064b-\u0652\u0670\u0640]")

# Zero-width and bidirectional controls become a space rather than vanishing,
# so a compound written with a ZWNJ matches the same compound written with a
# space -- which is how most people type it. The trade-off is that a compound
# typed with no separator at all still will not match on substring; full-text
# search covers that case, because each part is indexed as its own token.
_TO_SPACE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")

_WHITESPACE = re.compile(r"\s+")


def normalize_persian(value: str | None) -> str:
    """Folds a Persian string into the form used for indexing and querying."""
    if not value:
        return ""

    folded = value.translate(_TRANSLATION)
    folded = _STRIPPED.sub("", folded)
    folded = _TO_SPACE.sub(" ", folded)
    folded = _WHITESPACE.sub(" ", folded)

    return folded.strip().lower()
