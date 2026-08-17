"""Markdown-to-HTML conversion for both site flavours."""

from __future__ import annotations

import markdown

from .markdig_compat import (
    BareAutoLinkExtension,
    InlineMathExtension,
    ListInterruptsParagraphExtension,
    collapse_blank_lines,
    escape_text_quotes,
    markdig_slugify,
)


def _hp_markdown() -> markdown.Markdown:
    """hp used Markdig's UseAdvancedExtensions(): pipe tables, footnotes,
    definition lists, auto heading ids, bare URL auto-links, inline math,
    lists interrupting paragraphs, ..."""
    return markdown.Markdown(
        extensions=[
            "extra",
            "sane_lists",
            "toc",
            BareAutoLinkExtension(),
            InlineMathExtension(),
            ListInterruptsParagraphExtension(),
        ],
        extension_configs={"toc": {"slugify": markdig_slugify}},
    )


def _homepage_markdown() -> markdown.Markdown:
    """homepage used python-markdown with exactly these extensions."""
    return markdown.Markdown(extensions=["extra", "tables", "sane_lists"])


_FLAVOURS = {"hp": _hp_markdown, "homepage": _homepage_markdown}


class MarkdownConverter:
    """Thin wrapper that owns a reusable ``markdown.Markdown`` instance."""

    def __init__(self, flavour: str = "homepage", table_class: str | None = None):
        try:
            self._md = _FLAVOURS[flavour]()
        except KeyError:
            raise ValueError(f"Unknown markdown flavour: {flavour!r}") from None
        self._table_class = table_class
        # Markdig (hp) terminates the last block with a newline and escapes
        # quotes in text nodes; python-markdown does neither.
        self._markdig_output = flavour == "hp"

    def convert(self, text: str) -> str:
        self._md.reset()
        html = self._md.convert(text)
        if self._table_class:
            html = html.replace("<table>", f'<table class="{self._table_class}">')
        if self._markdig_output:
            html = collapse_blank_lines(escape_text_quotes(html))
            if html and not html.endswith("\n"):
                html += "\n"
        return html
