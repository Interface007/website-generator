"""Step: regenerate sitemap.xml. Port of the C# SitemapGenerator.

A page's <lastmod> is taken from its content date (articles step) when
available, otherwise from the last Git commit touching the file, and as a
final fallback from the file's last write time (UTC).

Options:
  scan_dir     directory whose top-level *.html files make up the site
               (default: the output dir)
  exclude      glob patterns of file names to exclude (case-insensitive)
  git_repo     repository root for git-based lastmod dates (optional)
  priorities   ordered list of {pattern: <glob>, priority: "0.64"} rules
  default_priority  fallback priority (default "0.80")
  output       file name (default sitemap.xml)
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path

from ..config import BuildContext


def run(ctx: BuildContext, options: dict) -> None:
    scan_dir = (
        ctx.config.resolve_path(options["scan_dir"])
        if options.get("scan_dir")
        else ctx.out_dir
    )
    base_url = ctx.config.base_url
    excludes = [pattern.lower() for pattern in options.get("exclude", [])]

    pages = [
        path.name
        for path in scan_dir.glob("*.html")
        if not any(fnmatch(path.name.lower(), pattern) for pattern in excludes)
    ]
    # Home first, the remaining pages alphabetically.
    pages.sort(key=lambda name: (0 if name.lower() == "index.html" else 1, name.lower()))

    git_repo = ctx.config.resolve_path(options["git_repo"]) if options.get("git_repo") else None

    nl = ctx.newline
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for page in pages:
        loc = base_url if page.lower() == "index.html" else base_url + page
        lastmod = _last_modified(ctx, page, scan_dir / page, git_repo)
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <priority>{_priority(page, options)}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")

    output_name = options.get("output", "sitemap.xml")
    ctx.write_output(output_name, nl.join(lines) + nl)
    print(f"Wrote {output_name} with {len(pages)} URL(s).")


def _priority(page: str, options: dict) -> str:
    for rule in options.get("priorities", []):
        if fnmatch(page.lower(), rule["pattern"].lower()):
            return str(rule["priority"])
    return str(options.get("default_priority", "0.80"))


def _last_modified(ctx: BuildContext, page: str, file_path: Path, git_repo: Path | None) -> str:
    content_date = ctx.content_dates.get(page.lower())
    if content_date is not None:
        return content_date.strftime("%Y-%m-%d")

    if git_repo is not None:
        git_date = _git_last_commit_date(git_repo, file_path)
        if git_date:
            return git_date

    mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
    return mtime.strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_last_commit_date(repo_root: Path, file_path: Path) -> str:
    """Committer date (ISO 8601) of the last commit touching the file."""
    try:
        relative = file_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return ""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", relative],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""
