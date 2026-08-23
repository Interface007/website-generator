#!/usr/bin/env python3
"""Command line entry point for the static site generator.

Usage:
    sitegen-build --config configs/matzen.yaml
    python -m sitegen --config configs/matzen.yaml
"""

from __future__ import annotations

import argparse
import sys

from .config import ConfigError, load_config
from .logutil import log_ts
from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the generator CLI."""
    parser = argparse.ArgumentParser(
        prog="sitegen-build",
        description="Generate a static site from a YAML config.",
    )
    parser.add_argument("--config", required=True, help="Path to the site config YAML file")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Load the config, run the pipeline and return a process exit code."""
    args = build_parser().parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    log_ts(f"Building site '{config.name}' -> {config.output_dir}")
    run_pipeline(config)
    log_ts("Done.")
    return 0
