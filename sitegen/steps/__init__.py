"""Pipeline step registry."""

from __future__ import annotations

from . import (
    articles,
    cards,
    clean_output,
    content_page,
    copy_assets,
    copy_file,
    excel_table,
    favicons,
    gallery,
    sections,
    sitemap,
)

STEP_REGISTRY = {
    "articles": articles.run,
    "cards": cards.run,
    "clean_output": clean_output.run,
    "content_page": content_page.run,
    "copy_assets": copy_assets.run,
    "copy_file": copy_file.run,
    "excel_table": excel_table.run,
    "favicons": favicons.run,
    "gallery": gallery.run,
    "sections": sections.run,
    "sitemap": sitemap.run,
}
