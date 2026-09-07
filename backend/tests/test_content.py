"""Tests for the Tiptap document sanitiser.

These need no database, so they are the fastest guard on the one piece of the
app that handles untrusted structure directly.
"""

import pytest
from rest_framework import serializers

from apps.ideas.content import (
    MAX_NODES,
    ContentTooLargeError,
    empty_document,
    extract_plain_text,
    sanitize_document,
)


def paragraph(*children: dict) -> dict:
    return {"type": "paragraph", "content": list(children)}


def text(value: str, marks: list[dict] | None = None) -> dict:
    node: dict = {"type": "text", "text": value}
    if marks is not None:
        node["marks"] = marks
    return node


def doc(*children: dict) -> dict:
    return {"type": "doc", "content": list(children)}


class TestSanitizeDocument:
    def test_none_becomes_an_empty_document(self) -> None:
        assert sanitize_document(None) == empty_document()

    def test_allowed_structure_survives_unchanged(self) -> None:
        source = doc(
            {"type": "heading", "attrs": {"level": 2}, "content": [text("عنوان")]},
            paragraph(text("متن", [{"type": "bold"}])),
        )

        assert sanitize_document(source) == source

    def test_unknown_node_is_unwrapped_but_its_text_survives(self) -> None:
        source = doc({"type": "iframe", "content": [paragraph(text("سلام"))]})

        assert sanitize_document(source) == doc(paragraph(text("سلام")))

    def test_orphaned_inline_content_is_wrapped_in_a_paragraph(self) -> None:
        """A `doc` may only contain blocks, so unwrapping must not leave text
        directly under it -- ProseMirror would reject the document."""
        source = doc({"type": "section", "content": [text("متن یتیم")]})

        assert sanitize_document(source) == doc(paragraph(text("متن یتیم")))

    def test_orphaned_inline_content_inside_a_blockquote_is_wrapped(self) -> None:
        source = doc(
            {
                "type": "blockquote",
                "content": [{"type": "section", "content": [text("نقل قول")]}],
            }
        )

        assert sanitize_document(source) == doc(
            {"type": "blockquote", "content": [paragraph(text("نقل قول"))]}
        )

    def test_wrapping_keeps_adjacent_blocks_separate(self) -> None:
        source = doc(
            {"type": "section", "content": [text("اول")]},
            paragraph(text("دوم")),
        )

        assert extract_plain_text(sanitize_document(source)) == "اول\nدوم"

    def test_unknown_mark_is_dropped_and_text_kept(self) -> None:
        source = doc(paragraph(text("کلیک", [{"type": "link", "attrs": {"href": "x"}}])))

        assert sanitize_document(source) == doc(paragraph(text("کلیک")))

    def test_unknown_attributes_are_discarded(self) -> None:
        source = doc(
            {
                "type": "paragraph",
                "attrs": {"onclick": "alert(1)", "style": "color:red"},
                "content": [text("متن")],
            }
        )

        assert sanitize_document(source) == doc(paragraph(text("متن")))

    def test_heading_level_is_clamped_to_the_toolbar_range(self) -> None:
        source = doc({"type": "heading", "attrs": {"level": 6}, "content": [text("ت")]})

        result = sanitize_document(source)

        assert result["content"][0].get("attrs") is None

    def test_non_document_root_is_rejected(self) -> None:
        with pytest.raises(serializers.ValidationError):
            sanitize_document({"type": "paragraph"})

    def test_non_object_input_is_rejected(self) -> None:
        with pytest.raises(serializers.ValidationError):
            sanitize_document("<script>alert(1)</script>")

    def test_oversized_document_is_rejected(self) -> None:
        source = doc(*[paragraph(text("x")) for _ in range(MAX_NODES)])

        with pytest.raises(ContentTooLargeError):
            sanitize_document(source)

    def test_duplicate_marks_are_collapsed(self) -> None:
        source = doc(paragraph(text("متن", [{"type": "bold"}, {"type": "bold"}])))

        result = sanitize_document(source)

        assert result["content"][0]["content"][0]["marks"] == [{"type": "bold"}]


class TestExtractPlainText:
    def test_blocks_are_separated_by_newlines(self) -> None:
        source = doc(paragraph(text("خط اول")), paragraph(text("خط دوم")))

        assert extract_plain_text(source) == "خط اول\nخط دوم"

    def test_inline_runs_are_joined_without_a_separator(self) -> None:
        source = doc(paragraph(text("نیمهٔ "), text("اول")))

        assert extract_plain_text(source) == "نیمهٔ اول"

    def test_empty_document_yields_empty_string(self) -> None:
        assert extract_plain_text(empty_document()) == ""

    def test_list_items_each_get_their_own_line(self) -> None:
        source = doc(
            {
                "type": "bulletList",
                "content": [
                    {"type": "listItem", "content": [paragraph(text("یک"))]},
                    {"type": "listItem", "content": [paragraph(text("دو"))]},
                ],
            }
        )

        assert extract_plain_text(source) == "یک\nدو"
