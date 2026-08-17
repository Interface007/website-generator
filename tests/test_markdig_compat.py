from sitegen.markdig_compat import (
    collapse_blank_lines,
    escape_text_quotes,
    markdig_slugify,
)
from sitegen.md import MarkdownConverter


class TestMarkdigSlugify:
    """Cases verified against real Markdig output of the hp site."""

    def test_umlauts_stripped_to_base(self):
        assert (
            markdig_slugify("Der Aufhänger: Ein Klumpen Bronze")
            == "der-aufhanger-ein-klumpen-bronze"
        )

    def test_sharp_s_becomes_ss(self):
        assert (
            markdig_slugify("Das Problem: Der Mond läuft nicht gleichmäßig")
            == "das-problem-der-mond-lauft-nicht-gleichmaig".replace("maig", "massig")
        )

    def test_leading_digits_dropped(self):
        assert (
            markdig_slugify("82 Fragmente und ein halbes Jahrhundert")
            == "fragmente-und-ein-halbes-jahrhundert"
        )

    def test_digits_kept_after_first_letter(self):
        assert markdig_slugify("Teil 1: Der Fund") == "teil-1-der-fund"

    def test_dot_kept_and_dropped_punctuation_swallows_spaces(self):
        assert (
            markdig_slugify("Google gab 10 Mio. $ aus, um zu lernen")
            == "google-gab-10-mio.aus-um-zu-lernen"
        )

    def test_slash_dropped_without_separator(self):
        assert markdig_slugify("SSL/TLS encryption") == "ssltls-encryption"

    def test_en_dash_dropped(self):
        assert markdig_slugify("konnte – eine Führung") == "konnte-eine-fuhrung"


class TestEscapeTextQuotes:
    def test_text_quotes_escaped_attributes_untouched(self):
        html = '<p class="x">He said "hi"</p>'
        assert escape_text_quotes(html) == '<p class="x">He said &quot;hi&quot;</p>'


class TestCollapseBlankLines:
    def test_collapses_outside_pre(self):
        assert collapse_blank_lines("<p>a</p>\n\n<p>b</p>") == "<p>a</p>\n<p>b</p>"

    def test_preserves_blank_lines_in_pre(self):
        html = "<p>a</p>\n\n<pre><code>x\n\ny</code></pre>\n\n<p>b</p>"
        assert (
            collapse_blank_lines(html)
            == "<p>a</p>\n<pre><code>x\n\ny</code></pre>\n<p>b</p>"
        )


class TestHpFlavourConversion:
    def setup_method(self):
        self.converter = MarkdownConverter(flavour="hp", table_class="gradienttable")

    def test_bare_url_autolinked(self):
        html = self.converter.convert("See https://example.org/x for details")
        assert '<a href="https://example.org/x">https://example.org/x</a>' in html

    def test_trailing_punctuation_not_linked(self):
        html = self.converter.convert("Visit https://example.org.")
        assert '<a href="https://example.org">https://example.org</a>.' in html

    def test_url_inside_word_not_linked(self):
        html = self.converter.convert("xhttps://example.org")
        assert "<a" not in html

    def test_inline_math(self):
        html = self.converter.convert(r"allows up to $2\sqrt{2} \approx 2{,}83$.")
        assert '<span class="math">\\(2\\sqrt{2} \\approx 2{,}83\\)</span>' in html

    def test_currency_not_math(self):
        html = self.converter.convert("costs $10 million and later $20 million")
        assert '<span class="math">' not in html

    def test_list_interrupts_paragraph(self):
        html = self.converter.convert("Intro line:\n- one\n- two\n")
        assert "<ul>" in html and "<li>one</li>" in html

    def test_table_class_applied(self):
        html = self.converter.convert("| a | b |\n|---|---|\n| 1 | 2 |\n")
        assert '<table class="gradienttable">' in html

    def test_trailing_newline_like_markdig(self):
        assert self.converter.convert("hello").endswith("\n")

    def test_heading_gets_markdig_id(self):
        html = self.converter.convert("## Teil 1: Der Fund\n")
        assert '<h2 id="teil-1-der-fund">' in html


class TestHomepageFlavourConversion:
    def setup_method(self):
        self.converter = MarkdownConverter(flavour="homepage")

    def test_no_heading_ids(self):
        assert self.converter.convert("## Termine\n") == "<h2>Termine</h2>"

    def test_no_autolink_no_math(self):
        html = self.converter.convert("see https://example.org and $x$")
        assert "<a" not in html and "math" not in html
