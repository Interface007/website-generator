"""Step: render the homepage-style section tree.

Port of the homepage (semhps) generator ``build.py``: every
``source/<section>/index.md`` becomes ``<out>/<slug>/index.html`` with a
shared layout and top navigation. Detail pages come from flat ``*.md``
files inside a section (e.g. ``berichte/2014-06-08-foo.md``) — including
extensionless files that look like Markdown — and, for backward
compatibility, from legacy nested ``index.md`` files.

Options:
  source_dir         content root (one directory per section; "home" maps
                     to the site root)
  layout             Jinja layout template (default layout.html.j2)
  site_title         brand/title shown in the header
  footer             footer line
  assets_source      the _assets directory (gallery + media source)
  gallery_media_base_url  external host serving processed gallery media
                     (default: site.gallery_media_base_url)
  reports            {section, table_template}: date-slugged report pages
                     get a sortable table on the section page, previous/
                     next navigation, a picture-gallery link when a gallery
                     folder matches the report date, and flat
                     ``<section>/<slug>.html`` output files
  links_table_slug   page whose Markdown link list becomes a table
  gallery_page_slug  page that receives the accordion picture gallery
  footer_link_slugs  pages linked in the footer (default impressum,
                     datenschutz)
  not_found          {template, title, output}: themed 404 page
  sitemap            {git_repo, output, base_url}: page-based sitemap with
                     git lastmod dates (base_url defaults to site.base_url)
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from html import escape as _html_escape
from pathlib import Path

from ..config import BuildContext
from ..frontmatter import split_front_matter
from ..gallery_builder import GalleryBuilder
from ..homepage_features import (
    build_report_neighbors,
    extract_report_date,
    generate_sitemap,
    render_footer_links,
    render_links_table,
    render_report_neighbors,
    render_reports_table,
)
from ..md import MarkdownConverter


@dataclass
class Page:
    slug: str            # "" for home, else e.g. "ueber-uns"
    title: str           # <title> / <h1>
    nav_title: str       # label in the nav bar
    order: int
    body_md: str
    source_dir: Path     # source/<section>
    source_file: Path    # concrete .md source file for git timestamps
    nav_slug: str        # top-level slug used to highlight the nav item
    in_nav: bool         # include page in top navigation
    bilder: str | None   # optional gallery folder (front matter "bilder")


def normalize_slug(text: str) -> str:
    """Normalize text to a URL-friendly slug (German transliteration,
    lowercase, dashes)."""
    text = text.replace("ä", "ae").replace("Ä", "ae")
    text = text.replace("ö", "oe").replace("Ö", "oe")
    text = text.replace("ü", "ue").replace("Ü", "ue")
    text = text.replace("ß", "ss")
    text = text.lower()
    text = text.replace(" ", "-")
    text = re.sub(r"[^a-z0-9\-_]", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _iter_detail_markdown_files(section: Path):
    """Yield Markdown detail files in a section directory: regular ``*.md``
    plus extensionless files that look like Markdown (smaller than 10 KiB
    and starting with a ``---`` front matter marker)."""
    max_size = 10 * 1024
    for item in section.iterdir():
        if not item.is_file():
            continue
        if item.suffix.lower() == ".md":
            yield item
            continue
        if item.suffix:
            continue
        try:
            if item.stat().st_size >= max_size:
                continue
            with item.open("r", encoding="utf-8") as handle:
                if handle.read(3) == "---":
                    yield item
        except (OSError, UnicodeDecodeError):
            continue


def load_pages(source_dir: Path) -> list[Page]:
    pages: list[Page] = []
    for section in sorted(p for p in source_dir.iterdir() if p.is_dir()):
        if section.name.startswith("_"):
            continue
        index = section / "index.md"
        if not index.exists():
            continue
        meta, body = split_front_matter(index.read_text(encoding="utf-8"))
        # Special case: the "home" section gets an empty slug (site root).
        section_slug = "" if section.name == "home" else normalize_slug(section.name)
        in_nav = str(meta.get("in_nav", "true")).lower() not in {"false", "0", "no"}
        pages.append(
            Page(
                slug=section_slug,
                title=meta.get("title", section.name),
                nav_title=meta.get("nav_title", meta.get("title", section.name)),
                order=int(meta.get("order", "99")),
                body_md=body,
                source_dir=section,
                source_file=index,
                nav_slug=section_slug,
                in_nav=in_nav,
                bilder=meta.get("bilder", None),
            )
        )

        # Detail pages from flat markdown files, e.g. source/berichte/*.md.
        for detail in sorted(_iter_detail_markdown_files(section)):
            if detail.name == "index.md":
                continue
            if detail.stem.startswith("_"):
                continue

            detail_meta, detail_body = split_front_matter(
                detail.read_text(encoding="utf-8")
            )
            detail_slug = (
                f"{section_slug}/{normalize_slug(detail.stem)}"
                if section_slug
                else normalize_slug(detail.stem)
            )
            detail_title = detail_meta.get("title", detail.stem)

            pages.append(
                Page(
                    slug=detail_slug,
                    title=detail_title,
                    nav_title=detail_meta.get("nav_title", detail_title),
                    order=int(detail_meta.get("order", "999")),
                    body_md=detail_body,
                    source_dir=detail.parent,
                    source_file=detail,
                    nav_slug=section_slug,
                    in_nav=False,
                    bilder=detail_meta.get("bilder", None),
                )
            )

        # Backward compatibility: legacy nested index.md detail pages.
        for nested in sorted(section.rglob("index.md")):
            if nested == index or nested.parent == section:
                continue
            if any(part.startswith("_") for part in nested.parts):
                continue

            nested_meta, nested_body = split_front_matter(
                nested.read_text(encoding="utf-8")
            )
            rel_dir = nested.parent.relative_to(source_dir).as_posix()
            nested_slug = normalize_slug(rel_dir.replace("/", "-"))
            nested_title = nested_meta.get("title", nested.parent.name)

            pages.append(
                Page(
                    slug=nested_slug,
                    title=nested_title,
                    nav_title=nested_meta.get("nav_title", nested_title),
                    order=int(nested_meta.get("order", "999")),
                    body_md=nested_body,
                    source_dir=nested.parent,
                    source_file=nested,
                    nav_slug=section_slug,
                    in_nav=False,
                    bilder=nested_meta.get("bilder", None),
                )
            )
    pages.sort(key=lambda p: p.order)
    return pages


def render_nav(pages: list[Page], current_slug: str) -> str:
    items = []
    for page in pages:
        if not page.in_nav:
            continue
        href = "/" if page.slug == "" else f"/{page.slug}/"
        cls = ' class="active"' if page.slug == current_slug else ""
        items.append(f'      <li{cls}><a href="{href}">{page.nav_title}</a></li>')
    return "\n".join(items)


def rewrite_asset_links(html: str, gallery_media_base_url: str) -> str:
    """Rewrite Markdown asset links; gallery links point at the external
    media host, everything else at /assets/."""
    html = re.sub(r"(?:\.\./)+_assets/gallery/", f"{gallery_media_base_url}/", html)
    return re.sub(r"(?:\.\./)+_assets/", "/assets/", html)


def run(ctx: BuildContext, options: dict) -> None:
    source_dir = ctx.config.resolve_path(options["source_dir"])
    if not source_dir.is_dir():
        raise FileNotFoundError(f"sections: source dir not found: {source_dir}")

    pages = load_pages(source_dir)
    if not pages:
        raise ValueError(f"sections: no pages found in {source_dir}")

    media_base_url = options.get(
        "gallery_media_base_url", ctx.config.site.get("gallery_media_base_url", "")
    )
    assets_source = (
        ctx.config.resolve_path(options["assets_source"])
        if options.get("assets_source")
        else source_dir / "_assets"
    )
    gallery = GalleryBuilder(assets_source, ctx.out_dir / "assets", media_base_url)

    reports = options.get("reports") or {}
    reports_section = reports.get("section")
    reports_table_template = (
        ctx.read_template_text(reports.get("table_template", "berichte-table.html"))
        if reports_section
        else ""
    )
    report_neighbors = (
        build_report_neighbors(pages, reports_section) if reports_section else {}
    )

    links_table_slug = options.get("links_table_slug")
    gallery_page_slug = options.get("gallery_page_slug")
    footer_link_slugs = set(options.get("footer_link_slugs", ["impressum", "datenschutz"]))
    footer_links = render_footer_links(pages, footer_link_slugs)

    converter = MarkdownConverter(
        flavour=ctx.config.markdown_options.get("flavour", "homepage"),
        table_class=ctx.config.markdown_options.get("table_class"),
    )
    layout = ctx.jinja.get_template(options.get("layout", "layout.html.j2"))
    site_title = options.get("site_title", ctx.config.site.get("title", ""))
    footer = options.get("footer", "")

    def render_layout(title: str, nav_slug: str, body_html: str) -> str:
        return layout.render(
            title=title,
            site_title=site_title,
            footer=footer,
            footer_links=footer_links,
            nav=render_nav(pages, nav_slug),
            body=body_html,
            built=datetime.datetime.now().isoformat(),
        )

    for page in pages:
        body_html = converter.convert(page.body_md)
        body_html = rewrite_asset_links(body_html, media_base_url)
        needs_gallery_assets = False

        is_report = (
            reports_section
            and page.slug.startswith(f"{reports_section}/")
            and page.slug != reports_section
        )
        if is_report:
            report_date = extract_report_date(page.slug, reports_section)
            if report_date is not None:
                gallery_folder = gallery.find_gallery_folder_for_date(report_date.isoformat())
                if gallery_folder is not None:
                    gallery_folder_display = gallery.parse_gallery_folder_name(gallery_folder)[0]
                    body_html += (
                        f'\n<p class="galerie-link">'
                        f'<a href="/{gallery_page_slug or "bilder"}/#galerie-{report_date.isoformat()}">'
                        f'&#128247; Zur Bildergalerie: {_html_escape(gallery_folder_display)}'
                        f'</a></p>'
                    )
            prev_page, next_page = report_neighbors.get(page.slug, (None, None))
            body_html += "\n" + render_report_neighbors(prev_page, next_page, reports_section)
        if reports_section and page.slug == reports_section:
            body_html += "\n" + render_reports_table(pages, reports_table_template, reports_section)
        if gallery_page_slug and page.slug == gallery_page_slug:
            bilder_gallery_html = gallery.render_bilder_gallery()
            body_html += "\n" + bilder_gallery_html
            if 'class="glightbox' in bilder_gallery_html:
                needs_gallery_assets = True
        if links_table_slug and page.slug == links_table_slug:
            body_html = render_links_table(body_html)
        if page.bilder:
            gallery_html = gallery.render_gallery_for_folder(page.bilder, page.source_dir)
            if gallery_html:
                body_html += "\n" + gallery_html
                if 'class="glightbox' in gallery_html:
                    needs_gallery_assets = True

        if needs_gallery_assets:
            body_html = gallery.render_gallery_asset_includes() + "\n" + body_html

        rendered = render_layout(page.title, page.nav_slug, body_html)

        if page.slug == "":
            target = Path("index.html")
        elif is_report:
            report_slug = page.slug.split("/", 1)[1]
            target = Path(reports_section) / f"{report_slug}.html"
        else:
            target = Path(page.slug) / "index.html"

        ctx.write_output(target, rendered)
        print(f"  wrote {target.as_posix()}")

    not_found = options.get("not_found")
    if not_found:
        body_html = ctx.read_template_text(not_found.get("template", "not-found.html"))
        rendered = render_layout(
            not_found.get("title", "Seite nicht gefunden"), "__none__", body_html
        )
        ctx.write_output(not_found.get("output", "404.html"), rendered)

    sitemap = options.get("sitemap")
    if sitemap:
        base_url = sitemap.get("base_url", ctx.config.base_url).rstrip("/")
        repo_root = ctx.config.resolve_path(sitemap.get("git_repo", str(source_dir.parent)))
        xml = generate_sitemap(pages, base_url, repo_root, reports_section or "berichte")
        ctx.write_output(sitemap.get("output", "sitemap.xml"), xml)
        print("  wrote sitemap.xml")
    print("Sections build complete.")
