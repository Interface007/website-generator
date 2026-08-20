"""Pipeline runner: executes the configured steps in order."""

from __future__ import annotations

import time

from .config import BuildContext, SiteConfig
from .logutil import log_ts
from .steps import STEP_REGISTRY


def run_pipeline(config: SiteConfig) -> BuildContext:
    ctx = BuildContext(config=config)
    ctx.out_dir.mkdir(parents=True, exist_ok=True)

    for index, step_config in enumerate(config.pipeline):
        options = dict(step_config)
        step_name = options.pop("step")
        if options.pop("enabled", True) is False:
            log_ts(f"[{index + 1}] {step_name}: disabled, skipping")
            continue
        try:
            step = STEP_REGISTRY[step_name]
        except KeyError:
            known = ", ".join(sorted(STEP_REGISTRY))
            raise SystemExit(
                f"Unknown pipeline step '{step_name}' (known steps: {known})"
            ) from None
        log_ts(f"[{index + 1}/{len(config.pipeline)}] {step_name} - start")
        started = time.monotonic()
        step(ctx, options)
        elapsed = time.monotonic() - started
        log_ts(f"[{index + 1}/{len(config.pipeline)}] {step_name} - done in {elapsed:.1f}s")

    return ctx
