#!/usr/bin/env python3
"""Thin wrapper kept for running the generator straight from a source checkout.

Installed usage is `sitegen-build --config ...` or `python -m sitegen --config ...`;
this shim only puts the repository root on sys.path first so the package does not
need to be installed during local development.

Usage:
    python generate.py --config configs/matzen.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sitegen.cli import main  # noqa: E402  (import after sys.path bootstrap)

if __name__ == "__main__":
    raise SystemExit(main())
