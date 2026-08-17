"""Azure AI Speech provider implemented with the Python Speech SDK."""

from __future__ import annotations

import importlib
import html as _html
import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from contextlib import suppress
from urllib.parse import urlparse

from .audio_base import TTSProvider

_SPEECHSDK_IMPORT = "azure.cognitiveservices.speech"

_OUTPUT_FORMAT_MAP = {
    "riff-16khz-16bit-mono-pcm": "Riff16Khz16BitMonoPcm",
    "riff-24khz-16bit-mono-pcm": "Riff24Khz16BitMonoPcm",
    "riff-48khz-16bit-mono-pcm": "Riff48Khz16BitMonoPcm",
    "raw-16khz-16bit-mono-pcm": "Raw16Khz16BitMonoPcm",
    "raw-24khz-16bit-mono-pcm": "Raw24Khz16BitMonoPcm",
}


def _load_speechsdk():
    try:
        return importlib.import_module(_SPEECHSDK_IMPORT)
    except Exception:  # noqa: BLE001
        return None


def _safe_unlink(path: Path) -> None:
    with suppress(FileNotFoundError, PermissionError):
        path.unlink()


def _dump_result_debug(result, speechsdk, log, prefix: str = "speech_result") -> None:
    """Serialize a SpeechSynthesisResult to a timestamped JSON file for debugging."""
    data: dict = {}
    for attr in ("reason", "result_id", "audio_duration"):
        try:
            val = getattr(result, attr, None)
            data[attr] = str(val) if val is not None else None
        except Exception:  # noqa: BLE001
            data[attr] = "<error reading attribute>"
    try:
        audio_data = getattr(result, "audio_data", None)
        data["audio_data"] = f"<bytes len={len(audio_data)}>" if isinstance(audio_data, (bytes, bytearray)) else str(audio_data)
    except Exception:  # noqa: BLE001
        data["audio_data"] = "<error reading audio_data>"
    if speechsdk is not None:
        try:
            cd = speechsdk.SpeechSynthesisCancellationDetails.from_result(result)
            data["cancellation"] = {
                "reason": str(getattr(cd, "reason", None)),
                "error_code": str(getattr(cd, "error_code", None)),
                "error_details": str(getattr(cd, "error_details", None)),
            }
        except Exception:  # noqa: BLE001
            data["cancellation"] = "<could not extract SpeechSynthesisCancellationDetails>"
    try:
        props = result.properties
        prop_data: dict = {}
        if speechsdk is not None:
            for name in dir(speechsdk.PropertyId):
                if not name.startswith("_"):
                    try:
                        pid = getattr(speechsdk.PropertyId, name)
                        val = props.get_property(pid)
                        if val:
                            prop_data[name] = val
                    except Exception:  # noqa: BLE001
                        pass
        data["properties"] = prop_data
    except Exception:  # noqa: BLE001
        pass
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid = uuid.uuid4().hex[:8]
    debug_dir = Path(tempfile.gettempdir()) / "sitegen_debug"
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / f"{prefix}_{ts}_{uid}.json"
        with open(debug_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
        if log:
            log(f"  Debug dump written: {debug_path}")
    except Exception:  # noqa: BLE001
        if log:
            log("  Warning: could not write debug dump file.")


class AzureSpeechSdkProvider(TTSProvider):
    """Cloud TTS via the Azure Speech SDK (azure-cognitiveservices-speech)."""

    name = "azure-sdk"

    def __init__(self, key: str, region: str | None = None, endpoint: str | None = None,
                 voices: dict[str, str] | None = None, output_format: str = "riff-24khz-16bit-mono-pcm",
                 timeout: int = 60, log=None, debug: bool = False):
        super().__init__(voices, log, debug)
        self.key = key or ""
        self.region = region or ""
        self.endpoint = endpoint or ""
        self.output_format = output_format
        self.timeout = timeout
        self._speechsdk = None

    def _sdk_endpoint(self) -> str:
        """Base endpoint for the Speech SDK: ``scheme://host`` only.

        The SDK opens a WebSocket and builds its own path, so it must NOT receive
        the REST ``/cognitiveservices/v1`` path (nor the ``/tts`` REST sub-path) —
        that yields a 404 on the WS upgrade. Mirrors the Azure AI Foundry sample,
        which passes ``f"{scheme}://{netloc}"``. Region-based configs fall back to
        the SDK's own ``region`` handling (see ``_speech_config``)."""
        if self.endpoint:
            parsed = urlparse(self.endpoint)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
            return self.endpoint.rstrip("/")
        return ""

    def _sdk(self):
        if self._speechsdk is None:
            self._speechsdk = _load_speechsdk()
        return self._speechsdk

    def available(self) -> bool:
        if not self.key:
            self.log("  Azure Speech SDK: no subscription key (set audio.azure.key or key_env).")
            return False
        if not (self.endpoint or self.region):
            self.log("  Azure Speech SDK: no region or endpoint configured.")
            return False
        if self._sdk() is None:
            self.log("  Azure Speech SDK: package 'azure-cognitiveservices-speech' is not installed.")
            return False
        return True

    def voice_id(self, lang: str) -> str:
        return str(self.voices.get(lang, ""))

    def voice_problem(self, lang: str) -> str | None:
        voice = self.voices.get(lang)
        if not voice:
            return f"no Azure voice configured for language '{lang}'"
        if voice.count("-") < 2:
            return f"Azure voice for '{lang}' looks invalid: {voice!r} (expected e.g. de-DE-KatjaNeural)"
        return None

    @staticmethod
    def _locale(voice: str) -> str:
        parts = voice.split("-")
        return "-".join(parts[:2]) if len(parts) >= 2 else voice

    def _ssml(self, voice: str, text: str) -> str:
        locale = self._locale(voice)
        return (
            f"<speak version='1.0' xml:lang='{locale}'>"
            f"<voice xml:lang='{locale}' name='{voice}'>{_html.escape(text)}</voice>"
            f"</speak>"
        )

    def _speech_config(self, speechsdk):
        sdk_endpoint = self._sdk_endpoint()
        if sdk_endpoint:
            speech_config = speechsdk.SpeechConfig(subscription=self.key, endpoint=sdk_endpoint)
        else:
            speech_config = speechsdk.SpeechConfig(subscription=self.key, region=self.region)
        format_name = _OUTPUT_FORMAT_MAP.get(self.output_format.lower())
        if format_name is None:
            self.log(
                f"  Azure Speech SDK: unsupported output format {self.output_format!r}; using SDK default."
            )
        else:
            speech_config.set_speech_synthesis_output_format(
                getattr(speechsdk.SpeechSynthesisOutputFormat, format_name)
            )
        return speech_config

    def synthesize_wav(self, text: str, lang: str, wav_path: Path) -> bool:
        voice = self.voices.get(lang)
        if not voice:
            return False
        speechsdk = self._sdk()
        if speechsdk is None:
            self.log("  Azure Speech SDK: package 'azure-cognitiveservices-speech' is not installed.")
            return False

        wav_path.parent.mkdir(parents=True, exist_ok=True)
        speech_config = None
        audio_config = None
        synthesizer = None
        result = None
        try:
            speech_config = self._speech_config(speechsdk)
            audio_config = speechsdk.audio.AudioOutputConfig(filename=str(wav_path))
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
            result = synthesizer.speak_ssml_async(self._ssml(voice, text)).get()
        except Exception as exc:  # noqa: BLE001
            self.log(f"  Azure Speech SDK request failed: {exc}")
            synthesizer = None
            audio_config = None
            speech_config = None
            _safe_unlink(wav_path)
            return False

        if getattr(result, "reason", None) == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return wav_path.is_file()

        if getattr(result, "reason", None) == speechsdk.ResultReason.Canceled:
            try:
                details = speechsdk.SpeechSynthesisCancellationDetails.from_result(result)
                error_details = getattr(details, "error_details", "") or getattr(details, "reason", "")
                self.log(f"  Azure Speech SDK canceled: {error_details}")
            except Exception:  # noqa: BLE001
                self.log("  Azure Speech SDK canceled: could not extract cancellation details — dumping full result.")
                _dump_result_debug(result, speechsdk, self.log, prefix="speech_canceled")
        else:
            self.log(f"  Azure Speech SDK synthesis failed (reason={getattr(result, 'reason', 'unknown')}) — dumping full result.")
            _dump_result_debug(result, speechsdk, self.log, prefix="speech_failed")

        synthesizer = None
        audio_config = None
        speech_config = None
        result = None
        _safe_unlink(wav_path)
        return False