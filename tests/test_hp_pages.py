from datetime import datetime
from pathlib import Path

from sitegen.hp_pages import read_content


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_title_from_front_matter_keeps_body(tmp_path):
    path = _write(tmp_path, "privacypolicy.md", "---\ntitle: Privacy\n---\n\n# Not the title\ntext\n")
    article = read_content(path)
    assert article.title == "Privacy"
    assert "# Not the title" in article.body
    assert article.output_file_name == "privacypolicy.html"
    assert article.date is None


def test_title_from_heading_and_date_from_name(tmp_path):
    path = _write(
        tmp_path,
        "2026-07-02 - Der Kosmos - de-DE.md",
        "---\nInteressensgebiet: Geschichte\nThema: Antikythera\n---\n\n# Der Kosmos\n\n---\n\nBody text\n",
    )
    article = read_content(path, page_prefix="article-")
    assert article.title == "Der Kosmos"
    assert article.body.startswith("Body text")
    assert article.date == datetime(2026, 7, 2)
    assert article.area_of_interest == "Geschichte"
    assert article.description == "Antikythera"
    assert article.language == "de-DE"
    assert article.output_file_name == "article-2026-07-02-der-kosmos-de-de.html"


def test_datum_front_matter_wins_over_name(tmp_path):
    path = _write(tmp_path, "2026-01-01 - x - en-US.md", "---\nDatum: 2026-06-30\n---\n# T\nb")
    assert read_content(path).date == datetime(2026, 6, 30)


def test_fallback_title(tmp_path):
    path = _write(tmp_path, "notes.md", "just text without heading")
    assert read_content(path).title == "Content Page"
