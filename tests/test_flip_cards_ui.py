"""Source-contract tests for the generated flip-card experience."""

from pathlib import Path


ROOT = Path(__file__).parents[1]
TEMPLATES = ROOT / "templates" / "matzen"


def test_articles_teaser_is_one_link_with_compact_svg() -> None:
    intro = (TEMPLATES / "articles-overview-intro.md").read_text(encoding="utf-8")

    assert '<a class="flip-teaser__link" href="flip-cards.html">' in intro
    assert '<svg class="flip-teaser__icon"' in intro
    assert intro.index("flip-teaser__link") < intro.index("Want something more playful")
    assert intro.index("before diving into the longer articles") < intro.index("</a>")


def test_mobile_layout_places_filter_after_quiz() -> None:
    template = (TEMPLATES / "page-flip-cards.html.j2").read_text(encoding="utf-8")
    css = (TEMPLATES / "static" / "themes" / "style.css").read_text(encoding="utf-8")

    assert 'class="row flip-layout"' in template
    assert "flip-layout__portrait" in template
    assert ".flip-layout #layout-content" in css
    assert "order: 1" in css
    assert ".flip-layout #aside-first" in css
    assert "order: 2" in css


def test_card_labels_include_localized_domain() -> None:
    script = (TEMPLATES / "static" / "script" / "flip-cards.js").read_text(encoding="utf-8")

    assert 'domain: "Bereich"' in script
    assert 'domain: "Domain"' in script
    assert "pick.area" in script
    assert "this.el.tagQ.textContent" in script
    assert "this.el.tagA.textContent" in script