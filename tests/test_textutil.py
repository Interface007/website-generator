from datetime import datetime

from sitegen.textutil import (
    extract_language,
    extract_title,
    html_encode,
    is_sync_artifact,
    replace_wiki_links,
    slugify,
    strip_date_prefix,
    try_parse_date,
)


class TestHtmlEncode:
    def test_basic_entities(self):
        assert html_encode('<a href="x">&\'</a>') == "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;"

    def test_latin1_range_encoded_numerically(self):
        # Replicates .NET WebUtility.HtmlEncode: U+00A0..U+00FF as decimal refs
        assert html_encode("Wünschenswert") == "W&#252;nschenswert"
        assert html_encode("täuscht") == "t&#228;uscht"

    def test_chars_above_ff_left_alone(self):
        assert html_encode("a – b „x") == "a – b „x"

    def test_none_and_empty(self):
        assert html_encode(None) == ""
        assert html_encode("") == ""


class TestSlugify:
    def test_umlauts_transliterated(self):
        assert slugify("Über Öl ß") == "ueber-oel-ss"

    def test_article_filename(self):
        name = "2026-07-02 - Der Kosmos aus Bronze - de-DE"
        assert slugify(name) == "2026-07-02-der-kosmos-aus-bronze-de-de"

    def test_collapses_and_trims_dashes(self):
        assert slugify("  a -- b!  ") == "a-b"

    def test_empty_falls_back(self):
        assert slugify("!!!") == "article"


class TestNameHelpers:
    def test_strip_date_prefix(self):
        assert strip_date_prefix("2024-06-22 - Some Title") == "Some Title"
        assert strip_date_prefix("No Date Here") == "No Date Here"

    def test_extract_language(self):
        assert extract_language("Title - de-DE") == "de-DE"
        assert extract_language("Title - en-US") == "en-US"
        assert extract_language("Title") == ""

    def test_sync_artifacts(self):
        assert is_sync_artifact("article_WK-GCCR8F4_x")
        assert is_sync_artifact("draft-Conflict")
        assert not is_sync_artifact("2026-06-17 - Psychological Safety - en-US")


class TestTryParseDate:
    def test_iso(self):
        assert try_parse_date("2026-07-02") == datetime(2026, 7, 2)

    def test_garbage(self):
        assert try_parse_date("privacypol") is None
        assert try_parse_date(None) is None
        assert try_parse_date("") is None


class TestExtractTitle:
    def test_heading_and_following_rule_removed(self):
        body = "\n# The Title\n\n---\n\n## Section\n\ntext\n"
        title, rest = extract_title(body)
        assert title == "The Title"
        assert rest.startswith("## Section")

    def test_no_heading(self):
        title, rest = extract_title("just text")
        assert title is None
        assert rest == "just text"

    def test_content_before_heading_is_dropped(self):
        # C# behaviour: everything before the first level-1 heading goes away
        title, rest = extract_title("preamble\n# T\nbody")
        assert title == "T"
        assert rest == "body"


class TestWikiLinks:
    def _resolve(self, target):
        if target.lower() == "2026-01-01 - known - en-us":
            return "Known Title", "article-known.html"
        return None

    def test_known_target_uses_title(self):
        out = replace_wiki_links("see [[2026-01-01 - Known - en-US]]", self._resolve)
        assert out == "see [Known Title](article-known.html)"

    def test_alias_wins(self):
        out = replace_wiki_links("see [[2026-01-01 - Known - en-US|alias]]", self._resolve)
        assert out == "see [alias](article-known.html)"

    def test_unknown_target_degrades_to_text(self):
        out = replace_wiki_links("see [[2026-05-05 - Unknown Piece]]", self._resolve)
        assert out == "see Unknown Piece"

    def test_unknown_with_alias(self):
        out = replace_wiki_links("see [[external/foo|the alias]]", self._resolve)
        assert out == "see the alias"
