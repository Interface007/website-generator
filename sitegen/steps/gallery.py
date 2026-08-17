"""Step: process gallery media for the homepage site.

Port of GalleryBuilder.process_gallery_assets: images are EXIF-corrected,
resized to a maximum dimension of 1024px, JPEGs converted to WebP, and
210x128 thumbnails generated; videos are copied and get an ffmpeg-extracted
thumbnail (skipped with a warning when imageio-ffmpeg is missing).

Options:
  assets_source          the _assets directory containing gallery/
  target                 assets output dir below the output dir
                         (default "assets")
  gallery_media_base_url external media host (default:
                         site.gallery_media_base_url; only used for URL
                         rendering elsewhere, not for processing)
"""

from __future__ import annotations

from ..config import BuildContext
from ..gallery_builder import GalleryBuilder


def run(ctx: BuildContext, options: dict) -> None:
    assets_source = ctx.config.resolve_path(options["assets_source"])
    assets_out = ctx.out_dir / options.get("target", "assets")
    media_base_url = options.get(
        "gallery_media_base_url", ctx.config.site.get("gallery_media_base_url", "")
    )

    builder = GalleryBuilder(assets_source, assets_out, media_base_url)
    builder.process_gallery_assets()
    print("Processed gallery assets.")
