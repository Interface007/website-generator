"""Text helpers ported from the C# generator (PageRendererBase et al.)."""

from __future__ import annotations

import re
from datetime import datetime


def html_encode(value: str | None) -> str:
    """Replicates .NET ``WebUtility.HtmlEncode``: escapes ``& < > " '``
    and encodes characters U+00A0..U+00FF as decimal entities (characters
    above U+00FF are left as-is)."""
    if not value:
        return ""
    out: list[str] = []
    for ch in value:
        code = ord(ch)
        if ch == "&":
            out.append("&amp;")
        elif ch == "<":
            out.append("&lt;")
        elif ch == ">":
            out.append("&gt;")
        elif ch == '"':
            out.append("&quot;")
        elif ch == "'":
            out.append("&#39;")
        elif 160 <= code <= 255:
            out.append(f"&#{code};")
        else:
            out.append(ch)
    return "".join(out)


def slugify(value: str) -> str:
    """URL-friendly slug with German umlaut transliteration (C# Slugify)."""
    builder: list[str] = []
    for ch in value.lower():
        if ch == "ä":
            builder.append("ae")
        elif ch == "ö":
            builder.append("oe")
        elif ch == "ü":
            builder.append("ue")
        elif ch == "ß":
            builder.append("ss")
        elif ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            builder.append(ch)
        else:
            builder.append("-")
    slug = re.sub("-{2,}", "-", "".join(builder)).strip("-")
    return slug or "article"


def strip_date_prefix(name: str) -> str:
    """Removes a leading date prefix like ``2024-06-22 - `` from a string."""
    return re.sub(r"^\d{4}-\d{2}-\d{2}\s*-\s*", "", name).strip()


def extract_language(name: str) -> str:
    """Reads a trailing locale suffix (e.g. ``de-DE``) from a string."""
    match = re.search(r"-\s*([A-Za-z]{2}-[A-Za-z]{2})\s*$", name)
    return match.group(1) if match else ""


def is_sync_artifact(stem: str) -> bool:
    """True for Synology/OneDrive sync artifacts like ``*-conflict`` or
    ``*-wk-*`` (separators ``_`` and ``-`` are treated alike)."""
    normalized = stem.replace("_", "-").lower()
    return "-wk-" in normalized or normalized.endswith("-conflict")


def try_parse_date(value: str | None) -> datetime | None:
    """Best-effort date parsing (C# DateTime.TryParse, invariant culture).
    The content only ever uses ISO ``yyyy-MM-dd`` dates."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


_TITLE_RE = re.compile(r"^[ \t]*#[ \t]+(.+?)[ \t]*$", re.MULTILINE)


def extract_title(body: str) -> tuple[str | None, str]:
    """Extracts the first level-1 heading as the title, removing it (plus a
    directly following horizontal rule) and everything before it from the
    body. Returns ``(title, remaining_body)``."""
    match = _TITLE_RE.search(body)
    if not match:
        return None, body

    title = match.group(1).strip()
    rest = body[match.end() :].lstrip()

    if rest.startswith("---"):
        newline = rest.find("\n")
        rest = "" if newline < 0 else rest[newline + 1 :].lstrip()

    return title, rest


_WIKI_LINK_RE = re.compile(r"\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]")


def replace_wiki_links(markdown_text: str, resolve) -> str:
    """Turns Obsidian ``[[target|alias]]`` links into Markdown links.

    ``resolve(target)`` returns ``(title, href)`` for known targets or
    ``None``; unknown targets degrade to plain text (alias, or the target
    name without its date prefix)."""

    def _sub(match: re.Match) -> str:
        target = match.group(1).strip()
        alias = match.group(2).strip() if match.group(2) else None
        resolved = resolve(target)
        if resolved is not None:
            title, href = resolved
            return f"[{alias or title}]({href})"
        return alias or strip_date_prefix(target)

    return _WIKI_LINK_RE.sub(_sub, markdown_text)
