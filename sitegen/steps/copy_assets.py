"""Step: recursively copy an asset tree into the output directory.

Options:
  source        directory to copy from
  target        directory below the output dir (default: "")
  exclude_dirs  top-level sub-directories to skip (e.g. the gallery,
                which is processed by the gallery step instead)
  include       optional glob patterns on the file name (case-insensitive,
                e.g. ["*.ico", "*.css"]); when set, only matching files
                are copied
"""

from __future__ import annotations

import shutil
from fnmatch import fnmatch

from ..config import BuildContext


def run(ctx: BuildContext, options: dict) -> None:
    source = ctx.config.resolve_path(options["source"])
    target_root = ctx.out_dir / options.get("target", "")
    exclude_dirs = set(options.get("exclude_dirs", []))
    include = [pattern.lower() for pattern in options.get("include", [])]

    if not source.is_dir():
        print(f"copy_assets: source not found, skipping: {source}")
        return

    copied = 0
    for item in source.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(source)
        if rel.parts and rel.parts[0] in exclude_dirs:
            continue
        if include and not any(fnmatch(item.name.lower(), pattern) for pattern in include):
            continue
        destination = target_root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)
        copied += 1
    print(f"Copied {copied} asset file(s) from {source}")
