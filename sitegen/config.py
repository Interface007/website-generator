"""Configuration loading and the shared build context."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader


class ConfigError(Exception):
    """Raised for invalid or incomplete site configurations."""


def _expand(path_value: str) -> str:
    return os.path.expandvars(os.path.expanduser(path_value))


@dataclass
class SiteConfig:
    """Validated site configuration."""

    config_path: Path
    raw: dict[str, Any]

    @property
    def config_dir(self) -> Path:
        return self.config_path.parent

    def resolve_path(self, value: str) -> Path:
        """Resolve a path from the config: ``~`` and environment variables
        are expanded; relative paths are relative to the config file."""
        expanded = Path(_expand(value))
        if expanded.is_absolute():
            return expanded
        return (self.config_dir / expanded).resolve()

    # -- required sections ---------------------------------------------
    @property
    def site(self) -> dict[str, Any]:
        return self.raw.get("site", {})

    @property
    def name(self) -> str:
        return self.site.get("name", self.config_path.stem)

    @property
    def base_url(self) -> str:
        return self.site.get("base_url", "")

    @property
    def output_dir(self) -> Path:
        try:
            return self.resolve_path(self.raw["output"]["dir"])
        except KeyError:
            raise ConfigError("Config must define output.dir") from None

    @property
    def newline(self) -> str:
        """Newline used for generator-joined lines (e.g. table rows,
        sitemap). Kept configurable so output can match the historical
        CRLF output of the C# generator regardless of host OS."""
        return self.raw.get("output", {}).get("newline", "\n")

    @property
    def templates_dir(self) -> Path | None:
        value = self.raw.get("templates", {}).get("dir")
        return self.resolve_path(value) if value else None

    @property
    def markdown_options(self) -> dict[str, Any]:
        return self.raw.get("markdown", {})

    @property
    def pipeline(self) -> list[dict[str, Any]]:
        steps = self.raw.get("pipeline")
        if not steps or not isinstance(steps, list):
            raise ConfigError("Config must define a non-empty pipeline list")
        for index, step in enumerate(steps):
            if not isinstance(step, dict) or "step" not in step:
                raise ConfigError(f"pipeline[{index}] must be a mapping with a 'step' key")
        return steps


def load_config(path: str | os.PathLike) -> SiteConfig:
    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise ConfigError(f"Config file not found: {config_path}")
    with open(config_path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ConfigError(f"Config file is not a YAML mapping: {config_path}")
    config = SiteConfig(config_path=config_path, raw=raw)
    _ = config.output_dir  # validate eagerly
    _ = config.pipeline
    return config


@dataclass
class BuildContext:
    """State shared between pipeline steps of a single build run."""

    config: SiteConfig
    # Output file name -> authoritative content date, filled by the
    # articles step and consumed by the sitemap step.
    content_dates: dict[str, Any] = field(default_factory=dict)
    _jinja: Environment | None = None

    @property
    def out_dir(self) -> Path:
        return self.config.output_dir

    @property
    def newline(self) -> str:
        return self.config.newline

    @property
    def jinja(self) -> Environment:
        if self._jinja is None:
            templates_dir = self.config.templates_dir
            if templates_dir is None:
                raise ConfigError("templates.dir is required for template rendering steps")
            newline_sequence = self.config.raw.get("templates", {}).get(
                "newline_sequence", "\n"
            )
            self._jinja = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                autoescape=False,
                keep_trailing_newline=True,
                newline_sequence=newline_sequence,
            )
        return self._jinja

    def read_template_text(self, name: str) -> str:
        """Read a template-directory file verbatim (no Jinja rendering),
        preserving its exact newlines. Used for HTML snippet includes."""
        templates_dir = self.config.templates_dir
        if templates_dir is None:
            raise ConfigError("templates.dir is required")
        with open(templates_dir / name, encoding="utf-8", newline="") as handle:
            return handle.read()

    def write_output(self, relative: str | Path, content: str) -> Path:
        """Write text to the output directory without newline translation."""
        target = self.out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        return target
