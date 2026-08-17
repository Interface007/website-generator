"""Card collections: render a directory of card Markdown files into a grid.

Each card is one Markdown file with YAML front matter carrying the card's
*style* names (colour variant, icon/glyph, type) and structured extras
(tags, badges, facts); the Markdown body is the card's prose. A Jinja card
template turns each card into HTML, and the cards are wrapped in a grid
``<div>``. Icons are looked up by name from an SVG library so the glyph
markup lives in one place instead of being repeated in every card.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .md import MarkdownConverter


class CardError(Exception):
    """Raised for malformed card files or missing icons."""


@dataclass
class Card:
    meta: dict[str, Any]
    body_html: str


def split_yaml_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    """Split a ``---`` YAML front matter block from the Markdown body.

    Unlike the minimal page/article parser, card front matter is real YAML
    (lists and nested maps for tags/badges/facts)."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("---\n"):
        return {}, text
    closing = text.find("\n---", 4)
    if closing < 0:
        return {}, text
    block = text[4:closing]
    body_start = text.find("\n", closing + 1)
    body = "" if body_start < 0 else text[body_start + 1 :]
    meta = yaml.safe_load(block) or {}
    if not isinstance(meta, dict):
        raise CardError("Card front matter must be a YAML mapping")
    return meta, body


def load_icon_library(icons_dir: Path) -> dict[str, str]:
    """Load ``<name>.svg`` files (recursively) into a ``{name: markup}`` map."""
    library: dict[str, str] = {}
    if not icons_dir.is_dir():
        return library
    for svg in sorted(icons_dir.rglob("*.svg")):
        library[svg.stem] = svg.read_text(encoding="utf-8").strip()
    return library


def load_cards(collection_dir: Path, converter: MarkdownConverter) -> list[Card]:
    """Load and Markdown-convert every ``*.md`` card in a directory (sorted
    by file name, so a numeric prefix controls ordering)."""
    if not collection_dir.is_dir():
        raise CardError(f"card collection not found: {collection_dir}")
    cards: list[Card] = []
    for path in sorted(collection_dir.glob("*.md")):
        meta, body = split_yaml_front_matter(path.read_text(encoding="utf-8"))
        cards.append(Card(meta=meta, body_html=converter.convert(body).rstrip("\n")))
    if not cards:
        raise CardError(f"no card files in {collection_dir}")
    return cards


def render_grid(
    cards: list[Card],
    template,
    grid_class: str,
    icons: dict[str, str],
    icon_key: str | None,
) -> str:
    """Render each card through the template and wrap them in a grid div.

    ``icon_key`` is the front-matter field holding the icon name (e.g.
    ``glyph`` for project cards, ``icon`` for profile cards); when set, the
    resolved SVG markup is passed to the template as ``icon_svg``."""
    rendered: list[str] = []
    for card in cards:
        icon_svg = ""
        if icon_key:
            name = card.meta.get(icon_key)
            if name is None:
                raise CardError(f"card is missing '{icon_key}' front matter")
            if name not in icons:
                raise CardError(f"unknown icon '{name}' (have: {', '.join(sorted(icons))})")
            icon_svg = icons[name]
        html = template.render(description=card.body_html, icon_svg=icon_svg, **card.meta)
        rendered.append(html.strip("\n"))
    inner = "\n".join(rendered)
    return f'<div class="{grid_class}">\n{inner}\n</div>'
