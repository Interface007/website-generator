"""Local Piper TTS provider."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .audio_base import TTSProvider


class PiperProvider(TTSProvider):
    """Local, offline TTS via the Piper executable + ``.onnx`` voice models."""

    name = "piper"

    def __init__(self, piper_exe: str, voices: dict[str, str], piper_args: list[str] | None = None,
                 log=None, debug: bool = False):
        super().__init__(voices, log, debug)
        self.piper_exe = piper_exe
        self.piper_args = piper_args or []

    def available(self) -> bool:
        return bool(shutil.which(self.piper_exe)) or Path(self.piper_exe).is_file()

    def voice_id(self, lang: str) -> str:
        return Path(self.voices.get(lang, "")).name

    def voice_problem(self, lang: str) -> str | None:
        voice = self.voices.get(lang)
        if not voice:
            return f"no Piper voice configured for language '{lang}'"
        if not Path(voice).is_file():
            return f"voice model for '{lang}' not found: {voice}"
        if not Path(f"{voice}.json").is_file():
            return (
                f"voice config for '{lang}' missing: {voice}.json "
                f"(Piper needs the .onnx AND the .onnx.json next to it)"
            )
        return None

    def synthesize_wav(self, text: str, lang: str, wav_path: Path) -> bool:
        voice = self.voices.get(lang)
        if not voice:
            return False
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [self.piper_exe, "-m", str(voice), "-f", str(wav_path), *self.piper_args]
        if self.debug:
            self.log("  cmd: " + subprocess.list2cmdline(cmd))
        try:
            result = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True)
        except FileNotFoundError:
            self.log(f"  Piper executable not found: '{self.piper_exe}'")
            return False
        except OSError as exc:
            self.log(f"  could not run Piper: {exc}")
            return False
        if result.returncode != 0 or not wav_path.is_file():
            err = result.stderr.decode("utf-8", "replace").strip()
            out = result.stdout.decode("utf-8", "replace").strip()
            detail = err or out or "(no stderr output)"
            if not self.debug and len(detail) > 800:
                detail = "…" + detail[-800:]
            self.log(f"  Piper exit={result.returncode}; stderr: {detail}")
            if not self.debug:
                self.log("  (set audio.debug: true for the full command + output)")
            return False
        return True