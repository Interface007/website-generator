"""Step: generate favicon assets from one source image.

Port of process_favicon_assets from the homepage generator: PNG icons in
several sizes plus a multi-resolution favicon.ico.

Options:
  source     the favicon source image (e.g. .../_assets/favicons/favicon-image.png)
  target     output dir below the output dir (default "assets/favicons")
  sizes      PNG sizes (default [16, 32, 48, 180, 192, 512])
  ico_sizes  sizes embedded in favicon.ico (default [16, 32, 48])
"""

from __future__ import annotations

from PIL import Image, ImageOps

from ..config import BuildContext

DEFAULT_SIZES = (16, 32, 48, 180, 192, 512)
DEFAULT_ICO_SIZES = (16, 32, 48)


def run(ctx: BuildContext, options: dict) -> None:
    source = ctx.config.resolve_path(options["source"])
    if not source.is_file():
        raise FileNotFoundError(f"favicons: source image not found: {source}")

    output_dir = ctx.out_dir / options.get("target", "assets/favicons")
    output_dir.mkdir(parents=True, exist_ok=True)
    sizes = options.get("sizes", list(DEFAULT_SIZES))
    ico_sizes = [(s, s) for s in options.get("ico_sizes", list(DEFAULT_ICO_SIZES))]

    with Image.open(source) as source_image:
        base_image = ImageOps.exif_transpose(source_image).convert("RGBA")

        for size in sizes:
            icon_image = ImageOps.fit(
                base_image,
                (size, size),
                method=Image.Resampling.LANCZOS,
            )
            icon_image.save(output_dir / f"favicon-{size}.png", format="PNG", optimize=True)

        base_image.save(output_dir / "favicon.ico", format="ICO", sizes=ico_sizes)

    print(f"Generated {len(sizes)} favicon PNG(s) + favicon.ico")
