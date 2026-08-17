"""Tests for the articles manifest (articles.json) and the language filter
control inserted into the articles overview page."""

import json
from datetime import datetime
from pathlib import Path

import yaml

from sitegen.audio import AudioResult
from sitegen.config import BuildContext, load_config
from sitegen.hp_pages import Article
from sitegen.steps import articles as articles_step
from sitegen.steps.articles import _write_manifest


def _ctx(tmp_path: Path, newline: str = "\n") -> BuildContext:
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "page-template.html.j2").write_text(
        "<h1>{{ heading }}</h1>\n<main>\n{{ content }}\n</main>\n{{ foot_scripts }}",
        encoding="utf-8",
    )
    (templates / "default-scripts.html").write_text("<script></script>", encoding="utf-8")
    (templates / "articles-overview-intro.md").write_text(
        "Intro\n\n| Title | Field | Date | Language |\n|---|---|---|---|\n", encoding="utf-8"
    )
    (templates / "article-lang-filter.html").write_text(
        '<div id="article-lang-filter" hidden>\n  <button data-lang="all">All</button>\n</div>\n',
        encoding="utf-8",
    )
    raw = {
        "site": {"base_url": "https://www.matzen.cloud/"},
        "markdown": {"flavour": "hp", "table_class": "gradienttable"},
        "output": {"dir": str(tmp_path / "out"), "newline": newline},
        "templates": {"dir": str(templates)},
        "pipeline": [{"step": "clean_output"}],
    }
    cfg = tmp_path / "site.yaml"
    cfg.write_text(yaml.safe_dump(raw), encoding="utf-8")
    ctx = BuildContext(config=load_config(cfg))
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    return ctx


def _make_articles(tmp_path: Path) -> Path:
    src = tmp_path / "vault"
    src.mkdir()
    (src / "2026-07-02 - Cosmos in Bronze - en-US.md").write_text(
        "---\nInteressensgebiet: History\nThema: An ancient calculator\nDatum: 2026-07-02\n---\n\n# Cosmos\n\nBody\n",
        encoding="utf-8",
    )
    (src / "2026-07-02 - Kosmos aus Bronze - de-DE.md").write_text(
        "---\nInteressensgebiet: Geschichte\nThema: Ein antiker Rechner\nDatum: 2026-07-02\n---\n\n# Kosmos\n\nRumpf\n",
        encoding="utf-8",
    )
    return src


def _base_options(src: Path) -> dict:
    return {
        "source_dir": str(src),
        "overview_output": "articles.html",
        "overview_title": "Articles",
        "manifest": "articles.json",
        "lang_filter": "article-lang-filter.html",
    }


class TestManifest:
    def test_manifest_entries_and_fields(self, tmp_path):
        ctx = _ctx(tmp_path)
        articles_step.run(ctx, _base_options(_make_articles(tmp_path)))
        data = json.loads((ctx.out_dir / "articles.json").read_text(encoding="utf-8"))
        assert len(data) == 2
        en = next(e for e in data if e["langTag"] == "en-US")
        assert en["slug"] == "article-2026-07-02-cosmos-in-bronze-en-us"
        assert en["lang"] == "en"                       # bare subtag
        assert en["date"] == "2026-07-02"
        assert en["field"] == "History"
        assert en["url"] == "/article-2026-07-02-cosmos-in-bronze-en-us.html"
        assert en["excerpt"] == "An ancient calculator"  # from Thema/description
        # key order matches the C# manifest
        assert list(en.keys()) == ["slug", "title", "lang", "langTag", "date", "field", "url", "excerpt"]

    def test_excerpt_falls_back_to_title(self, tmp_path):
        ctx = _ctx(tmp_path)
        src = tmp_path / "vault"
        src.mkdir()
        (src / "2026-01-01 - No Thema - en-US.md").write_text(
            "---\nDatum: 2026-01-01\n---\n\n# Just A Title\n\nBody\n", encoding="utf-8"
        )
        articles_step.run(ctx, _base_options(src))
        data = json.loads((ctx.out_dir / "articles.json").read_text(encoding="utf-8"))
        assert data[0]["excerpt"] == "Just A Title"

    def test_manifest_uses_config_newline_and_no_trailing(self, tmp_path):
        ctx = _ctx(tmp_path, newline="\r\n")
        articles_step.run(ctx, _base_options(_make_articles(tmp_path)))
        raw = (ctx.out_dir / "articles.json").read_bytes()
        assert raw.startswith(b"[\r\n")           # CRLF like the committed hp file
        assert not raw.endswith(b"\n]\n")         # no trailing newline
        assert raw.endswith(b"}\r\n]")

    def test_no_manifest_without_option(self, tmp_path):
        ctx = _ctx(tmp_path)
        opts = _base_options(_make_articles(tmp_path))
        del opts["manifest"]
        articles_step.run(ctx, opts)
        assert not (ctx.out_dir / "articles.json").exists()


class TestLanguageFilter:
    def test_filter_inserted_before_table(self, tmp_path):
        ctx = _ctx(tmp_path)
        articles_step.run(ctx, _base_options(_make_articles(tmp_path)))
        html = (ctx.out_dir / "articles.html").read_text(encoding="utf-8")
        assert 'id="article-lang-filter"' in html
        # control sits immediately above the articles table
        assert html.index('id="article-lang-filter"') < html.index('<table class="gradienttable">')
        assert html.index("</div>\n<table class=\"gradienttable\">") > 0

    def test_no_filter_without_option(self, tmp_path):
        ctx = _ctx(tmp_path)
        opts = _base_options(_make_articles(tmp_path))
        del opts["lang_filter"]
        articles_step.run(ctx, opts)
        html = (ctx.out_dir / "articles.html").read_text(encoding="utf-8")
        assert "article-lang-filter" not in html


class TestManifestAudioFields:
    def _articles(self):
        return [
            Article("a", "article-de.html", "DE", "b", datetime(2026, 7, 2),
                    "Feld", "Ausz.", "de-DE"),
            Article("b", "article-en.html", "EN", "b", datetime(2026, 7, 1),
                    "Field", "Exc.", "en-US"),
        ]

    def test_audio_fields_only_when_present(self, tmp_path):
        ctx = _ctx(tmp_path)
        audio_map = {"article-de": AudioResult(url="/audio/article-de.mp3", duration_sec=930)}
        _write_manifest(ctx, self._articles(), "articles.json", audio_map)
        data = json.loads((ctx.out_dir / "articles.json").read_text(encoding="utf-8"))
        de = next(e for e in data if e["slug"] == "article-de")
        en = next(e for e in data if e["slug"] == "article-en")
        assert de["audioUrl"] == "/audio/article-de.mp3"
        assert de["audioDurationSec"] == 930
        assert list(de.keys())[-2:] == ["audioUrl", "audioDurationSec"]   # appended at end
        assert "audioUrl" not in en and "audioDurationSec" not in en

    def test_no_audio_fields_when_map_empty(self, tmp_path):
        ctx = _ctx(tmp_path)
        _write_manifest(ctx, self._articles(), "articles.json", {})
        data = json.loads((ctx.out_dir / "articles.json").read_text(encoding="utf-8"))
        assert all("audioUrl" not in e for e in data)


class TestAudioGracefulDegradation:
    def test_enabled_but_piper_missing_still_builds(self, tmp_path):
        """Audio enabled with a non-existent Piper executable must not fail
        the build — audio is simply skipped and the manifest omits it."""
        ctx = _ctx(tmp_path)
        opts = _base_options(_make_articles(tmp_path))
        opts["audio"] = {
            "enabled": True,
            "piper_exe": "definitely-not-a-real-piper-binary",
            "format": "wav",
            "voices": {"de": str(tmp_path / "de.onnx"), "en": str(tmp_path / "en.onnx")},
        }
        articles_step.run(ctx, opts)   # must not raise
        data = json.loads((ctx.out_dir / "articles.json").read_text(encoding="utf-8"))
        assert len(data) == 2
        assert all("audioUrl" not in e for e in data)   # synthesis failed -> no audio

    def test_disabled_by_default_no_audio_dir(self, tmp_path):
        ctx = _ctx(tmp_path)
        articles_step.run(ctx, _base_options(_make_articles(tmp_path)))
        assert not (ctx.out_dir / "audio").exists()

    def test_existing_audio_file_injects_player_when_generation_disabled(self, tmp_path):
        ctx = _ctx(tmp_path)
        src = _make_articles(tmp_path)
        slug = "article-2026-07-02-kosmos-aus-bronze-de-de"
        (tmp_path / "templates" / "article-audio-player.html").write_text(
            '<audio src="%AUDIO_URL%" data-duration="%AUDIO_DURATION%"></audio>\n',
            encoding="utf-8",
        )
        (ctx.out_dir / "audio").mkdir()
        (ctx.out_dir / "audio" / f"{slug}.mp3").write_bytes(b"audio")

        opts = _base_options(src)
        opts["audio"] = {
            "enabled": False,
            "format": "mp3",
            "output_dir": "audio",
            "player_template": "article-audio-player.html",
        }

        articles_step.run(ctx, opts)

        de_html = (ctx.out_dir / f"{slug}.html").read_text(encoding="utf-8")
        en_html = (ctx.out_dir / "article-2026-07-02-cosmos-in-bronze-en-us.html").read_text(
            encoding="utf-8"
        )
        assert f'<audio src="/audio/{slug}.mp3" data-duration="0"></audio>' in de_html
        assert "<audio" not in en_html


class TestAudioPlayerInjection:
    def _options(self) -> dict:
        return {
            "audio": {
                "output_dir": "audio",
                "player_template": "article-audio-player.html",
            }
        }

    def _write_player_template(self, tmp_path: Path) -> None:
        (tmp_path / "templates" / "article-audio-player.html").write_text(
            '<audio src="%AUDIO_URL%" data-duration="%AUDIO_DURATION%"></audio>\n',
            encoding="utf-8",
        )

    def test_injects_player_when_audio_file_exists(self, tmp_path):
        ctx = _ctx(tmp_path)
        self._write_player_template(tmp_path)
        (ctx.out_dir / "audio").mkdir()
        (ctx.out_dir / "audio" / "article-de.mp3").write_bytes(b"audio")

        html = articles_step._inject_audio_player(
            ctx,
            self._options(),
            "<main>\n<p>Article</p>",
            AudioResult(url="/audio/article-de.mp3", duration_sec=42),
        )

        assert '<audio src="/audio/article-de.mp3" data-duration="42"></audio>' in html

    def test_skips_player_when_audio_file_is_missing(self, tmp_path):
        ctx = _ctx(tmp_path)
        self._write_player_template(tmp_path)
        original = "<main>\n<p>Article</p>"

        html = articles_step._inject_audio_player(
            ctx,
            self._options(),
            original,
            AudioResult(url="/audio/article-de.mp3", duration_sec=42),
        )

        assert html == original
