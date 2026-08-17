"""Rendering of hp-style pages (articles, overview, content pages).

Faithful port of the C# PageRendererBase / MultiPageRenderer /
ContentPageRenderer trio.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from .config import BuildContext
from .frontmatter import FrontMatter, split_front_matter
from .md import MarkdownConverter
from .textutil import (
    extract_language,
    extract_title,
    html_encode,
    slugify,
    try_parse_date,
)

AI_NOTICE_TEMPLATE = "ai-article-notice.html"


@dataclass(frozen=True)
class Article:
    name: str
    output_file_name: str
    title: str
    body: str
    date: datetime | None
    area_of_interest: str
    description: str
    language: str
    # Full front matter for per-page rendering overrides (static pages).
    front_matter: FrontMatter = field(default_factory=FrontMatter)
    # Pre-built <link rel="alternate" hreflang=...> block for language pairs
    # (set by the articles step); empty for pages without a language variant.
    hreflang_html: str = ""

    def with_body(self, body: str) -> "Article":
        return replace(self, body=body)


def read_content(path: Path, page_prefix: str = "") -> Article:
    """Reads a Markdown file, extracting title/date/metadata exactly like
    the C# ReadContent."""
    name = path.stem
    raw = path.read_text(encoding="utf-8")
    front_matter, body = split_front_matter(raw)

    title = front_matter.get("title")
    if title is None:
        title, body = extract_title(body)
    if title is None:
        title = "Content Page"

    date = try_parse_date(front_matter.get("Datum"))
    if date is None and len(name) >= 10:
        date = try_parse_date(name[:10])

    description = front_matter.get("Thema") or front_matter.get("Description") or ""

    return Article(
        name=name,
        output_file_name=f"{page_prefix}{slugify(name)}.html",
        title=title,
        body=body,
        date=date,
        area_of_interest=front_matter.get("Interessensgebiet", ""),
        description=description,
        language=extract_language(name),
        front_matter=front_matter,
    )


class HpPageRenderer:
    """Renders a full hp page from the Jinja page template.

    ``options`` (from the pipeline step config):
      page_template      Jinja template for the page (default page-template.html.j2)
      foot_scripts       snippet with foot script tags (default default-scripts.html)
      title_suffix       appended to the <title> (e.g. " | Sven Erik Matzen")
      portrait_image     e.g. img/pp.jpg
      portrait_modifier  extra css class fragment, e.g. " ai-portrait"

    Per-page front matter keys (case-insensitive) override the step options,
    so hand-maintained pages can be driven entirely from their .md file:
      Template, FootScripts ("none" for no scripts), PageTitle (full <title>,
      suffix not applied), Heading (<h1>, default: title), OgTitle,
      OgDescription, OgType (default "article"), Canonical, Portrait,
      PortraitModifier.
    """

    def __init__(self, ctx: BuildContext, options: dict):
        self.ctx = ctx
        self.options = options
        self.markdown = MarkdownConverter(
            flavour=ctx.config.markdown_options.get("flavour", "hp"),
            table_class=ctx.config.markdown_options.get("table_class"),
        )

    def _resolve_localized(self, template_file: str, language: str) -> str:
        """Returns the file content of a language-specific template variant
        (e.g. ``ai-article-notice.de-DE.html``) when one exists."""
        if language:
            stem, dot, ext = template_file.rpartition(".")
            localized = f"{stem}.{language}{dot}{ext}"
            templates_dir = self.ctx.config.templates_dir
            if templates_dir and (templates_dir / localized).is_file():
                return self.ctx.read_template_text(localized)
        return self.ctx.read_template_text(template_file)

    def render_page(
        self,
        article: Article,
        disclaimer_paragraphs: tuple[str, ...] = (),
        body_is_html: bool = False,
    ) -> str:
        meta_parts: list[str] = []
        if article.area_of_interest.strip():
            meta_parts.append(html_encode(article.area_of_interest))
        if article.date is not None:
            meta_parts.append(article.date.strftime("%Y-%m-%d"))

        # EU AI Act transparency: show the AI-content label inline next to
        # the byline when the page has one; otherwise keep it at the bottom.
        has_byline = bool(meta_parts)
        inline_notice = has_byline and any(
            p.lower() == AI_NOTICE_TEMPLATE for p in disclaimer_paragraphs
        )

        joined_meta = " &middot; ".join(meta_parts)
        if inline_notice:
            byline = (
                '<p style="color:var(--gray-medium);font-size:.9em;'
                f'margin:0;white-space:nowrap;">{joined_meta}</p>'
            )
            notice = self._resolve_localized(AI_NOTICE_TEMPLATE, article.language)
            meta_content = (
                '<div style="display:flex;align-items:center;flex-wrap:wrap;'
                'gap:10px 16px;margin:0 0 24px;">\n'
                f"{byline}\n{notice}\n</div>\n"
            )
        elif meta_parts:
            meta_content = (
                '<p style="color:var(--gray-medium);font-size:.9em;'
                f'margin:0 0 24px;">{joined_meta}</p>\n'
            )
        else:
            meta_content = ""

        bottom = (
            tuple(p for p in disclaimer_paragraphs if p.lower() != AI_NOTICE_TEMPLATE)
            if inline_notice
            else disclaimer_paragraphs
        )
        disclaimer = "\n".join(self.ctx.read_template_text(p) for p in bottom)

        if article.date is not None:
            stamp = article.date.strftime("%Y-%m-%d")
            date_meta = (
                f'\n  <meta property="article:published_time" content="{stamp}">'
                f'\n  <meta property="article:modified_time" content="{stamp}">'
            )
        else:
            date_meta = ""

        content_html = article.body if body_is_html else self.markdown.convert(article.body)

        fm = article.front_matter
        foot_snippet = fm.get("FootScripts") or self.options.get(
            "foot_scripts", "default-scripts.html"
        )
        foot_scripts = "" if foot_snippet == "none" else self.ctx.read_template_text(foot_snippet)

        title_suffix = self.options.get("title_suffix", "")
        page_title = fm.get("PageTitle") or f"{article.title}{title_suffix}"

        portrait_modifier = fm.get("PortraitModifier")
        if portrait_modifier is None:
            portrait_modifier = self.options.get("portrait_modifier", "")

        template = self.ctx.jinja.get_template(
            fm.get("Template")
            or self.options.get("page_template", "page-template.html.j2")
        )
        return template.render(
            meta_dates=date_meta,
            # <html lang>: front matter override, else the article's locale
            # tag (from the file name), else the site default.
            page_lang=fm.get("Lang") or article.language or "en-US",
            hreflang_links=article.hreflang_html,
            page_title=html_encode(page_title),
            meta_description=html_encode(article.description),
            og_title=html_encode(fm.get("OgTitle") or article.title),
            og_description=html_encode(fm.get("OgDescription") or article.description),
            og_type=fm.get("OgType") or self.options.get("og_type", "article"),
            canonical_url=fm.get("Canonical")
            or self.ctx.config.base_url + article.output_file_name,
            heading=html_encode(fm.get("Heading") or article.title),
            portrait_img=fm.get("Portrait") or self.options.get("portrait_image", "img/pp.jpg"),
            portrait_modifier=portrait_modifier,
            disclaimer=disclaimer,
            meta_content=meta_content,
            content=content_html,
            foot_scripts=foot_scripts,
        )
