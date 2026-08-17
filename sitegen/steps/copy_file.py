"""Step: copy a single file into the output directory.

Options:
  source    file to copy
  target    path below the output dir (default: the source file name)
  optional  if true, a missing source is not an error (default: false)
"""

from __future__ import annotations

import shutil

from ..config import BuildContext


def run(ctx: BuildContext, options: dict) -> None:
    source = ctx.config.resolve_path(options["source"])
    if not source.is_file():
        if options.get("optional", False):
            print(f"copy_file: optional source not found, skipping: {source}")
            return
        raise FileNotFoundError(f"copy_file: source not found: {source}")

    target = ctx.out_dir / options.get("target", source.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"Copied {source.name}")
