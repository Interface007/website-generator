"""Step: render a folder of Markdown articles plus an overview page.

Port of the hp MultiPageRenderer: reads ``*.md`` from a (flat) article
folder — e.g. an Obsidian vault directory — skips index/sync-artifact
files, resolves Obsidian wiki links, renders one HTML page per article
and an overview page with a link table.

Options:
  source_dir          folder containing the article .md files
  page_prefix         output file prefix (default "article-")
  overview_output     overview file name (default "articles.html")
  overview_intro      Markdown intro template (in templates dir)
  overview_title      title of the overview page
  overview_description  meta description of the overview page
  overview_language   language tag of the overview page (default "en-US")
  skip_files          file names to ignore (e.g. topics.md)
  disclaimers         snippet templates appended to each page
  manifest            optional JSON manifest file name (e.g. articles.json):
                      single source of truth for the client-side language
                      filter, one entry per article
  lang_filter         optional snippet inserted into the overview page
                      before ``lang_filter_anchor`` (the language filter
                      segmented control)
  lang_filter_anchor  string the filter snippet is inserted before
                      (default: the gradienttable opening tag)
  audio               optional TTS block (opt-in) — synthesizes a spoken-word
                      file per article and adds audioUrl / audioDurationSec
                      to the manifest:
                        enabled        turn the feature on (default off)
                        provider       "piper" (default) or "azure"
                        format         "mp3" (needs ffmpeg) or "wav"
                        mp3_bitrate    e.g. "96k"
                        ffmpeg_exe     override (default: imageio-ffmpeg)
                        output_dir     audio sub-dir of the output (default "audio")
                        url_prefix     URL prefix (default "/<output_dir>")
                        batch_size     cap new syntheses per run (throttles a
                                       paid provider; omit for no cap)
                        player_template  snippet inserted into each article
                                       page (%AUDIO_URL% / %AUDIO_DURATION%)
                        debug          log provider details on failure
                      provider "piper":
                        piper_exe      Piper executable (default "piper")
                        voices         {lang: voice.onnx path} per language
                        piper_args     extra Piper CLI args (optional)
                      provider "azure" (Azure AI Speech / Foundry):
                        azure.region   e.g. "westeurope" (or azure.endpoint)
                        azure.endpoint full custom endpoint (Foundry) instead
                                       of region
                        azure.key      subscription key (prefer azure.key_env)
                        azure.key_env  env var holding the key
                                       (default AZURE_SPEECH_KEY)
                        azure.voices   {lang: voice name}, e.g. de-DE-KatjaNeural
                        azure.output_format  WAV/PCM format (default
                                       riff-24khz-16bit-mono-pcm)
                                            provider "azure-sdk" (Azure AI Speech SDK):
                                                same azure.* settings as provider "azure"
  title_suffix / portrait_image / portrait_modifier  see HpPageRenderer
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from dataclasses import replace
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

from ..audio import (
    AudioItem,
    AudioResult,
    AzureSpeechProvider,
    AzureSpeechSdkProvider,
    PiperProvider,
    TTSProvider,
    generate_article_audio,
    markdown_to_speech_text,
)
from ..config import BuildContext
from ..hp_pages import Article, HpPageRenderer, read_content
from ..textutil import is_sync_artifact, replace_wiki_links

_MIN_DATE = datetime.min
_DEFAULT_FILTER_ANCHOR = '<table class="gradienttable">'


def run(ctx: BuildContext, options: dict) -> None:
    source_dir = ctx.config.resolve_path(options["source_dir"])
    page_prefix = options.get("page_prefix", "article-")
    skip_files = {name.lower() for name in options.get("skip_files", [])}
    disclaimers = tuple(options.get("disclaimers", []))
    renderer = HpPageRenderer(ctx, options)

    # Remove previously generated article pages so renamed/deleted articles
    # do not linger in the output.
    for stale in ctx.out_dir.glob(f"{page_prefix}*.html"):
        stale.unlink()

    articles = [
        read_content(path, page_prefix)
        for path in source_dir.glob("*.md")
        if path.name.lower() not in skip_files and not is_sync_artifact(path.stem)
    ]
    # Newest first; ties alphabetically by title (case-insensitive), like
    # the C# OrderByDescending(...).ThenBy(...). Sorting by the secondary
    # key first keeps the primary sort stable.
    articles.sort(key=lambda a: a.title.upper())
    articles.sort(key=lambda a: a.date or _MIN_DATE, reverse=True)

    by_name = {article.name.lower(): article for article in articles}

    def resolve(target: str):
        article = by_name.get(target.lower())
        if article is None:
            return None
        return article.title, article.output_file_name

    # Language pairs (de-DE/en-US) share a content date: emit reciprocal
    # hreflang alternates so search engines treat them as translations of
    # one page instead of near-duplicate content.
    hreflang_by_name = _build_hreflang_map(ctx, articles)

    # Resolve Obsidian wiki links once; the result feeds both the page
    # render and the TTS text extraction.
    resolved_articles = [
        replace(
            article,
            body=replace_wiki_links(article.body, resolve),
            hreflang_html=hreflang_by_name.get(article.name.lower(), ""),
        )
        for article in articles
    ]

    # Optional Piper TTS: synthesize audio before rendering so the player
    # can be injected and the manifest can carry the audio fields.
    audio_map = _build_audio_map(ctx, options, resolved_articles)

    for resolved in resolved_articles:
        html = renderer.render_page(resolved, disclaimers)
        slug = resolved.output_file_name.removesuffix(".html")
        if slug in audio_map:
            html = _inject_audio_player(ctx, options, html, audio_map[slug])
        ctx.write_output(resolved.output_file_name, html)
        print(f"Rendered content page '{resolved.output_file_name}'.")

    overview_name = options.get("overview_output", "articles.html")
    ctx.write_output(
        overview_name,
        _render_overview(ctx, renderer, articles, overview_name, disclaimers, options),
    )
    print(f"Rendered content page '{overview_name}'.")

    manifest_name = options.get("manifest")
    if manifest_name:
        _write_manifest(ctx, articles, manifest_name, audio_map)
        print(f"Wrote '{manifest_name}' ({len(articles)} entries).")

    # Publish each dated article's content date for the sitemap step.
    for article in articles:
        if article.date is not None:
            ctx.content_dates[article.output_file_name.lower()] = article.date


def _build_hreflang_map(ctx: BuildContext, articles: list[Article]) -> dict[str, str]:
    """Maps article name (lower) -> hreflang <link> block.

    Articles are paired by content date: the daily publishing model produces
    exactly one article per day in two languages. Only dates with exactly two
    articles in two distinct languages get alternates (self-reference
    included, per Google's hreflang requirements); anything else is skipped.
    """
    by_date: dict[datetime, list[Article]] = defaultdict(list)
    for article in articles:
        if article.date is not None and article.language:
            by_date[article.date].append(article)

    result: dict[str, str] = {}
    for group in by_date.values():
        languages = {a.language.lower() for a in group}
        if len(group) != 2 or len(languages) != 2:
            continue
        block = "".join(
            f'\n  <link rel="alternate" hreflang="{a.language}" '
            f'href="{ctx.config.base_url}{a.output_file_name}" />'
            for a in sorted(group, key=lambda a: a.language.lower())
        )
        for article in group:
            result[article.name.lower()] = block
    return result


def _normalize_language(language: str) -> str:
    """Locale tag ("de-DE") -> bare language subtag ("de")."""
    return language[:2].lower() if len(language) >= 2 else language.lower()


def _build_provider(ctx: BuildContext, audio_opts: dict, debug: bool) -> TTSProvider:
    """Construct the configured TTS provider (default: Piper)."""
    provider = audio_opts.get("provider", "piper")
    if provider == "piper":
        voices = {
            lang: str(ctx.config.resolve_path(path))
            for lang, path in (audio_opts.get("voices") or {}).items()
        }
        return PiperProvider(
            piper_exe=audio_opts.get("piper_exe", "piper"),
            voices=voices,
            piper_args=audio_opts.get("piper_args"),
            log=print,
            debug=debug,
        )
    if provider == "azure":
        az = audio_opts.get("azure") or {}
        key = az.get("key") or os.environ.get(az.get("key_env", "AZURE_SPEECH_KEY"), "")
        from ..audio import AZURE_DEFAULT_OUTPUT_FORMAT

        return AzureSpeechProvider(
            key=key,
            region=az.get("region"),
            endpoint=az.get("endpoint"),
            voices=az.get("voices") or {},
            output_format=az.get("output_format", AZURE_DEFAULT_OUTPUT_FORMAT),
            timeout=int(az.get("timeout", 60)),
            retries=int(az.get("retries", 3)),
            log=print,
            debug=debug,
        )
    if provider == "azure-sdk":
        az = audio_opts.get("azure") or {}
        key = az.get("key") or os.environ.get(az.get("key_env", "AZURE_SPEECH_KEY"), "")
        return AzureSpeechSdkProvider(
            key=key,
            region=az.get("region"),
            endpoint=az.get("endpoint"),
            voices=az.get("voices") or {},
            output_format=az.get("output_format", "riff-24khz-16bit-mono-pcm"),
            timeout=int(az.get("timeout", 60)),
            log=print,
            debug=debug,
        )
    raise ValueError(f"Unknown audio provider '{provider}' (known: piper, azure, azure-sdk)")


def _build_audio_map(
    ctx: BuildContext, options: dict, articles: list[Article]
) -> dict[str, AudioResult]:
    """Run the configured TTS provider for each article (when
    ``audio.enabled``); returns ``{slug: AudioResult}``. Absent/disabled
    audio yields an empty map."""
    audio_opts = options.get("audio") or {}
    if not audio_opts:
        return {}

    existing_audio = _existing_audio_map(ctx, audio_opts, articles)
    if not audio_opts.get("enabled"):
        return existing_audio

    debug = bool(audio_opts.get("debug"))
    provider = _build_provider(ctx, audio_opts, debug)

    fmt = audio_opts.get("format", "mp3")
    ffmpeg_exe = audio_opts.get("ffmpeg_exe")
    if fmt == "mp3" and not ffmpeg_exe:
        try:
            import imageio_ffmpeg

            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:  # noqa: BLE001 (optional dependency)
            ffmpeg_exe = None

    output_dir = audio_opts.get("output_dir", "audio")
    batch_size = audio_opts.get("batch_size")
    if batch_size is not None:
        batch_size = int(batch_size)
    items = [
        AudioItem(
            slug=article.output_file_name.removesuffix(".html"),
            lang=_normalize_language(article.language),
            text=markdown_to_speech_text(article.title, article.body),
        )
        for article in articles
    ]
    generated_audio = generate_article_audio(
        items,
        audio_dir=ctx.out_dir / output_dir,
        url_prefix=_audio_url_prefix(audio_opts, output_dir),
        provider=provider,
        ffmpeg_exe=ffmpeg_exe,
        mp3_bitrate=audio_opts.get("mp3_bitrate", "96k"),
        fmt=fmt,
        batch_size=batch_size,
    )
    return existing_audio | generated_audio


def _audio_url_prefix(audio_opts: dict, output_dir: str) -> str:
    return audio_opts.get("url_prefix", "/" + output_dir.strip("/"))


def _existing_audio_map(
    ctx: BuildContext, audio_opts: dict, articles: list[Article]
) -> dict[str, AudioResult]:
    """Return AudioResults for already existing article audio files."""
    output_dir = audio_opts.get("output_dir", "audio")
    audio_dir = ctx.out_dir / output_dir
    if not audio_dir.is_dir():
        return {}

    url_prefix = _audio_url_prefix(audio_opts, output_dir)
    extensions = ("mp3", "wav") if audio_opts.get("format", "mp3") == "mp3" else ("wav", "mp3")
    cache = _read_audio_cache(audio_dir / "audio-index.json")
    results: dict[str, AudioResult] = {}

    for article in articles:
        slug = article.output_file_name.removesuffix(".html")
        for ext in extensions:
            target = audio_dir / f"{slug}.{ext}"
            if target.is_file():
                duration = int((cache.get(slug) or {}).get("duration") or 0)
                results[slug] = AudioResult(
                    url=f"{url_prefix}/{target.name}",
                    duration_sec=duration,
                )
                break

    return results


def _read_audio_cache(cache_path):
    if not cache_path.is_file():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _inject_audio_player(ctx: BuildContext, options: dict, html: str, result: AudioResult) -> str:
    """Insert the audio-player snippet immediately after the opening
    ``<main>`` tag of an article page (opt-in via ``audio.player_template``)."""
    template_name = (options.get("audio") or {}).get("player_template")
    if not template_name:
        return html

    audio_path = _audio_output_path(ctx, options, result)
    if audio_path is None or not audio_path.is_file():
        print(f"WARNING: audio file '{result.url}' is missing — skipping audio player.")
        return html

    snippet = ctx.read_template_text(template_name).replace("\r\n", "\n")
    snippet = snippet.replace("%AUDIO_URL%", result.url).replace(
        "%AUDIO_DURATION%", str(result.duration_sec)
    )
    return re.sub(r"(<main>\s*)", lambda m: m.group(1) + snippet, html, count=1)


def _audio_output_path(ctx: BuildContext, options: dict, result: AudioResult):
    """Resolve an AudioResult URL to the expected local output file."""
    audio_file = PurePosixPath(unquote(urlparse(result.url).path)).name
    if not audio_file:
        return None
    output_dir = (options.get("audio") or {}).get("output_dir", "audio")
    return ctx.out_dir / output_dir / audio_file


def _write_manifest(
    ctx: BuildContext,
    articles: list[Article],
    manifest_name: str,
    audio_map: dict[str, AudioResult] | None = None,
) -> None:
    """Emit the articles manifest (JSON) consumed by the language filter.

    Matches the C# manifest: 2-space indented, umlauts kept literal, no
    trailing newline, and the configured newline sequence (CRLF for hp).
    ``audioUrl`` / ``audioDurationSec`` are appended only for articles that
    actually have audio (mirroring the C# "omit when absent" behaviour)."""
    audio_map = audio_map or {}
    entries = []
    for article in articles:
        slug = article.output_file_name.removesuffix(".html")
        entry = {
            "slug": slug,
            "title": article.title,
            "lang": _normalize_language(article.language),
            "langTag": article.language,
            "date": article.date.strftime("%Y-%m-%d") if article.date is not None else "",
            "field": article.area_of_interest,
            "url": "/" + article.output_file_name,
            "excerpt": article.description.strip() or article.title,
        }
        audio = audio_map.get(slug)
        if audio is not None:
            entry["audioUrl"] = audio.url
            entry["audioDurationSec"] = audio.duration_sec
        entries.append(entry)
    payload = json.dumps(entries, ensure_ascii=False, indent=2)
    ctx.write_output(manifest_name, payload.replace("\n", ctx.newline))


def _render_overview(
    ctx: BuildContext,
    renderer: HpPageRenderer,
    articles: list[Article],
    overview_name: str,
    disclaimers: tuple[str, ...],
    options: dict,
) -> str:
    intro_markdown = ctx.read_template_text(
        options.get("overview_intro", "articles-overview-intro.md")
    ).rstrip()

    # Values go in raw: the C# generator HTML-encoded them, but Markdig
    # decoded the entities again during the Markdown pass, so the net
    # effect equals plain Markdown escaping of the raw text.
    rows = []
    for article in articles:
        date = article.date.strftime("%Y-%m-%d") if article.date is not None else ""
        rows.append(
            f"| [{article.title}]({article.output_file_name}) "
            f"| {article.area_of_interest} | {date} "
            f"| {article.language} |"
        )

    markdown_text = intro_markdown + "\n" + "\n".join(rows) + "\n"
    content_html = renderer.markdown.convert(markdown_text)

    overview = Article(
        name="articles",
        output_file_name=overview_name,
        title=options.get("overview_title", "Articles"),
        body=content_html,
        date=None,
        area_of_interest="",
        description=options.get("overview_description", ""),
        language=options.get("overview_language", "en-US"),
    )
    html = renderer.render_page(overview, disclaimers, body_is_html=True)

    # Progressive-enhancement language filter: insert the (JS-less: hidden)
    # segmented control immediately above the articles table. Done on the
    # final HTML so the second Markdown pass cannot mangle it; the snippet
    # keeps its LF newlines to match the markdown-rendered content region.
    lang_filter = options.get("lang_filter")
    if lang_filter:
        anchor = options.get("lang_filter_anchor", _DEFAULT_FILTER_ANCHOR)
        snippet = ctx.read_template_text(lang_filter).replace("\r\n", "\n")
        html = html.replace(anchor, snippet + anchor, 1)
    return html
