"""Feature renderers specific to the homepage (Shantychor) site.

Port of ``semhps/scripts/reporting.py`` plus the links-table and
footer-link helpers from ``build.py``: date-based report slugs, the
Berichte DataTable, previous/next report navigation, the links page
table transform, and the page-based sitemap.
"""

from __future__ import annotations

import datetime
import html
import re
import subprocess
from html import escape as _html_escape
from pathlib import Path
from typing import Any

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


# -- git / sitemap --------------------------------------------------------

def get_git_lastmod(file_path: Path, repo_root: Path) -> str:
    """Return the ISO date (YYYY-MM-DD) of the last git commit touching
    file_path; today when the file is untracked or git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", str(file_path)],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        timestamp = result.stdout.strip()
        if timestamp:
            return timestamp[:10]
    except FileNotFoundError:
        pass
    return datetime.date.today().isoformat()


def generate_sitemap(
    pages: list[Any], site_base_url: str, repo_root: Path, reports_section: str = "berichte"
) -> str:
    """Build a Google-compatible XML sitemap for all pages."""
    entries: list[str] = []
    for page in pages:
        if page.slug.startswith(f"{reports_section}/") and page.slug != reports_section:
            report_slug = page.slug.split("/", 1)[1]
            loc = f"{site_base_url}/{reports_section}/{report_slug}.html"
        elif page.slug == "":
            loc = f"{site_base_url}/"
        else:
            loc = f"{site_base_url}/{page.slug}/"

        lastmod = get_git_lastmod(page.source_file, repo_root)

        if page.slug == "":
            priority = "1.0"
        elif page.in_nav:
            priority = "0.8"
        else:
            priority = "0.6"

        entries.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    entries_xml = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries_xml}\n"
        "</urlset>\n"
    )


# -- reports --------------------------------------------------------------

def extract_report_date(slug: str, section: str = "berichte") -> datetime.date | None:
    """Extract the date from a slug like ``berichte/2014-06-08-foo``."""
    match = re.match(rf"^{re.escape(section)}/(\d{{4}})-(\d{{2}})-(\d{{2}})-", slug)
    if not match:
        return None
    try:
        return datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def normalize_author_name(author: str) -> str:
    """Normalize author display names for consistent table output."""
    normalized = author.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.replace(",", ". ")
    normalized = re.sub(r"\s*/\s*", " / ", normalized)
    normalized = re.sub(
        r"\b([A-ZÄÖÜ])\.\s*([A-ZÄÖÜ][a-zäöüß]+)",
        r"\1. \2",
        normalized,
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def extract_report_author(body_md: str) -> str:
    """Extract the author from a report Markdown line like ``**Autor:** Name``."""
    match = re.search(r"(?m)^\*\*Autor:\*\*\s*(.+)$", body_md)
    if not match:
        return "Unbekannt"
    return normalize_author_name(match.group(1).strip())


def render_reports_table(pages: list[Any], template: str, section: str = "berichte") -> str:
    """Render the Berichte DataTable (date/title/author, newest first) into
    the ``__ROWS_HTML__`` placeholder of the table template."""
    reports: list[tuple[datetime.date, str, str, str]] = []
    for page in pages:
        if page.slug == section or not page.slug.startswith(f"{section}/"):
            continue
        report_date = extract_report_date(page.slug, section)
        if report_date is None:
            continue
        report_slug = page.slug.split("/", 1)[1]
        reports.append(
            (
                report_date,
                report_slug,
                page.title,
                extract_report_author(page.body_md),
            )
        )

    reports.sort(key=lambda row: row[0], reverse=True)

    rows = []
    for report_date, report_slug, report_title, report_author in reports:
        date_iso = report_date.isoformat()
        date_display = report_date.strftime("%d.%m.%Y")
        rows.append(
            "        <tr>"
            f'<td data-order="{date_iso}">{date_display}</td>'
            f"<td><a href=\"./{report_slug}.html\">{html.escape(report_title)}</a></td>"
            f"<td>{html.escape(report_author)}</td>"
            "</tr>"
        )

    rows_html = "\n".join(rows)
    return template.replace("__ROWS_HTML__", rows_html)


def build_report_neighbors(
    pages: list[Any], section: str = "berichte"
) -> dict[str, tuple[Any | None, Any | None]]:
    """Build the previous/next mapping for report detail pages in
    chronological order."""
    reports: list[Any] = []
    for page in pages:
        if page.slug == section or not page.slug.startswith(f"{section}/"):
            continue
        if extract_report_date(page.slug, section) is None:
            continue
        reports.append(page)

    reports.sort(key=lambda p: (extract_report_date(p.slug, section), p.slug))

    neighbors: dict[str, tuple[Any | None, Any | None]] = {}
    for idx, page in enumerate(reports):
        prev_page = reports[idx - 1] if idx > 0 else None
        next_page = reports[idx + 1] if idx < len(reports) - 1 else None
        neighbors[page.slug] = (prev_page, next_page)
    return neighbors


def render_report_neighbors(
    prev_page: Any | None, next_page: Any | None, section: str = "berichte"
) -> str:
    """Render previous/next report links for a report detail page."""

    def _href(page: Any) -> str:
        report_slug = page.slug.split("/", 1)[1]
        return f"/{section}/{report_slug}.html"

    prev_html = ""
    if prev_page is not None:
        prev_html = (
            f'<a class="report-nav-item" href="{_href(prev_page)}" '
            f'title="{_html_escape(prev_page.title)}">&#8592; Vorheriger Bericht</a>'
        )

    next_html = ""
    if next_page is not None:
        next_html = (
            f'<a class="report-nav-item report-nav-item-next" href="{_href(next_page)}" '
            f'title="{_html_escape(next_page.title)}">Nächster Bericht &#8594;</a>'
        )

    return (
        '<nav class="report-nav" aria-label="Bericht-Navigation">'
        f"{prev_html}{next_html}"
        "</nav>"
    )


# -- links page -----------------------------------------------------------

def render_links_table(body_html: str) -> str:
    """Transform a Markdown list of ``**description** — link`` items into an
    aligned two-column HTML table (used on the links page)."""
    list_match = re.search(r"<ul>(.*?)</ul>", body_html, re.DOTALL)
    if not list_match:
        return body_html

    items = re.findall(r"<li>(.*?)</li>", list_match.group(1), re.DOTALL)
    if not items:
        return body_html

    rows = []
    for item in items:
        item = item.strip()
        strong_match = re.search(r"<strong>(.*?)</strong>", item)
        if not strong_match:
            continue

        description = f"<strong>{strong_match.group(1)}</strong>"
        after_strong = item[strong_match.end():]
        link_html = re.sub(r"^\s*—\s*", "", after_strong).strip()

        if link_html:
            rows.append((description, link_html))

    if not rows:
        return body_html

    table_rows = [
        f"<tr><td>{description}</td><td>{link_html}</td></tr>"
        for description, link_html in rows
    ]
    table_html = (
        '<table style="border-collapse: collapse; width: 100%;">\n'
        + "\n".join(table_rows)
        + "\n</table>"
    )

    return body_html[: list_match.start()] + table_html + body_html[list_match.end():]


# -- footer ---------------------------------------------------------------

def render_footer_links(pages: list[Any], slugs: set[str] | None = None) -> str:
    """Generate footer links (Impressum / Datenschutz by default)."""
    wanted = slugs if slugs is not None else {"impressum", "datenschutz"}
    links = []
    for page in pages:
        if page.slug in wanted:
            links.append(f'<a href="/{page.slug}/">{page.nav_title}</a>')
    return " | ".join(links)
