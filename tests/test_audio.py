"""Tests for the Piper TTS audio module. Piper itself is mocked (no real
executable / voice models needed); WAV files are created with the stdlib so
duration probing is exercised for real."""

import json
import wave
from pathlib import Path

import imageio_ffmpeg

from sitegen.audio import (
    AudioItem,
    AzureSpeechProvider,
    AzureSpeechSdkProvider,
    PiperProvider,
    generate_article_audio,
    markdown_to_speech_text,
    wav_duration_seconds,
)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def _write_wav(path: Path, seconds: float = 1.0, rate: int = 8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames)


class FakeProvider:
    """Duck-typed TTS provider that writes a real short WAV."""

    name = "fake"

    def __init__(self, voices, fail_langs=(), seconds=2.0):
        self.voices = voices
        self.fail_langs = set(fail_langs)
        self.seconds = seconds
        self.synth_calls = []

    def available(self):
        return True

    def voice_problem(self, lang):
        return None if lang in self.voices else f"no voice for '{lang}'"

    def voice_id(self, lang):
        return self.voices.get(lang, "")

    def synthesize_wav(self, text, lang, wav_path):
        if lang in self.fail_langs:
            return False
        self.synth_calls.append(wav_path.stem)
        _write_wav(wav_path, self.seconds)
        return True


class TestSpeechText:
    def test_title_prepended_and_markup_stripped(self):
        body = (
            "# Heading One\n\n"
            "Some **bold** and *italic* and `code` text with a "
            "[link](https://x.y).\n\n"
            "```\ncode block\n```\n\n"
            "- item one\n- item two\n\n"
            "> a quote\n\n"
            "| a | b |\n|---|---|\n| 1 | 2 |\n\n"
            "An equation $x^2$ inline.\n"
        )
        out = markdown_to_speech_text("My Title", body)
        assert out.startswith("My Title.\n\n")
        assert "Heading One." in out
        assert "**" not in out and "`" not in out
        assert "code block" not in out          # fenced code dropped
        assert "link" in out and "https://x.y" not in out
        assert "item one" in out
        assert "a quote" in out
        assert "| a |" not in out               # table row dropped
        assert "x^2" in out and "$" not in out

    def test_empty_body(self):
        assert markdown_to_speech_text("Title", "") == "Title."

    def test_wav_duration(self, tmp_path):
        _write_wav(tmp_path / "a.wav", seconds=1.5)
        assert abs(wav_duration_seconds(tmp_path / "a.wav") - 1.5) < 0.01


class TestGenerateAudio:
    def _items(self):
        return [
            AudioItem(slug="article-de", lang="de", text="Hallo Welt."),
            AudioItem(slug="article-en", lang="en", text="Hello world."),
        ]

    def test_wav_generation_and_results(self, tmp_path):
        provider = FakeProvider({"de": "de.onnx", "en": "en.onnx"}, seconds=2.0)
        res = generate_article_audio(
            self._items(), audio_dir=tmp_path / "audio", url_prefix="/audio",
            provider=provider, fmt="wav", log=lambda m: None,
        )
        assert set(res) == {"article-de", "article-en"}
        assert res["article-de"].url == "/audio/article-de.wav"
        assert res["article-de"].duration_sec == 2
        assert (tmp_path / "audio" / "article-de.wav").is_file()
        assert (tmp_path / "audio" / "audio-index.json").is_file()

    def test_cache_reuse_skips_regeneration(self, tmp_path):
        items = self._items()
        p1 = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        generate_article_audio(items, audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=p1, fmt="wav", log=lambda m: None)
        assert len(p1.synth_calls) == 2
        p2 = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        res = generate_article_audio(items, audio_dir=tmp_path / "a", url_prefix="/audio",
                                     provider=p2, fmt="wav", log=lambda m: None)
        assert p2.synth_calls == []              # everything reused from cache
        assert res["article-de"].duration_sec == 2

    def test_changed_text_regenerates(self, tmp_path):
        p1 = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        generate_article_audio(self._items(), audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=p1, fmt="wav", log=lambda m: None)
        changed = [AudioItem("article-de", "de", "Anderer Text."),
                   AudioItem("article-en", "en", "Hello world.")]
        p2 = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        generate_article_audio(changed, audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=p2, fmt="wav", log=lambda m: None)
        assert p2.synth_calls == ["article-de"]  # only the changed one

    def test_switching_provider_regenerates(self, tmp_path):
        p1 = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        p1.name = "piper"
        generate_article_audio(self._items(), audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=p1, fmt="wav", log=lambda m: None)
        p2 = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        p2.name = "azure"
        generate_article_audio(self._items(), audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=p2, fmt="wav", log=lambda m: None)
        assert p2.synth_calls == ["article-de", "article-en"]   # hash includes provider name

    def test_missing_voice_is_skipped(self, tmp_path):
        provider = FakeProvider({"de": "de.onnx"})   # no en voice
        res = generate_article_audio(self._items(), audio_dir=tmp_path / "a", url_prefix="/audio",
                                     provider=provider, fmt="wav", log=lambda m: None)
        assert set(res) == {"article-de"}

    def test_synthesis_failure_is_skipped(self, tmp_path):
        provider = FakeProvider({"de": "de.onnx", "en": "en.onnx"}, fail_langs={"en"})
        res = generate_article_audio(self._items(), audio_dir=tmp_path / "a", url_prefix="/audio",
                                     provider=provider, fmt="wav", log=lambda m: None)
        assert set(res) == {"article-de"}

    def test_mp3_with_real_ffmpeg(self, tmp_path):
        provider = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        res = generate_article_audio(self._items(), audio_dir=tmp_path / "a", url_prefix="/audio",
                                     provider=provider, ffmpeg_exe=FFMPEG, fmt="mp3",
                                     log=lambda m: None)
        assert res["article-de"].url.endswith(".mp3")
        assert (tmp_path / "a" / "article-de.mp3").is_file()
        assert not (tmp_path / "a" / "article-de.wav").exists()   # wav cleaned up

    def test_mp3_falls_back_to_wav_without_ffmpeg(self, tmp_path):
        provider = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        res = generate_article_audio(self._items(), audio_dir=tmp_path / "a", url_prefix="/audio",
                                     provider=provider, ffmpeg_exe=None, fmt="mp3",
                                     log=lambda m: None)
        assert res["article-de"].url.endswith(".wav")

    def test_orphans_pruned(self, tmp_path):
        audio_dir = tmp_path / "a"
        audio_dir.mkdir()
        (audio_dir / "old-article.mp3").write_bytes(b"stale")
        provider = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        generate_article_audio(self._items(), audio_dir=audio_dir, url_prefix="/audio",
                               provider=provider, fmt="wav", log=lambda m: None)
        assert not (audio_dir / "old-article.mp3").exists()       # pruned
        assert (audio_dir / "article-de.wav").is_file()

    def _many_items(self, n):
        return [AudioItem(slug=f"article-{i}", lang="de", text=f"Text {i}.") for i in range(n)]

    def test_batch_size_caps_new_syntheses(self, tmp_path):
        provider = FakeProvider({"de": "de.onnx"})
        res = generate_article_audio(
            self._many_items(5), audio_dir=tmp_path / "a", url_prefix="/audio",
            provider=provider, fmt="wav", batch_size=2, log=lambda m: None,
        )
        # Only two files synthesized this run; the rest deferred.
        assert len(provider.synth_calls) == 2
        assert set(res) == {"article-0", "article-1"}

    def test_batch_size_resumes_across_runs(self, tmp_path):
        items = self._many_items(5)
        p1 = FakeProvider({"de": "de.onnx"})
        generate_article_audio(items, audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=p1, fmt="wav", batch_size=2, log=lambda m: None)
        assert p1.synth_calls == ["article-0", "article-1"]
        # Second run reuses the two cached files (free) and generates two more.
        p2 = FakeProvider({"de": "de.onnx"})
        res = generate_article_audio(items, audio_dir=tmp_path / "a", url_prefix="/audio",
                                     provider=p2, fmt="wav", batch_size=2, log=lambda m: None)
        assert p2.synth_calls == ["article-2", "article-3"]
        assert set(res) == {f"article-{i}" for i in range(4)}   # cached + new, deferred one absent

    def test_batch_size_deferred_files_not_pruned(self, tmp_path):
        items = self._many_items(5)
        p1 = FakeProvider({"de": "de.onnx"})
        generate_article_audio(items, audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=p1, fmt="wav", batch_size=2, log=lambda m: None)
        # The two generated files survive a capped run (they are still current articles).
        assert (tmp_path / "a" / "article-0.wav").is_file()
        assert (tmp_path / "a" / "article-1.wav").is_file()

    def test_batch_size_reports_deferred(self, tmp_path):
        msgs: list[str] = []
        provider = FakeProvider({"de": "de.onnx"})
        generate_article_audio(self._many_items(5), audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=provider, fmt="wav", batch_size=2, log=msgs.append)
        assert any("3 deferred" in m and "batch_size=2" in m for m in msgs)

    def test_no_batch_size_generates_all(self, tmp_path):
        provider = FakeProvider({"de": "de.onnx"})
        res = generate_article_audio(
            self._many_items(5), audio_dir=tmp_path / "a", url_prefix="/audio",
            provider=provider, fmt="wav", log=lambda m: None,
        )
        assert len(provider.synth_calls) == 5
        assert len(res) == 5

    def test_progress_logging_name_then_ok_or_failed(self, tmp_path):
        # STORY 2026-07-15-003: article name before synthesis, then ok/failed.
        msgs: list[str] = []
        provider = FakeProvider({"de": "de.onnx", "en": "en.onnx"}, fail_langs={"en"})
        generate_article_audio(self._items(), audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=provider, fmt="wav", log=msgs.append)
        i_de = msgs.index("Audio: article-de ...")
        assert msgs[i_de + 1] == "Audio: article-de ok"
        i_en = msgs.index("Audio: article-en ...")
        assert msgs[i_en + 1] == "Audio: article-en failed"

    def test_progress_logging_absent_for_cache_hits(self, tmp_path):
        items = self._items()
        p1 = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        generate_article_audio(items, audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=p1, fmt="wav", log=lambda m: None)
        msgs: list[str] = []
        p2 = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        generate_article_audio(items, audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=p2, fmt="wav", log=msgs.append)
        assert not any(m.startswith("Audio: article-de") for m in msgs)   # reused: no progress log

    def test_cache_index_content(self, tmp_path):
        provider = FakeProvider({"de": "de.onnx", "en": "en.onnx"})
        generate_article_audio(self._items(), audio_dir=tmp_path / "a", url_prefix="/audio",
                               provider=provider, fmt="wav", log=lambda m: None)
        index = json.loads((tmp_path / "a" / "audio-index.json").read_text(encoding="utf-8"))
        assert set(index) == {"article-de", "article-en"}
        assert "hash" in index["article-de"] and index["article-de"]["duration"] == 2


class TestPiperDiagnostics:
    def test_available_false_for_bogus_exe(self):
        assert PiperProvider("definitely-not-a-real-piper-xyz", {}).available() is False

    def test_available_true_for_existing_file(self, tmp_path):
        exe = tmp_path / "piper.exe"
        exe.write_text("x", encoding="utf-8")
        assert PiperProvider(str(exe), {}).available() is True

    def test_voice_problem_messages(self, tmp_path):
        onnx = tmp_path / "de.onnx"
        p = PiperProvider("piper", {"de": str(onnx), "en": str(tmp_path / "missing.onnx")})
        assert "no Piper voice configured" in p.voice_problem("fr")   # not configured
        assert "not found" in p.voice_problem("en")                   # .onnx missing
        onnx.write_text("x", encoding="utf-8")
        assert ".onnx.json" in p.voice_problem("de")                  # sidecar missing
        (tmp_path / "de.onnx.json").write_text("{}", encoding="utf-8")
        assert p.voice_problem("de") is None                          # all good

    def test_synthesize_logs_reason_when_exe_missing(self, tmp_path):
        onnx = tmp_path / "de.onnx"
        onnx.write_text("x", encoding="utf-8")
        (tmp_path / "de.onnx.json").write_text("{}", encoding="utf-8")
        msgs: list[str] = []
        p = PiperProvider("definitely-not-a-real-piper-xyz", {"de": str(onnx)}, log=msgs.append)
        assert p.synthesize_wav("hi", "de", tmp_path / "o.wav") is False
        assert any("not found" in m for m in msgs)

    def test_generate_aborts_when_piper_unavailable(self, tmp_path):
        msgs: list[str] = []
        p = PiperProvider("definitely-not-a-real-piper-xyz", {"de": "x.onnx"})
        res = generate_article_audio(
            [AudioItem("a", "de", "text")], audio_dir=tmp_path / "a",
            url_prefix="/audio", provider=p, fmt="wav", log=msgs.append,
        )
        assert res == {}
        assert any("not usable" in m for m in msgs)

    def test_generate_reports_missing_voice_once(self, tmp_path):
        # real exe (dummy file so available() passes), voice files absent
        exe = tmp_path / "piper.exe"
        exe.write_text("x", encoding="utf-8")
        msgs: list[str] = []
        p = PiperProvider(str(exe), {"de": str(tmp_path / "de.onnx")})
        res = generate_article_audio(
            [AudioItem("a1", "de", "t"), AudioItem("a2", "de", "t")],
            audio_dir=tmp_path / "a", url_prefix="/audio", provider=p, fmt="wav", log=msgs.append,
        )
        assert res == {}
        # the voice problem is reported once, not once per article
        assert sum("voice model for 'de' not found" in m for m in msgs) == 1


class TestAzureProvider:
    def _fake_response(self, data: bytes):
        class _Resp:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def read(self_inner):
                return data

        return _Resp()

    def test_available_requires_key_and_region(self):
        assert AzureSpeechProvider("", region="westeurope").available() is False
        assert AzureSpeechProvider("key", region=None).available() is False
        assert AzureSpeechProvider("key", region="westeurope").available() is True

    def test_endpoint_url_from_region_and_endpoint(self):
        a = AzureSpeechProvider("k", region="westeurope")
        assert a.endpoint_url == "https://westeurope.tts.speech.microsoft.com/cognitiveservices/v1"
        b = AzureSpeechProvider("k", endpoint="https://my-foundry.cognitiveservices.azure.com")
        assert b.endpoint_url.endswith("/cognitiveservices/v1")

    def test_voice_problem(self):
        a = AzureSpeechProvider("k", region="we", voices={"de": "de-DE-KatjaNeural", "en": "bad"})
        assert a.voice_problem("fr") is not None            # not configured
        assert "invalid" in a.voice_problem("en")           # not a real voice name
        assert a.voice_problem("de") is None

    def test_ssml_and_locale(self):
        a = AzureSpeechProvider("k", region="we", voices={"de": "de-DE-KatjaNeural"})
        assert AzureSpeechProvider._locale("de-DE-KatjaNeural") == "de-DE"
        ssml = a._ssml("de-DE-KatjaNeural", 'A & B <x>')
        assert "name='de-DE-KatjaNeural'" in ssml
        assert "xml:lang='de-DE'" in ssml
        assert "A &amp; B &lt;x&gt;" in ssml               # text XML-escaped

    def test_synthesize_writes_response_bytes(self, tmp_path):
        wav = tmp_path / "src.wav"
        _write_wav(wav, seconds=1.0)
        payload = wav.read_bytes()
        a = AzureSpeechProvider("k", region="we", voices={"de": "de-DE-KatjaNeural"})
        a._urlopen = lambda req, timeout=0: self._fake_response(payload)
        out = tmp_path / "out.wav"
        assert a.synthesize_wav("Hallo", "de", out) is True
        assert out.read_bytes() == payload
        assert abs(wav_duration_seconds(out) - 1.0) < 0.05

    def test_synthesize_reports_http_error(self, tmp_path):
        import urllib.error

        msgs: list[str] = []
        a = AzureSpeechProvider("badkey", region="we", voices={"de": "de-DE-KatjaNeural"},
                                log=msgs.append)

        def _raise(req, timeout=0):
            raise urllib.error.HTTPError(a.endpoint_url, 401, "Unauthorized", {}, None)

        a._urlopen = _raise
        assert a.synthesize_wav("Hallo", "de", tmp_path / "o.wav") is False
        assert any("401" in m for m in msgs)

    def test_synthesize_retries_transient_then_succeeds(self, tmp_path):
        import urllib.error

        wav = tmp_path / "src.wav"
        _write_wav(wav, seconds=1.0)
        payload = wav.read_bytes()
        msgs: list[str] = []
        a = AzureSpeechProvider("k", region="we", voices={"de": "de-DE-KatjaNeural"}, log=msgs.append)
        a._sleep = lambda _s: None                       # no real waiting in tests
        calls = {"n": 0}

        def _flaky(req, timeout=0):
            calls["n"] += 1
            if calls["n"] == 1:
                raise urllib.error.HTTPError(a.endpoint_url, 502, "Bad Gateway", {}, None)
            if calls["n"] == 2:
                raise TimeoutError("The read operation timed out")
            return self._fake_response(payload)

        a._urlopen = _flaky
        out = tmp_path / "o.wav"
        assert a.synthesize_wav("Hallo", "de", out) is True   # third attempt wins
        assert calls["n"] == 3
        assert out.read_bytes() == payload

    def test_synthesize_gives_up_after_retries(self, tmp_path):
        import urllib.error

        a = AzureSpeechProvider("k", region="we", voices={"de": "de-DE-KatjaNeural"},
                                retries=2, log=lambda m: None)
        a._sleep = lambda _s: None
        calls = {"n": 0}

        def _always_503(req, timeout=0):
            calls["n"] += 1
            raise urllib.error.HTTPError(a.endpoint_url, 503, "Service Unavailable", {}, None)

        a._urlopen = _always_503
        assert a.synthesize_wav("Hallo", "de", tmp_path / "o.wav") is False
        assert calls["n"] == 2                            # exactly `retries` attempts

    def test_synthesize_does_not_retry_auth_error(self, tmp_path):
        import urllib.error

        a = AzureSpeechProvider("badkey", region="we", voices={"de": "de-DE-KatjaNeural"},
                                log=lambda m: None)
        a._sleep = lambda _s: None
        calls = {"n": 0}

        def _raise_401(req, timeout=0):
            calls["n"] += 1
            raise urllib.error.HTTPError(a.endpoint_url, 401, "Unauthorized", {}, None)

        a._urlopen = _raise_401
        assert a.synthesize_wav("Hallo", "de", tmp_path / "o.wav") is False
        assert calls["n"] == 1                            # 401 is not retried

    def test_end_to_end_with_fake_azure(self, tmp_path):
        wav = tmp_path / "src.wav"
        _write_wav(wav, seconds=3.0)
        payload = wav.read_bytes()
        a = AzureSpeechProvider("k", region="we",
                                voices={"de": "de-DE-KatjaNeural", "en": "en-US-JennyNeural"})
        a._urlopen = lambda req, timeout=0: self._fake_response(payload)
        res = generate_article_audio(
            [AudioItem("article-de", "de", "Hallo"), AudioItem("article-en", "en", "Hi")],
            audio_dir=tmp_path / "a", url_prefix="/audio", provider=a, fmt="wav",
            log=lambda m: None,
        )
        assert set(res) == {"article-de", "article-en"}
        assert res["article-de"].duration_sec == 3


class TestAzureSpeechSdkProvider:
    def test_available_requires_sdk_module(self, monkeypatch):
        monkeypatch.setattr("sitegen.audio_azure_sdk._load_speechsdk", lambda: None)
        provider = AzureSpeechSdkProvider("k", region="we")
        assert provider.available() is False

    def test_synthesize_writes_fake_sdk_response(self, tmp_path, monkeypatch):
        import types

        wav = tmp_path / "src.wav"
        _write_wav(wav, seconds=1.0)
        payload = wav.read_bytes()

        class FakeSpeechSdk:
            class ResultReason:
                SynthesizingAudioCompleted = object()
                Canceled = object()

            class SpeechSynthesisOutputFormat:
                Riff24Khz16BitMonoPcm = object()

            class audio:
                class AudioOutputConfig:
                    def __init__(self, filename):
                        self.filename = filename

            class SpeechConfig:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs
                    self.format = None

                def set_speech_synthesis_output_format(self, format_id):
                    self.format = format_id

            class SpeechSynthesizer:
                def __init__(self, speech_config, audio_config):
                    self.audio_config = audio_config

                def speak_ssml_async(self, ssml):
                    Path(self.audio_config.filename).write_bytes(payload)
                    return types.SimpleNamespace(
                        get=lambda: types.SimpleNamespace(
                            reason=FakeSpeechSdk.ResultReason.SynthesizingAudioCompleted
                        )
                    )

        monkeypatch.setattr("sitegen.audio_azure_sdk._load_speechsdk", lambda: FakeSpeechSdk)
        provider = AzureSpeechSdkProvider("k", region="we", voices={"de": "de-DE-KatjaNeural"})
        out = tmp_path / "out.wav"
        assert provider.synthesize_wav("Hallo", "de", out) is True
        assert out.read_bytes() == payload
