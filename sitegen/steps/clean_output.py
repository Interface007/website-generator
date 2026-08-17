"""Step: remove the output directory and recreate it empty."""

from __future__ import annotations

import shutil

from ..config import BuildContext


def run(ctx: BuildContext, options: dict) -> None:
    out_dir = ctx.out_dir
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    print(f"Cleaned output directory {out_dir}")
