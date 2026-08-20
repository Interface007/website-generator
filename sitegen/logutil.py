"""Shared timestamped console logging for the generator pipeline.

Plain ``print`` gives no indication of *when* a long-running step (e.g. TTS
audio synthesis) is progressing, which makes hangs hard to diagnose from the
publish log. ``log_ts`` prefixes every line with a wall-clock timestamp so a
stuck step is visible from the gap between consecutive timestamps.
"""

from __future__ import annotations

from datetime import datetime


def log_ts(message: str) -> None:
    """Print ``message`` prefixed with an ``HH:MM:SS`` timestamp, flushed
    immediately (stdout is fully buffered when redirected to a file)."""
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)
