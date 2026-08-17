"""Text-to-speech audio generation for articles, with pluggable providers.

Turns each article into a spoken-word audio file and reports the resulting
URL + duration so they can be added to the articles manifest (the
``audioUrl`` / ``audioDurationSec`` fields the C# generator reserved for
"the audio pipeline once it exists").

Providers implement a small interface (:class:`TTSProvider`) that synthesizes
one article to a WAV file; the orchestrator handles caching, duration and the
optional WAV→MP3 conversion (ffmpeg), so a provider only worries about turning
text into speech. Providers ship in separate modules and are re-exported here:

- :class:`PiperProvider` — local, offline Piper executable + voice models.
- :class:`AzureSpeechProvider` — Azure AI Speech (Foundry / Cognitive
    Services) via the REST synthesis endpoint (no SDK dependency).
- :class:`AzureSpeechSdkProvider` — Azure AI Speech via the Python SDK
    (azure-cognitiveservices-speech).

Everything degrades gracefully: a missing/misconfigured provider (no Piper
binary, no Azure key, missing voice, …) is reported clearly and the audio is
skipped — the build continues. Generation is cached by content hash (text +
provider + voice + format), so a daily run only synthesizes new or changed
articles.
"""

from __future__ import annotations

import hashlib
import html as _html
import json
import re
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .audio_base import TTSProvider
from .audio_azure_http import AZURE_DEFAULT_OUTPUT_FORMAT, AzureSpeechProvider
from .audio_azure_sdk import AzureSpeechSdkProvider
from .audio_piper import PiperProvider

# -- Markdown -> plain readable speech text -------------------------------

_CODE_FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_BLOCKQUOTE_RE = re.compile(r"(?m)^\s*>\s?")
_LIST_MARKER_RE = re.compile(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+")
_TABLE_ROW_RE = re.compile(r"(?m)^\s*\|.*$")
_RULE_RE = re.compile(r"(?m)^\s*([-*_=:])\1{2,}\s*$")
_INLINE_MATH_RE = re.compile(r"\$([^$\n]+)\$")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_EMPHASIS_RE = re.compile(r"[*_`~]{1,3}")


def markdown_to_speech_text(title: str, body_markdown: str) -> str:
    """Reduce an article's Markdown body to clean prose suitable for TTS.

    Code blocks, images, tables, rules and markup are dropped; links and
    headings keep their text. The title is spoken first."""
    text = body_markdown.replace("\r\n", "\n").replace("\r", "\n")
    text = _CODE_FENCE_RE.sub("", text)
    text = _IMAGE_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)

    def _heading(match: re.Match) -> str:
        head = match.group(1).strip()
        return head if head[-1:] in ".!?:" else head + "."

    text = _HEADING_RE.sub(_heading, text)
    text = _BLOCKQUOTE_RE.sub("", text)
    text = _LIST_MARKER_RE.sub("", text)
    text = _TABLE_ROW_RE.sub("", text)
    text = _RULE_RE.sub("", text)
    text = _INLINE_MATH_RE.sub(r"\1", text)
    text = _HTML_TAG_RE.sub("", text)
    text = _EMPHASIS_RE.sub("", text)
    text = _html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    title = title.strip()
    if title:
        spoken_title = title if title[-1:] in ".!?:" else title + "."
        return f"{spoken_title}\n\n{text}" if text else spoken_title
    return text


# -- ffmpeg WAV -> MP3 ----------------------------------------------------

def convert_to_mp3(ffmpeg_exe: str, wav_path: Path, mp3_path: Path, bitrate: str = "96k",
                   log: Callable[[str], None] = lambda _m: None) -> bool:
    if not ffmpeg_exe:
        return False
    cmd = [ffmpeg_exe, "-y", "-i", str(wav_path), "-b:a", bitrate, str(mp3_path)]
    try:
        result = subprocess.run(cmd, capture_output=True)
    except OSError as exc:
        log(f"  could not run ffmpeg: {exc}")
        return False
    if result.returncode != 0 or not mp3_path.is_file():
        err = result.stderr.decode("utf-8", "replace").strip()
        log(f"  ffmpeg exit={result.returncode}; stderr: {err[-400:] or '(empty)'}")
        return False
    return True


def wav_duration_seconds(wav_path: Path) -> float:
    """Duration of a WAV file (frames / sample rate) — no ffmpeg needed."""
    with wave.open(str(wav_path), "rb") as handle:
        rate = handle.getframerate()
        return handle.getnframes() / float(rate) if rate else 0.0


# -- orchestration --------------------------------------------------------

@dataclass
class AudioItem:
    slug: str
    lang: str
    text: str


@dataclass
class AudioResult:
    url: str
    duration_sec: int


def _content_hash(text: str, provider: str, voice_id: str, fmt: str) -> str:
    digest = hashlib.sha256()
    for part in (text, provider, voice_id, fmt):
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def generate_article_audio(
    items: Iterable[AudioItem],
    *,
    audio_dir: Path,
    url_prefix: str,
    provider: TTSProvider,
    ffmpeg_exe: str | None = None,
    mp3_bitrate: str = "96k",
    fmt: str = "mp3",
    batch_size: int | None = None,
    cache_name: str = "audio-index.json",
    log: Callable[[str], None] = print,
) -> dict[str, AudioResult]:
    """Synthesize audio for ``items`` into ``audio_dir`` with ``provider``,
    caching by content hash. Returns ``{slug: AudioResult}`` for the items
    that have audio (missing voice / failed synthesis are skipped).

    ``batch_size`` caps how many *new* files are synthesized in one run: once
    that many have been generated, the remaining cache misses are deferred to a
    later run (still reusing anything already cached). ``None`` means no cap.
    This throttles the cost of a paid provider (e.g. Azure) when first
    populating the audio library."""
    items = list(items)
    if fmt == "mp3" and not ffmpeg_exe:
        log("WARNING: ffmpeg unavailable — falling back to WAV audio output.")
        fmt = "wav"
    ext = "mp3" if fmt == "mp3" else "wav"

    # Preflight: a broken provider is fatal for every article — report once.
    if not provider.available():
        log(f"WARNING: TTS provider '{provider.name}' is not usable — skipping all article audio.")
        return {}

    # Report each distinct per-language voice problem once.
    bad_langs: dict[str, str] = {}
    for lang in {item.lang for item in items}:
        problem = provider.voice_problem(lang)
        if problem:
            bad_langs[lang] = problem
            log(f"WARNING: {problem} — skipping all '{lang}' articles.")

    audio_dir.mkdir(parents=True, exist_ok=True)
    cache_path = audio_dir / cache_name
    cache: dict[str, dict] = {}
    if cache_path.is_file():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cache = {}

    results: dict[str, AudioResult] = {}
    new_cache: dict[str, dict] = {}
    generated = reused = skipped = deferred = 0

    for item in items:
        if item.lang in bad_langs:
            skipped += 1
            continue

        digest = _content_hash(item.text, provider.name, provider.voice_id(item.lang), ext)
        target = audio_dir / f"{item.slug}.{ext}"
        url = f"{url_prefix}/{item.slug}.{ext}"

        cached = cache.get(item.slug)
        if cached and cached.get("hash") == digest and target.is_file():
            results[item.slug] = AudioResult(url=url, duration_sec=int(cached["duration"]))
            new_cache[item.slug] = cached
            reused += 1
            continue

        # Cache miss -> this item needs an (expensive) provider call. Honor the
        # batch cap by deferring further syntheses to a later run once we have
        # already generated ``batch_size`` files this run. Cached items above
        # are unaffected so their URLs stay in the manifest.
        if batch_size is not None and generated >= batch_size:
            deferred += 1
            continue

        # Progress logging per article (STORY 2026-07-15-003): name before the
        # synthesis starts, then "ok" / "failed" — makes long runs observable.
        log(f"Audio: {item.slug} ...")
        wav_path = audio_dir / f"{item.slug}.wav"
        if not provider.synthesize_wav(item.text, item.lang, wav_path):
            log(f"Audio: {item.slug} failed")
            log(f"WARNING: {provider.name} synthesis failed for {item.slug} — skipping audio.")
            skipped += 1
            continue

        try:
            duration = int(round(wav_duration_seconds(wav_path)))
        except (wave.Error, EOFError, OSError) as exc:
            log(f"Audio: {item.slug} failed")
            log(f"WARNING: could not read audio duration for {item.slug}: {exc} — skipping.")
            wav_path.unlink(missing_ok=True)
            skipped += 1
            continue

        if ext == "mp3":
            if convert_to_mp3(ffmpeg_exe, wav_path, target, mp3_bitrate, log):
                wav_path.unlink(missing_ok=True)
            else:
                log(f"  MP3 conversion failed for {item.slug} — keeping WAV.")
                target = audio_dir / f"{item.slug}.wav"
                url = f"{url_prefix}/{item.slug}.wav"
        else:
            wav_path.replace(target)

        results[item.slug] = AudioResult(url=url, duration_sec=duration)
        new_cache[item.slug] = {"hash": digest, "duration": duration}
        generated += 1
        log(f"Audio: {item.slug} ok")

    _prune_orphans(audio_dir, {item.slug for item in items}, cache_name, log)
    cache_path.write_text(json.dumps(new_cache, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = f"Audio ({provider.name}): {generated} generated, {reused} reused, {skipped} skipped"
    if deferred:
        summary += f", {deferred} deferred (batch_size={batch_size})"
    log(summary + ".")
    return results


def _prune_orphans(audio_dir: Path, keep_slugs: set[str], cache_name: str, log) -> None:
    """Delete audio files for articles that no longer exist."""
    for path in audio_dir.iterdir():
        if not path.is_file() or path.name == cache_name:
            continue
        if path.suffix.lower() in {".mp3", ".wav"} and path.stem not in keep_slugs:
            path.unlink(missing_ok=True)
            log(f"Audio: removed orphaned {path.name}")
