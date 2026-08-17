from sitegen.frontmatter import split_front_matter


def test_no_front_matter():
    meta, body = split_front_matter("# Hello\n")
    assert meta == {}
    assert body == "# Hello\n"


def test_basic_block():
    meta, body = split_front_matter("---\ntitle: Foo\nDatum: 2026-07-02\n---\n\nBody\n")
    assert meta["title"] == "Foo"
    assert meta["Datum"] == "2026-07-02"
    assert body == "\nBody\n"


def test_case_insensitive_get():
    meta, _ = split_front_matter("---\nInteressensgebiet: Geschichte\n---\nx")
    assert meta.get("interessensgebiet") == "Geschichte"
    assert meta.get("missing", "d") == "d"


def test_quotes_stripped():
    meta, _ = split_front_matter('---\nslug: ""\nnav_title: \'Home\'\n---\nx')
    assert meta["slug"] == ""
    assert meta["nav_title"] == "Home"


def test_crlf_normalised():
    meta, body = split_front_matter("---\r\ntitle: T\r\n---\r\nBody\r\n")
    assert meta["title"] == "T"
    assert body == "Body\n"


def test_unterminated_block_is_body():
    meta, body = split_front_matter("---\ntitle: T\n")
    assert meta == {}
    assert body == "---\ntitle: T\n"


def test_colon_in_value():
    meta, _ = split_front_matter("---\nThema: A: B\n---\nx")
    assert meta["Thema"] == "A: B"
