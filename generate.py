#!/usr/bin/env python3
"""Unified static site generator.

Usage:
    python generate.py --config configs/matzen.yaml
    python generate.py --config configs/shanty.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sitegen.config import ConfigError, load_config
from sitegen.logutil import log_ts
from sitegen.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a static site from a YAML config.")
    parser.add_argument("--config", required=True, help="Path to the site config YAML file")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    log_ts(f"Building site '{config.name}' -> {config.output_dir}")
    run_pipeline(config)
    log_ts("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
