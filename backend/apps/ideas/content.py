"""Sanitisation of Tiptap documents and extraction of their plain text.

Idea content arrives from the client as a ProseMirror/Tiptap JSON tree. It is
never rendered as raw HTML -- the editor rebuilds the DOM from the JSON itself
-- so the exposure here is not markup injection but arbitrary structure being
persisted and later handed to something less careful.

The defence is therefore structural rather than textual: the document is
rebuilt from scratch against an allow-list. Any node or mark type that is not
recognised is unwrapped so its text survives, and every attribute that is not
explicitly permitted is discarded. An HTML sanitiser such as nh3 has nothing
to act on here, because no HTML is ever stored.

The allow-list matches exactly the toolbar in the design reference. Adding an
editor feature means adding it here too, otherwise it is silently stripped.
"""

from collections.abc import Callable
from typing import Any

from rest_framework import serializers

# Guard rails against pathological documents. These are generous for prose but
# stop a malicious or broken client from persisting something unbounded.
MAX_DEPTH = 30
MAX_NODES = 5_000
MAX_TEXT_LENGTH = 200_000

DOC_TYPE = "doc"
TEXT_TYPE = "text"


def empty_document() -> dict[str, Any]:
    """The canonical empty Tiptap document, used as the model default."""
    return {"type": DOC_TYPE, "content": []}


def _heading_level(value: Any) -> int | None:
    """Headings are limited to the three levels offered by the toolbar."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 1 <= value <= 3 else None


def _boolean(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _short_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed[:40] if trimmed else None


# Node type -> attribute name -> normaliser. A normaliser returning None means
# the attribute is dropped. A node type absent from this mapping is unwrapped.
ALLOWED_NODES: dict[str, dict[str, Callable[[Any], Any]]] = {
    DOC_TYPE: {},
    "paragraph": {},
    TEXT_TYPE: {},
    "hardBreak": {},
    "heading": {"level": _heading_level},
    "bulletList": {},
    "orderedList": {"start": lambda v: v if isinstance(v, int) and v > 0 else None},
    "listItem": {},
    "taskList": {},
    "taskItem": {"checked": _boolean},
    "blockquote": {},
    "codeBlock": {"language": _short_text},
}

# Mark type -> attribute name -> normaliser.
ALLOWED_MARKS: dict[str, dict[str, Callable[[Any], Any]]] = {
    "bold": {},
    "italic": {},
    "underline": {},
    "strike": {},
    "code": {},
    "highlight": {},
}

# Nodes after which the plain-text rendering starts a new line.
BLOCK_NODES = frozenset(
    {
        "paragraph",
        "heading",
        "listItem",
        "taskItem",
        "blockquote",
        "codeBlock",
    }
)

# Nodes that carry inline content rather than standing on their own.
INLINE_NODES = frozenset({TEXT_TYPE, "hardBreak"})

# Nodes whose children must all be blocks. Unwrapping an unrecognised wrapper
# can leave inline content directly under one of these, which ProseMirror
# treats as an invalid document, so such runs are re-wrapped in a paragraph.
# `paragraph`, `heading` and `codeBlock` are absent on purpose: their content
# is meant to be inline.
BLOCK_CONTAINERS = frozenset({DOC_TYPE, "blockquote", "listItem", "taskItem"})


class ContentTooLargeError(serializers.ValidationError):
    """Raised when a document exceeds the structural limits."""


def _wrap_inline_runs(children: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Gathers consecutive inline nodes into paragraphs."""
    wrapped: list[dict[str, Any]] = []
    run: list[dict[str, Any]] = []

    def flush() -> None:
        if run:
            wrapped.append({"type": "paragraph", "content": list(run)})
            run.clear()

    for child in children:
        if child.get("type") in INLINE_NODES:
            run.append(child)
        else:
            flush()
            wrapped.append(child)

    flush()
    return wrapped


def _clean_attrs(raw: Any, allowed: dict[str, Callable[[Any], Any]]) -> dict[str, Any]:
    if not allowed or not isinstance(raw, dict):
        return {}

    cleaned: dict[str, Any] = {}
    for name, normalise in allowed.items():
        if name not in raw:
            continue
        value = normalise(raw[name])
        if value is not None:
            cleaned[name] = value
    return cleaned


def _clean_marks(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()

    for mark in raw:
        if not isinstance(mark, dict):
            continue
        mark_type = mark.get("type")
        if not isinstance(mark_type, str) or mark_type not in ALLOWED_MARKS:
            continue
        if mark_type in seen:
            continue
        seen.add(mark_type)

        entry: dict[str, Any] = {"type": mark_type}
        attrs = _clean_attrs(mark.get("attrs"), ALLOWED_MARKS[mark_type])
        if attrs:
            entry["attrs"] = attrs
        cleaned.append(entry)

    return cleaned


class _Sanitiser:
    """Rebuilds a document, counting nodes so limits apply to the whole tree."""

    def __init__(self) -> None:
        self.node_count = 0
        self.text_length = 0

    def clean_children(self, raw: Any, depth: int) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []

        cleaned: list[dict[str, Any]] = []
        for child in raw:
            cleaned.extend(self.clean_node(child, depth))
        return cleaned

    def clean_node(self, raw: Any, depth: int) -> list[dict[str, Any]]:
        """Returns a list because an unknown node is replaced by its children."""
        if depth > MAX_DEPTH or not isinstance(raw, dict):
            return []

        self.node_count += 1
        if self.node_count > MAX_NODES:
            raise ContentTooLargeError("محتوای یادداشت بیش از حد بزرگ است.")

        node_type = raw.get("type")
        if not isinstance(node_type, str):
            return []

        if node_type == TEXT_TYPE:
            return self._clean_text(raw)

        children = self.clean_children(raw.get("content"), depth + 1)

        if node_type not in ALLOWED_NODES:
            # Unwrap: the wrapper is dropped but its content survives.
            return children

        if node_type in BLOCK_CONTAINERS:
            children = _wrap_inline_runs(children)

        node: dict[str, Any] = {"type": node_type}
        attrs = _clean_attrs(raw.get("attrs"), ALLOWED_NODES[node_type])
        if attrs:
            node["attrs"] = attrs
        if children:
            node["content"] = children

        return [node]

    def _clean_text(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        text = raw.get("text")
        if not isinstance(text, str) or not text:
            return []

        self.text_length += len(text)
        if self.text_length > MAX_TEXT_LENGTH:
            raise ContentTooLargeError("متن یادداشت بیش از حد طولانی است.")

        node: dict[str, Any] = {"type": TEXT_TYPE, "text": text}
        marks = _clean_marks(raw.get("marks"))
        if marks:
            node["marks"] = marks
        return [node]


def sanitize_document(raw: Any) -> dict[str, Any]:
    """Returns a document containing only allow-listed nodes, marks and attrs.

    Anything else is stripped. The result is always a well-formed `doc` node,
    so callers never have to defend against a partially valid tree.
    """
    if raw is None:
        return empty_document()

    if not isinstance(raw, dict):
        raise serializers.ValidationError("ساختار محتوای یادداشت نامعتبر است.")

    if raw.get("type") != DOC_TYPE:
        raise serializers.ValidationError("محتوای یادداشت باید یک سند معتبر باشد.")

    sanitiser = _Sanitiser()
    content = _wrap_inline_runs(sanitiser.clean_children(raw.get("content"), depth=1))

    return {"type": DOC_TYPE, "content": content}


def extract_plain_text(document: Any) -> str:
    """Flattens a document to text for search indexing and Telegram messages.

    Block-level nodes are separated by newlines so the result stays readable
    rather than collapsing into one run-on line.
    """
    if not isinstance(document, dict):
        return ""

    parts: list[str] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return

        node_type = node.get("type")

        if node_type == TEXT_TYPE:
            text = node.get("text")
            if isinstance(text, str):
                parts.append(text)
            return

        if node_type == "hardBreak":
            parts.append("\n")
            return

        children = node.get("content")
        if isinstance(children, list):
            for child in children:
                walk(child)

        if node_type in BLOCK_NODES:
            parts.append("\n")

    walk(document)

    # Collapse the blank lines that nested blocks inevitably produce.
    lines = [line.strip() for line in "".join(parts).split("\n")]
    return "\n".join(line for line in lines if line).strip()
