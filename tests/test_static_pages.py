"""Tests for the static-page conversion features: front-matter rendering
overrides, content_page directory mode, copy_assets include patterns and
excel_table splicing into a rendered output page."""

from pathlib import Path

import yaml

from sitegen.config import BuildContext, load_config
from sitegen.hp_pages import HpPageRenderer, read_content
from sitegen.steps import content_page, copy_assets, excel_table

PAGE_TEMPLATE = (
    "<title>{{ page_title }}</title>\n"
    "<meta name=\"description\" content=\"{{ meta_description }}\">\n"
    "<meta property=\"og:title\" content=\"{{ og_title }}\">\n"
    "<meta property=\"og:type\" content=\"{{ og_type }}\">\n"
    "<link rel=\"canonical\" href=\"{{ canonical_url }}\">\n"
    "<img src=\"{{ portrait_img }}\" class=\"{{ portrait_modifier }}\">\n"
    "<h1>{{ heading }}</h1>\n"
    "<main>\n{{ content }}</main>\n"
    "<foot>{{ foot_scripts }}</foot>\n"
)


def _ctx(tmp_path: Path) -> BuildContext:
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "page-template.html.j2").write_text(PAGE_TEMPLATE, encoding="utf-8")
    (templates / "default-scripts.html").write_text("<script>default</script>", encoding="utf-8")
    (templates / "foot-alt.html").write_text("<script>alt</script>", encoding="utf-8")
    (templates / "page-alt.html.j2").write_text(
        "ALT <h1>{{ heading }}</h1>\n{{ content }}", encoding="utf-8"
    )
    raw = {
        "site": {"base_url": "https://example.org/"},
        "markdown": {"flavour": "hp"},
        "output": {"dir": str(tmp_path / "out")},
        "templates": {"dir": str(templates)},
        "pipeline": [{"step": "clean_output"}],
    }
    config_path = tmp_path / "site.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    ctx = BuildContext(config=load_config(config_path))
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    return ctx


def _write_md(tmp_path: Path, name: str, text: str) -> Path:
    content = tmp_path / "content"
    content.mkdir(exist_ok=True)
    path = content / name
    path.write_text(text, encoding="utf-8")
    return path


class TestFrontMatterOverrides:
    def test_full_override_set(self, tmp_path):
        ctx = _ctx(tmp_path)
        md = _write_md(
            tmp_path,
            "index.md",
            "---\n"
            "title: Base Title\n"
            "PageTitle: Full Page Title\n"
            "Heading: Custom Heading\n"
            "Description: The description\n"
            "OgTitle: OG Title\n"
            "OgType: website\n"
            "Canonical: https://example.org/\n"
            "FootScripts: foot-alt.html\n"
            "---\n\nBody text\n",
        )
        renderer = HpPageRenderer(ctx, {"title_suffix": " | Suffix"})
        html = renderer.render_page(read_content(md))
        assert "<title>Full Page Title</title>" in html          # suffix not applied
        assert "<h1>Custom Heading</h1>" in html
        assert 'og:title" content="OG Title"' in html
        assert 'og:type" content="website"' in html
        assert 'canonical" href="https://example.org/"' in html
        assert "<foot><script>alt</script></foot>" in html

    def test_defaults_without_front_matter_keys(self, tmp_path):
        ctx = _ctx(tmp_path)
        md = _write_md(tmp_path, "plain.md", "---\ntitle: Plain\n---\n\nText\n")
        renderer = HpPageRenderer(ctx, {"title_suffix": " | S"})
        html = renderer.render_page(read_content(md))
        assert "<title>Plain | S</title>" in html
        assert 'og:type" content="article"' in html               # default preserved
        assert 'canonical" href="https://example.org/plain.html"' in html
        assert "<foot><script>default</script></foot>" in html

    def test_foot_scripts_none(self, tmp_path):
        ctx = _ctx(tmp_path)
        md = _write_md(tmp_path, "bare.md", "---\ntitle: T\nFootScripts: none\n---\nx")
        html = HpPageRenderer(ctx, {}).render_page(read_content(md))
        assert "<foot></foot>" in html

    def test_template_override(self, tmp_path):
        ctx = _ctx(tmp_path)
        md = _write_md(tmp_path, "alt.md", "---\ntitle: T\nTemplate: page-alt.html.j2\n---\nx")
        html = HpPageRenderer(ctx, {}).render_page(read_content(md))
        assert html.startswith("ALT <h1>T</h1>")


class TestContentPageDir:
    def test_renders_all_md_files(self, tmp_path):
        ctx = _ctx(tmp_path)
        _write_md(tmp_path, "one.md", "---\ntitle: One\n---\nA")
        _write_md(tmp_path, "404.md", "---\ntitle: Not found\n---\nB")
        content_page.run(ctx, {"markdown_dir": str(tmp_path / "content")})
        assert (ctx.out_dir / "one.html").is_file()
        assert (ctx.out_dir / "404.html").is_file()   # numeric slug preserved


class TestCopyAssetsInclude:
    def test_include_patterns_filter(self, tmp_path):
        ctx = _ctx(tmp_path)
        src = tmp_path / "static"
        (src / "img").mkdir(parents=True)
        (src / "img" / "a.PNG").write_bytes(b"x")
        (src / "style.css").write_bytes(b"x")
        (src / "notes.txt").write_bytes(b"x")
        copy_assets.run(ctx, {"source": str(src), "include": ["*.png", "*.css"]})
        assert (ctx.out_dir / "img" / "a.PNG").is_file()  # case-insensitive
        assert (ctx.out_dir / "style.css").is_file()
        assert not (ctx.out_dir / "notes.txt").exists()


class TestExcelSpliceIntoOutput:
    def test_template_from_output(self, tmp_path):
        import openpyxl

        ctx = _ctx(tmp_path)
        (ctx.out_dir / "mooc.html").write_text(
            "<table><tbody></tbody></table>", encoding="utf-8"
        )
        workbook = openpyxl.Workbook()
        workbook.active.append(["Title"])
        workbook.active.append(["Course A"])
        xlsx = tmp_path / "c.xlsx"
        workbook.save(xlsx)

        excel_table.run(
            ctx,
            {
                "workbook": str(xlsx),
                "columns": [{"index": 1, "type": "text"}],
                "row_template": "<tr><td>{0}</td></tr>",
                "template_file": "mooc.html",
                "template_from_output": True,
                "output": "mooc.html",
            },
        )
        html = (ctx.out_dir / "mooc.html").read_text(encoding="utf-8")
        assert "<tbody>\n<tr><td>Course A</td></tr>\n</tbody>" in html
