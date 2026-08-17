"""python-markdown extensions replicating Markdig behaviours the hp site
relies on (Markdig was the Markdown engine of the original C# generator).

- bare URL auto-linking (Markdig's AutoLinks extension)
- Markdig-compatible heading id slugs (leading digits dropped, diacritics
  stripped, ss for sharp-s)
- ``"`` escaped as ``&quot;`` in text nodes (Markdig's HTML escaping)
"""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as etree

from markdown import Extension, util
from markdown.inlinepatterns import InlineProcessor
from markdown.preprocessors import Preprocessor

# -- bare URL auto-linking ----------------------------------------------

_AUTOLINK_RE = r"(?:https?://|ftp://|www\.)[^\s<>]+"
# Markdig only auto-links when the URL starts the text or follows
# whitespace or one of these characters.
_VALID_PREVIOUS = set(" \t\n*_~([")
_TRAILING_PUNCTUATION = ".,;:!?'\""


class _BareAutoLinkProcessor(InlineProcessor):
    def handleMatch(self, m, data):  # noqa: N802 (library API)
        start = m.start(0)
        if start > 0 and data[start - 1] not in _VALID_PREVIOUS:
            return None, None, None

        url = m.group(0).rstrip(_TRAILING_PUNCTUATION)
        # Trim unbalanced closing parentheses (e.g. "(see https://x.y)").
        while url.endswith(")") and url.count("(") < url.count(")"):
            url = url[:-1].rstrip(_TRAILING_PUNCTUATION)
        if not url:
            return None, None, None

        element = etree.Element("a")
        element.set("href", "http://" + url if url.startswith("www.") else url)
        element.text = url
        return element, start, start + len(url)


class BareAutoLinkExtension(Extension):
    def extendMarkdown(self, md):  # noqa: N802 (library API)
        md.inlinePatterns.register(
            _BareAutoLinkProcessor(_AUTOLINK_RE, md), "bare_autolink", 105
        )


# -- inline math ---------------------------------------------------------

# Markdig's Mathematics extension (part of UseAdvancedExtensions):
# $...$ becomes <span class="math">\(...\)</span>. The opening $ must not
# be preceded by an alphanumeric char and must be followed by
# non-whitespace; the closing $ must not be preceded by whitespace and
# not be followed by a digit (protects currency amounts like "$10 ... $20").
_MATH_RE = r"\$([^\s$](?:[^$\n]*[^\s$])?)\$"


class _InlineMathProcessor(InlineProcessor):
    def handleMatch(self, m, data):  # noqa: N802 (library API)
        start = m.start(0)
        if start > 0 and (data[start - 1].isalnum() or data[start - 1] in "\\$"):
            return None, None, None
        end = m.end(0)
        if end < len(data) and data[end].isdigit():
            return None, None, None

        element = etree.Element("span")
        element.set("class", "math")
        element.text = util.AtomicString(rf"\({m.group(1)}\)")
        return element, start, end


class InlineMathExtension(Extension):
    def extendMarkdown(self, md):  # noqa: N802 (library API)
        md.inlinePatterns.register(_InlineMathProcessor(_MATH_RE, md), "inline_math", 75)


# -- lists interrupting paragraphs ---------------------------------------

_LIST_START_RE = re.compile(r"^(?:[-*+]|1[.)])\s")
_ANY_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])(?:\s|$)")


class _ListInterruptsParagraphPreprocessor(Preprocessor):
    """Markdig (CommonMark) lets a bullet list start directly after a
    paragraph line; python-markdown needs a blank line. Insert one where a
    top-level list start follows a plain paragraph line. Runs after the
    fenced-code preprocessor, so code blocks are already stashed."""

    def run(self, lines):  # noqa: N802 (library API)
        out: list[str] = []
        for line in lines:
            if (
                out
                and out[-1].strip()
                and _LIST_START_RE.match(line)
                and not _ANY_LIST_ITEM_RE.match(out[-1])
                and not out[-1].lstrip().startswith(("#", ">", "|"))
            ):
                out.append("")
            out.append(line)
        return out


class ListInterruptsParagraphExtension(Extension):
    def extendMarkdown(self, md):  # noqa: N802 (library API)
        md.preprocessors.register(
            _ListInterruptsParagraphPreprocessor(md), "list_interrupts_paragraph", 20
        )


# -- Markdig-compatible heading slugs -----------------------------------

def markdig_slugify(value: str, separator: str = "-") -> str:
    """Heading id slug compatible with Markdig's auto-identifier:
    lowercase; diacritics stripped and ``ß`` -> ``ss``; ``- _ .`` kept;
    a space becomes one separator only when it follows a letter/digit;
    all other punctuation is dropped silently; the id starts at the
    first letter (leading digits are dropped)."""
    normalized = unicodedata.normalize("NFKD", value)
    out: list[str] = []
    has_letter = False
    for ch in normalized:
        if unicodedata.combining(ch):
            continue
        for c in "ss" if ch == "ß" else ch.lower():
            if c.isascii() and c.isalpha():
                out.append(c)
                has_letter = True
            elif c.isascii() and (c.isdigit() or c in "-_."):
                if has_letter:
                    out.append(c)
            elif c.isspace():
                if out and out[-1].isalnum():
                    out.append(separator)
    return "".join(out)


# -- blank-line collapsing ------------------------------------------------

_PRE_SPLIT_RE = re.compile(r"(<pre[\s\S]*?</pre>)")
_BLANK_LINES_RE = re.compile(r"\n{2,}")


def collapse_blank_lines(html: str) -> str:
    """Markdig emits no blank lines between blocks; python-markdown leaves
    one after raw HTML blocks. Collapse them everywhere except inside
    <pre> blocks (where blank lines are content)."""
    parts = _PRE_SPLIT_RE.split(html)
    for index in range(0, len(parts), 2):  # even indexes are outside <pre>
        parts[index] = _BLANK_LINES_RE.sub("\n", parts[index])
    return "".join(parts)


# -- text-node quote escaping -------------------------------------------

_TAG_SPLIT_RE = re.compile(r"(<[^>]*>)")


def escape_text_quotes(html: str) -> str:
    """Escape ``"`` as ``&quot;`` in text between tags (Markdig escapes
    quotes in text nodes; python-markdown does not)."""
    parts = _TAG_SPLIT_RE.split(html)
    for index in range(0, len(parts), 2):  # even indexes are text segments
        parts[index] = parts[index].replace('"', "&quot;")
    return "".join(parts)
