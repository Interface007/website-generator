"""Azure AI Speech provider implemented via direct HTTP requests."""

from __future__ import annotations

import html as _html
import time
import urllib.error
import urllib.request
from pathlib import Path

from .audio_base import TTSProvider

AZURE_DEFAULT_OUTPUT_FORMAT = "riff-24khz-16bit-mono-pcm"
_AZURE_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class AzureSpeechProvider(TTSProvider):
    """Cloud TTS via Azure AI Speech (Azure AI Foundry / Cognitive Services)."""

    name = "azure"

    def __init__(self, key: str, region: str | None = None, endpoint: str | None = None,
                 voices: dict[str, str] | None = None, output_format: str = AZURE_DEFAULT_OUTPUT_FORMAT,
                 timeout: int = 60, retries: int = 3, retry_backoff: float = 2.0,
                 log=None, debug: bool = False):
        super().__init__(voices, log, debug)
        self.key = key or ""
        self.output_format = output_format
        self.timeout = timeout
        self.retries = max(1, retries)
        self.retry_backoff = retry_backoff
        if endpoint:
            base = endpoint.rstrip("/")
            self.endpoint_url = base if base.endswith("/cognitiveservices/v1") else base + "/cognitiveservices/v1"
        elif region:
            self.endpoint_url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
        else:
            self.endpoint_url = ""
        self._urlopen = urllib.request.urlopen
        self._sleep = time.sleep

    def available(self) -> bool:
        if not self.key:
            self.log("  Azure Speech: no subscription key (set audio.azure.key or key_env).")
            return False
        if not self.endpoint_url:
            self.log("  Azure Speech: no region or endpoint configured.")
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

    def synthesize_wav(self, text: str, lang: str, wav_path: Path) -> bool:
        voice = self.voices.get(lang)
        if not voice:
            return False
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        body = self._ssml(voice, text).encode("utf-8")

        for attempt in range(1, self.retries + 1):
            last = attempt == self.retries
            request = urllib.request.Request(
                self.endpoint_url,
                data=body,
                method="POST",
                headers={
                    "Ocp-Apim-Subscription-Key": self.key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": self.output_format,
                    "User-Agent": "sitegen-tts",
                },
            )
            if self.debug:
                where = f" (attempt {attempt}/{self.retries})" if self.retries > 1 else ""
                self.log(f"  POST {self.endpoint_url} voice={voice} format={self.output_format}{where}")
            try:
                with self._urlopen(request, timeout=self.timeout) as response:
                    data = response.read()
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", "replace").strip()
                except Exception:  # noqa: BLE001
                    detail = ""
                hint = " (check subscription key / region)" if exc.code in (401, 403) else ""
                self.log(f"  Azure HTTP {exc.code}{hint}: {detail[-400:] or exc.reason}")
                if exc.code in _AZURE_RETRYABLE_STATUS and not last:
                    self._backoff_sleep(attempt, exc.headers)
                    continue
                return False
            except urllib.error.URLError as exc:
                self.log(f"  Azure request failed: {exc.reason} (network / endpoint)")
                if not last:
                    self._backoff_sleep(attempt, None)
                    continue
                return False
            except OSError as exc:
                self.log(f"  Azure request error: {exc}")
                if not last:
                    self._backoff_sleep(attempt, None)
                    continue
                return False

            if not data:
                self.log("  Azure returned an empty response.")
                if not last:
                    self._backoff_sleep(attempt, None)
                    continue
                return False
            wav_path.write_bytes(data)
            if attempt > 1:
                self.log(f"  Azure: recovered on attempt {attempt}/{self.retries}.")
            return True
        return False

    def _backoff_sleep(self, attempt: int, headers) -> None:
        delay = self.retry_backoff ** (attempt - 1)
        if headers is not None:
            retry_after = headers.get("Retry-After")
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except (TypeError, ValueError):
                    pass
        delay = min(delay, 30.0)
        self.log(f"  Azure: retrying in {delay:.0f}s…")
        self._sleep(delay)