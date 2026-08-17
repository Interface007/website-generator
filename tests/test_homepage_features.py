import datetime
from dataclasses import dataclass
from pathlib import Path

from sitegen.gallery_builder import GalleryBuilder
from sitegen.homepage_features import (
    build_report_neighbors,
    extract_report_author,
    extract_report_date,
    generate_sitemap,
    normalize_author_name,
    render_footer_links,
    render_links_table,
    render_report_neighbors,
    render_reports_table,
)

TABLE_TEMPLATE = "<table id=\"berichte-table\"><tbody>\n__ROWS_HTML__\n</tbody></table>"


@dataclass
class FakePage:
    slug: str
    title: str
    body_md: str = ""
    nav_title: str = ""
    in_nav: bool = False
    source_file: Path = Path("x.md")


class TestReportHelpers:
    def test_extract_report_date(self):
        assert extract_report_date("berichte/2014-06-08-vatertag") == datetime.date(2014, 6, 8)
        assert extract_report_date("berichte/87-unsere-teilnahme") is None
        assert extract_report_date("berichte/2014-13-99-invalid") is None
        assert extract_report_date("berichte") is None

    def test_extract_report_author(self):
        assert extract_report_author("text\n**Autor:** Hans Meier\nmore") == "Hans Meier"
        assert extract_report_author("no author line") == "Unbekannt"

    def test_normalize_author_name(self):
        assert normalize_author_name("  Hans   Meier ") == "Hans Meier"
        assert normalize_author_name("Meier,Hans") == "Meier. Hans"
        assert normalize_author_name("A/B") == "A / B"


class TestReportsTable:
    def _pages(self):
        return [
            FakePage("berichte", "Berichte"),
            FakePage("berichte/2014-06-08-alt", "Alt & Neu", "**Autor:** A"),
            FakePage("berichte/2025-01-02-neu", "Neu", "**Autor:** B"),
            FakePage("berichte/kein-datum", "Ohne Datum"),
            FakePage("other", "Other"),
        ]

    def test_rows_sorted_by_date_descending(self):
        html = render_reports_table(self._pages(), TABLE_TEMPLATE)
        assert html.index("2025-01-02") < html.index("2014-06-08")
        assert 'data-order="2014-06-08">08.06.2014<' in html
        assert 'href="./2025-01-02-neu.html"' in html
        assert "Alt &amp; Neu" in html
        assert "Ohne Datum" not in html   # undated reports excluded

    def test_template_placeholder_replaced(self):
        html = render_reports_table(self._pages(), TABLE_TEMPLATE)
        assert "__ROWS_HTML__" not in html


class TestReportNeighbors:
    def test_prev_next_chronological(self):
        pages = [
            FakePage("berichte/2014-06-08-a", "A"),
            FakePage("berichte/2025-01-02-c", "C"),
            FakePage("berichte/2020-05-05-b", "B"),
        ]
        neighbors = build_report_neighbors(pages)
        prev_b, next_b = neighbors["berichte/2020-05-05-b"]
        assert prev_b.slug == "berichte/2014-06-08-a"
        assert next_b.slug == "berichte/2025-01-02-c"
        assert neighbors["berichte/2014-06-08-a"][0] is None
        assert neighbors["berichte/2025-01-02-c"][1] is None

    def test_render_neighbors(self):
        prev_page = FakePage("berichte/2014-06-08-a", 'A "quoted"')
        html = render_report_neighbors(prev_page, None)
        assert 'href="/berichte/2014-06-08-a.html"' in html
        assert "&#8592; Vorheriger Bericht" in html
        assert "&quot;quoted&quot;" in html
        assert "Nächster" not in html

    def test_render_neighbors_empty(self):
        html = render_report_neighbors(None, None)
        assert html == '<nav class="report-nav" aria-label="Bericht-Navigation"></nav>'


class TestLinksTable:
    def test_list_becomes_table(self):
        body = (
            "<p>Intro</p>\n<ul>\n"
            '<li><strong>NDR</strong> — <a href="https://ndr.de">ndr.de</a></li>\n'
            '<li><strong>Chor</strong> — <a href="https://x.de">x.de</a></li>\n'
            "</ul>"
        )
        html = render_links_table(body)
        assert "<table" in html and "<ul>" not in html
        assert '<tr><td><strong>NDR</strong></td><td><a href="https://ndr.de">ndr.de</a></td></tr>' in html

    def test_without_list_unchanged(self):
        assert render_links_table("<p>nur text</p>") == "<p>nur text</p>"


class TestFooterLinks:
    def test_footer_links(self):
        pages = [
            FakePage("impressum", "Impressum", nav_title="Impressum"),
            FakePage("datenschutz", "Datenschutz", nav_title="Datenschutz"),
            FakePage("kontakt", "Kontakt", nav_title="Kontakt"),
        ]
        html = render_footer_links(pages)
        assert html == (
            '<a href="/impressum/">Impressum</a> | <a href="/datenschutz/">Datenschutz</a>'
        )


class TestSitemap:
    def test_urls_and_priorities(self, tmp_path):
        pages = [
            FakePage("", "Home", in_nav=True, source_file=tmp_path / "a.md"),
            FakePage("termine", "Termine", in_nav=True, source_file=tmp_path / "b.md"),
            FakePage("berichte/2024-01-01-x", "X", source_file=tmp_path / "c.md"),
        ]
        xml = generate_sitemap(pages, "https://example.org", tmp_path)
        assert "<loc>https://example.org/</loc>" in xml
        assert "<loc>https://example.org/termine/</loc>" in xml
        assert "<loc>https://example.org/berichte/2024-01-01-x.html</loc>" in xml
        assert "<priority>1.0</priority>" in xml
        assert "<priority>0.8</priority>" in xml
        assert "<priority>0.6</priority>" in xml


class TestGalleryBuilder:
    def _builder(self, tmp_path: Path) -> GalleryBuilder:
        return GalleryBuilder(tmp_path / "_assets", tmp_path / "out", "https://media.example/gallery")

    def _make_tree(self, tmp_path: Path) -> Path:
        root = tmp_path / "_assets" / "gallery"
        (root / "2024" / "2024-06-01-Sommerfest").mkdir(parents=True)
        (root / "2024" / "2024-06-01-Sommerfest" / "bild_eins.jpg").write_bytes(b"x")
        (root / "2024" / "2024-06-01-Sommerfest" / "clip-rotate-left.mp4").write_bytes(b"x")
        (root / "loose.png").write_bytes(b"x")
        return root

    def test_output_rel_paths(self):
        assert GalleryBuilder.gallery_output_rel_path(Path("a/b.jpg"), ".jpg") == Path("a/b.webp")
        assert GalleryBuilder.gallery_output_rel_path(Path("a/b.png"), ".png") == Path("a/b.png")
        assert GalleryBuilder.gallery_video_thumb_rel_path(Path("a/c.mp4")) == Path("a/c.webp")

    def test_title_and_rotation(self):
        title, rotation = GalleryBuilder.parse_media_title_and_rotation(
            Path("clip_eins-rotate-left.mp4")
        )
        assert title == "clip eins" and rotation == "left"
        title, rotation = GalleryBuilder.parse_media_title_and_rotation(Path("bild_zwei.jpg"))
        assert title == "bild zwei" and rotation is None

    def test_folder_name_date_display(self):
        assert GalleryBuilder.parse_gallery_folder_name("2024-06-01-Sommerfest") == (
            "01.06.2024 - Sommerfest",
            True,
        )
        assert GalleryBuilder.parse_gallery_folder_name("Sonstiges") == ("Sonstiges", False)

    def test_collect_two_level_grouping(self, tmp_path):
        self._make_tree(tmp_path)
        grouped = self._builder(tmp_path).collect_gallery_images()
        assert set(grouped) == {"2024", "Sonstiges"}
        assert set(grouped["2024"]) == {"2024-06-01-Sommerfest"}
        entries = grouped["2024"]["2024-06-01-Sommerfest"]
        jpg = next(e for e in entries if e[3] == "image")
        assert jpg[0].endswith("/full/2024/2024-06-01-Sommerfest/bild_eins.webp")
        video = next(e for e in entries if e[3] == "video")
        assert video[1].endswith("/thumbs/2024/2024-06-01-Sommerfest/clip-rotate-left.webp")
        assert video[4] == "left"

    def test_render_accordion(self, tmp_path):
        self._make_tree(tmp_path)
        html = self._builder(tmp_path).render_bilder_gallery()
        assert "galerie-accordion-item" in html
        assert 'data-gallery-date="2024-06-01"' in html
        assert "01.06.2024 - Sommerfest" in html
        assert "galerie-play-button" in html
        assert 'data-rotate="left"' in html

    def test_find_gallery_folder_for_date(self, tmp_path):
        self._make_tree(tmp_path)
        builder = self._builder(tmp_path)
        assert builder.find_gallery_folder_for_date("2024-06-01") == "2024-06-01-Sommerfest"
        assert builder.find_gallery_folder_for_date("1999-01-01") is None

    def test_render_gallery_for_folder(self, tmp_path):
        self._make_tree(tmp_path)
        builder = self._builder(tmp_path)
        html = builder.render_gallery_for_folder("gallery/2024/2024-06-01-Sommerfest", tmp_path)
        assert 'data-gallery="folder-gallery"' in html
        assert "/full/2024/2024-06-01-Sommerfest/bild_eins.webp" in html
        assert builder.render_gallery_for_folder("does/not/exist", tmp_path) == ""

    def test_render_empty_gallery(self, tmp_path):
        assert "keine Galerie-Bilder" in self._builder(tmp_path).render_bilder_gallery()
