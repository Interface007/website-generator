"""Shared TTS provider base classes."""

from __future__ import annotations

from typing import Callable


class TTSProvider:
    """Base class for TTS providers."""

    name = "tts"

    def __init__(self, voices: dict[str, str] | None = None, log: Callable[[str], None] | None = None,
                 debug: bool = False):
        self.voices = voices or {}
        self.log = log or (lambda _msg: None)
        self.debug = debug

    def available(self) -> bool:
        return True

    def voice_id(self, lang: str) -> str:
        return str(self.voices.get(lang, ""))

    def voice_problem(self, lang: str) -> str | None:
        if lang not in self.voices:
            return f"no voice configured for language '{lang}'"
        return None

    def synthesize_wav(self, text: str, lang: str, wav_path):
        raise NotImplementedError