"""Tests for the card-collection feature (clean Markdown cards + templates)."""

from pathlib import Path

import pytest
import yaml

from sitegen.cards import (
    CardError,
    load_cards,
    load_icon_library,
    render_grid,
    split_yaml_front_matter,
)
from sitegen.config import BuildContext, load_config
from sitegen.md import MarkdownConverter
from sitegen.steps import cards as cards_step


class TestSplitYamlFrontMatter:
    def test_parses_lists_and_maps(self):
        meta, body = split_yaml_front_matter(
            "---\n"
            "variant: automation\n"
            "tags: [A, B, C]\n"
            "facts:\n"
            "  - label: Courses\n"
            "    value: \"12,000+\"\n"
            "---\n\nBody text\n"
        )
        assert meta["variant"] == "automation"
        assert meta["tags"] == ["A", "B", "C"]
        assert meta["facts"] == [{"label": "Courses", "value": "12,000+"}]
        assert body.lstrip("\n") == "Body text\n"

    def test_no_front_matter(self):
        meta, body = split_yaml_front_matter("Just text")
        assert meta == {} and body == "Just text"

    def test_non_mapping_rejected(self):
        with pytest.raises(CardError):
            split_yaml_front_matter("---\n- a\n- b\n---\nx")


class TestIconLibrary:
    def test_loads_svgs_by_stem(self, tmp_path):
        (tmp_path / "cloud.svg").write_text("<svg>cloud</svg>\n", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "home.svg").write_text("<svg>home</svg>", encoding="utf-8")
        icons = load_icon_library(tmp_path)
        assert icons == {"cloud": "<svg>cloud</svg>", "home": "<svg>home</svg>"}

    def test_missing_dir_returns_empty(self, tmp_path):
        assert load_icon_library(tmp_path / "nope") == {}


def _project_template(tmp_path: Path):
    from jinja2 import Environment, FileSystemLoader

    tdir = tmp_path / "t"
    tdir.mkdir()
    (tdir / "card.j2").write_text(
        '<div class="project-card {{ variant|e }}">'
        "<span class=\"icon\">{{ icon_svg }}</span>"
        "<h3>{{ title|e }}</h3>{{ description }}"
        "{% if tags %}<ul>{% for t in tags %}<li>{{ t|e }}</li>{% endfor %}</ul>{% endif %}"
        "{% if link %}<a href=\"{{ link|e }}\">go</a>{% endif %}"
        "</div>\n",
        encoding="utf-8",
    )
    env = Environment(loader=FileSystemLoader(str(tdir)), autoescape=False)
    return env.get_template("card.j2")


class TestLoadAndRender:
    def _make_cards(self, tmp_path: Path):
        d = tmp_path / "coll"
        d.mkdir()
        (d / "02.md").write_text(
            "---\nvariant: personal\nglyph: shield\ntitle: Second & Last\n---\n\nBody two\n",
            encoding="utf-8",
        )
        (d / "01.md").write_text(
            "---\nvariant: automation\nglyph: cloud\ntitle: First\n"
            "tags: [X, Y]\nlink: mooc.html\n---\n\n**Bold** body\n",
            encoding="utf-8",
        )
        return d

    def test_cards_sorted_by_filename(self, tmp_path):
        conv = MarkdownConverter(flavour="hp")
        loaded = load_cards(self._make_cards(tmp_path), conv)
        assert [c.meta["title"] for c in loaded] == ["First", "Second & Last"]
        assert "<strong>Bold</strong>" in loaded[0].body_html

    def test_render_grid_escapes_and_resolves_icons(self, tmp_path):
        conv = MarkdownConverter(flavour="hp")
        loaded = load_cards(self._make_cards(tmp_path), conv)
        icons = {"cloud": "<svg>C</svg>", "shield": "<svg>S</svg>"}
        grid = render_grid(loaded, _project_template(tmp_path), "projects-grid", icons, "glyph")
        assert grid.startswith('<div class="projects-grid">')
        assert grid.rstrip().endswith("</div>")
        assert "<svg>C</svg>" in grid and "<svg>S</svg>" in grid
        assert "Second &amp; Last" in grid          # title HTML-escaped
        assert "<li>X</li><li>Y</li>" in grid        # tags rendered
        assert '<a href="mooc.html">' in grid        # link rendered

    def test_unknown_icon_raises(self, tmp_path):
        conv = MarkdownConverter(flavour="hp")
        loaded = load_cards(self._make_cards(tmp_path), conv)
        with pytest.raises(CardError, match="unknown icon"):
            render_grid(loaded, _project_template(tmp_path), "g", {}, "glyph")

    def test_empty_collection_raises(self, tmp_path):
        (tmp_path / "empty").mkdir()
        with pytest.raises(CardError):
            load_cards(tmp_path / "empty", MarkdownConverter(flavour="hp"))


class TestCardsStep:
    def _ctx(self, tmp_path: Path) -> BuildContext:
        templates = tmp_path / "templates"
        (templates / "icons" / "project").mkdir(parents=True)
        (templates / "icons" / "project" / "cloud.svg").write_text("<svg>C</svg>", encoding="utf-8")
        (templates / "card-project.html.j2").write_text(
            '<div class="project-card {{ variant|e }}">{{ icon_svg }}'
            "<h3>{{ title|e }}</h3>{{ description }}</div>",
            encoding="utf-8",
        )
        raw = {
            "site": {"base_url": "https://example.org/"},
            "markdown": {"flavour": "hp"},
            "output": {"dir": str(tmp_path / "out")},
            "templates": {"dir": str(templates)},
            "pipeline": [{"step": "clean_output"}],
        }
        cfg = tmp_path / "site.yaml"
        cfg.write_text(yaml.safe_dump(raw), encoding="utf-8")
        ctx = BuildContext(config=load_config(cfg))
        ctx.out_dir.mkdir(parents=True, exist_ok=True)
        return ctx

    def test_splices_grid_into_page(self, tmp_path):
        ctx = self._ctx(tmp_path)
        coll = tmp_path / "cards"
        coll.mkdir()
        (coll / "01.md").write_text(
            "---\nvariant: automation\nglyph: cloud\ntitle: Card One\n---\n\nProse\n",
            encoding="utf-8",
        )
        # page produced by an earlier step, with the placeholder
        (ctx.out_dir / "page.html").write_text(
            "<main>\n<p class=\"intro-text\">Intro</p>\n<!-- cards -->\n</main>", encoding="utf-8"
        )
        cards_step.run(
            ctx,
            {
                "collection": str(coll),
                "card_template": "card-project.html.j2",
                "grid_class": "projects-grid",
                "icon_dir": "project",
                "page": "page.html",
            },
        )
        html = (ctx.out_dir / "page.html").read_text(encoding="utf-8")
        assert "<!-- cards -->" not in html
        assert '<div class="projects-grid">' in html
        assert "<h3>Card One</h3>" in html
        assert "<svg>C</svg>" in html
        assert '<p class="intro-text">Intro</p>' in html   # surrounding page kept

    def test_missing_placeholder_raises(self, tmp_path):
        ctx = self._ctx(tmp_path)
        coll = tmp_path / "cards"
        coll.mkdir()
        (coll / "01.md").write_text(
            "---\nvariant: automation\nglyph: cloud\ntitle: X\n---\n\nY\n", encoding="utf-8"
        )
        (ctx.out_dir / "page.html").write_text("<main>no marker</main>", encoding="utf-8")
        with pytest.raises(CardError, match="placeholder"):
            cards_step.run(
                ctx,
                {
                    "collection": str(coll),
                    "card_template": "card-project.html.j2",
                    "grid_class": "projects-grid",
                    "icon_dir": "project",
                    "page": "page.html",
                },
            )
