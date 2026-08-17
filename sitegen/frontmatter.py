"""YAML-ish front matter parsing shared by both site flavours.

Both original generators used a minimal ``key: value`` parser (no real YAML):
the C# generator with case-insensitive keys, the Python one with quote
stripping. This parser combines both behaviours; they are compatible.
"""

from __future__ import annotations


class FrontMatter(dict):
    """A dict with case-insensitive ``get`` (the C# generator used
    OrdinalIgnoreCase key lookups; the homepage generator used exact keys,
    which are all lowercase there, so case-insensitivity is a safe superset)."""

    def get(self, key: str, default=None):  # type: ignore[override]
        if key in self:
            return super().get(key)
        lowered = key.lower()
        for existing, value in self.items():
            if existing.lower() == lowered:
                return value
        return default


def split_front_matter(raw: str) -> tuple[FrontMatter, str]:
    """Split an optional leading ``---`` front matter block from the body.

    Newlines are normalised to ``\\n`` for the whole text (as the C#
    generator did). The body starts on the line after the closing ``---``;
    a single leading newline is preserved, matching the C# behaviour
    (irrelevant for Markdown rendering).
    """
    meta = FrontMatter()
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    if not text.startswith("---\n"):
        return meta, text

    closing = text.find("\n---", 4)
    if closing < 0:
        return meta, text

    for line in text[4:closing].split("\n"):
        separator = line.find(":")
        if separator <= 0:
            continue
        key = line[:separator].strip()
        if not key:
            continue
        value = line[separator + 1 :].strip()
        # Strip a single layer of surrounding quotes (homepage flavour,
        # e.g. ``slug: ""``); harmless for the hp content.
        value = value.strip('"').strip("'")
        meta[key] = value

    body_start = text.find("\n", closing + 1)
    body = "" if body_start < 0 else text[body_start + 1 :]
    return meta, body
