"""Integration-level tests for pipeline steps on synthetic sites."""

import textwrap
from pathlib import Path

import yaml

from sitegen.config import BuildContext, load_config
from sitegen.steps import sections as sections_step
from sitegen.steps import sitemap as sitemap_step
from sitegen.steps.sections import load_pages, render_nav


def _make_config(tmp_path: Path, extra: dict | None = None) -> BuildContext:
    raw = {
        "site": {"name": "test", "base_url": "https://example.org/"},
        "output": {"dir": str(tmp_path / "out")},
        "templates": {"dir": str(tmp_path / "templates")},
        "pipeline": [{"step": "clean_output"}],
    }
    raw.update(extra or {})
    config_path = tmp_path / "site.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return BuildContext(config=load_config(config_path))


def _make_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "home").mkdir(parents=True)
    (source / "home" / "index.md").write_text(
        "---\ntitle: Startseite\nnav_title: Home\norder: 1\n---\n\nHallo\n",
        encoding="utf-8",
    )
    (source / "berichte").mkdir()
    (source / "berichte" / "index.md").write_text(
        "---\ntitle: Berichte\norder: 2\n---\n\nAlle Berichte\n", encoding="utf-8"
    )
    (source / "berichte" / "2024-05-01-Erster Bericht.md").write_text(
        "---\ntitle: Erster Bericht\n---\n\n**Autor:** Hans\n\nText\n", encoding="utf-8"
    )
    (source / "berichte" / "2025-06-02-zweiter.md").write_text(
        "---\ntitle: Zweiter Bericht\n---\n\n**Autor:** Karl\n\nText\n", encoding="utf-8"
    )
    (source / "impressum").mkdir()
    (source / "impressum" / "index.md").write_text(
        "---\ntitle: Impressum\norder: 9\nin_nav: false\n---\n\nImpressum\n",
        encoding="utf-8",
    )
    (source / "_assets").mkdir()
    return source


class TestLoadPages:
    def test_structure(self, tmp_path):
        pages = load_pages(_make_source(tmp_path))
        slugs = [(p.slug, p.in_nav) for p in pages]
        assert ("", True) in slugs                                 # "home" -> root
        assert ("berichte", True) in slugs
        assert ("berichte/2024-05-01-erster-bericht", False) in slugs  # slug normalized
        assert ("impressum", False) in slugs                       # in_nav front matter
        home = next(p for p in pages if p.slug == "")
        assert home.order == 1 and home.nav_title == "Home"

    def test_extensionless_markdown_detail(self, tmp_path):
        source = _make_source(tmp_path)
        (source / "berichte" / "2023-01-01-ohne-endung").write_text(
            "---\ntitle: Ohne Endung\n---\n\nText\n", encoding="utf-8"
        )
        pages = load_pages(source)
        assert any(p.slug == "berichte/2023-01-01-ohne-endung" for p in pages)

    def test_nav_highlights_current(self, tmp_path):
        pages = load_pages(_make_source(tmp_path))
        nav = render_nav(pages, "berichte")
        assert '<li class="active"><a href="/berichte/">Berichte</a></li>' in nav
        assert '<li><a href="/">Home</a></li>' in nav
        assert "erster-bericht" not in nav      # detail page not in nav
        assert "Impressum" not in nav           # in_nav: false respected


class TestSectionsStep:
    def test_renders_pages_reports_and_404(self, tmp_path):
        source = _make_source(tmp_path)
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "layout.html.j2").write_text(
            "<title>{{ title }} – {{ site_title }}</title>\n"
            "<nav>\n{{ nav }}\n</nav>\n<main>\n{{ body }}\n</main>\n"
            "<footer>{{ footer_links }} {{ footer }} built={{ built }}</footer>\n",
            encoding="utf-8",
        )
        (templates / "berichte-table.html").write_text(
            "<table id=\"berichte-table\"><tbody>\n__ROWS_HTML__\n</tbody></table>",
            encoding="utf-8",
        )
        (templates / "not-found.html").write_text(
            "<section class=\"not-found\">404</section>", encoding="utf-8"
        )
        ctx = _make_config(tmp_path)
        sections_step.run(
            ctx,
            {
                "source_dir": str(source),
                "site_title": "Testchor",
                "footer": "© Testchor",
                "reports": {"section": "berichte", "table_template": "berichte-table.html"},
                "footer_link_slugs": ["impressum"],
                "not_found": {"title": "Nicht gefunden", "template": "not-found.html"},
                "sitemap": {"base_url": "https://example.org/", "git_repo": str(tmp_path)},
            },
        )
        out = ctx.out_dir
        assert (out / "index.html").is_file()
        assert (out / "berichte" / "index.html").is_file()
        # report detail pages are flat .html files, not directories
        assert (out / "berichte" / "2024-05-01-erster-bericht.html").is_file()
        assert (out / "404.html").is_file()

        berichte = (out / "berichte" / "index.html").read_text(encoding="utf-8")
        assert "berichte-table" in berichte
        assert 'href="./2024-05-01-erster-bericht.html">Erster Bericht</a>' in berichte
        assert ">Hans<" in berichte
        assert 'data-order="2024-05-01">01.05.2024<' in berichte

        # previous/next navigation between the two dated reports
        first = (out / "berichte" / "2024-05-01-erster-bericht.html").read_text(encoding="utf-8")
        assert 'href="/berichte/2025-06-02-zweiter.html"' in first
        assert "Nächster Bericht" in first

        # footer links + 404 body from template
        home = (out / "index.html").read_text(encoding="utf-8")
        assert "<title>Startseite – Testchor</title>" in home
        assert '<a href="/impressum/">Impressum</a>' in home
        not_found = (out / "404.html").read_text(encoding="utf-8")
        assert '<section class="not-found">404</section>' in not_found

        # sitemap: report URL flat, trailing slash for sections, priorities
        xml = (out / "sitemap.xml").read_text(encoding="utf-8")
        assert "<loc>https://example.org/</loc>" in xml
        assert "<loc>https://example.org/berichte/2024-05-01-erster-bericht.html</loc>" in xml
        assert "<priority>0.6</priority>" in xml


class TestSitemapStep:
    def test_priorities_order_and_content_dates(self, tmp_path):
        scan = tmp_path / "scan"
        scan.mkdir()
        for name in ("index.html", "b.html", "article-x.html", "google123.html"):
            (scan / name).write_text("x", encoding="utf-8")

        ctx = _make_config(tmp_path)
        ctx.out_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime

        ctx.content_dates["article-x.html"] = datetime(2026, 7, 1)
        sitemap_step.run(
            ctx,
            {
                "scan_dir": str(scan),
                "exclude": ["google*"],
                "priorities": [
                    {"pattern": "index.html", "priority": "1.00"},
                    {"pattern": "article-*", "priority": "0.64"},
                ],
                "default_priority": "0.80",
            },
        )
        xml = (ctx.out_dir / "sitemap.xml").read_text(encoding="utf-8")
        assert "google123" not in xml
        # home first, then alphabetical
        assert xml.index("https://example.org/</loc>") < xml.index("article-x.html")
        assert "<lastmod>2026-07-01</lastmod>" in xml
        assert "<priority>1.00</priority>" in xml
        assert "<priority>0.64</priority>" in xml
        assert "<priority>0.80</priority>" in xml


class TestExcelStep:
    def test_rows_rendered_and_sorted(self, tmp_path):
        import openpyxl

        from sitegen.steps import excel_table

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["Title", "Platform", "Provider", "Date"])
        from datetime import datetime

        sheet.append(["Old Course", "P1", "X", datetime(2020, 1, 2)])
        sheet.append(["New Course", "P2", "Y", datetime(2026, 5, 20)])
        xlsx = tmp_path / "courses.xlsx"
        workbook.save(xlsx)

        template = tmp_path / "template.html"
        template.write_text("<table><tbody></tbody></table>", encoding="utf-8")

        ctx = _make_config(tmp_path)
        ctx.out_dir.mkdir(parents=True, exist_ok=True)
        excel_table.run(
            ctx,
            {
                "workbook": str(xlsx),
                "columns": [
                    {"index": 1, "type": "text"},
                    {"index": 2, "type": "text"},
                    {"index": 3, "type": "text"},
                    {"index": 4, "type": "date", "format": "%Y-%m-%d"},
                ],
                "sort_by": 3,
                "row_template": '<tr><td>{0}</td><td>{1}</td><td>{2}</td><td class="col-date">{3}</td></tr>',
                "template_file": str(template),
                "output": "mooc.html",
            },
        )
        html = (ctx.out_dir / "mooc.html").read_text(encoding="utf-8")
        assert html.index("New Course") < html.index("Old Course")
        assert '<td class="col-date">2026-05-20</td>' in html
        assert html.startswith("<table><tbody>")
