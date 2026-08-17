"""Gallery processing and rendering for the homepage site.

Port of ``semhps/scripts/gallery_builder.py``: processes gallery media
(images resized to max 1024px, JPEG converted to WebP, video thumbnails
via ffmpeg), and renders the accordion gallery / per-folder galleries
whose media URLs point at an external media host.
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
VIDEO_ROTATE_LEFT_SUFFIX = "-rotate-left"
VIDEO_ROTATE_RIGHT_SUFFIX = "-rotate-right"
GALLERY_THUMB_SIZE = (210, 128)
GALLERY_MAX_DIMENSION = 1024
GALLERY_VIDEO_THUMB_FRAME_INDEX = 9
JPEG_EXTENSIONS = {".jpg", ".jpeg"}


class GalleryBuilder:
    def __init__(self, assets_src: Path, assets_out: Path, gallery_media_base_url: str) -> None:
        self.assets_src = assets_src
        self.assets_out = assets_out
        self.gallery_media_base_url = gallery_media_base_url

    @staticmethod
    def gallery_output_rel_path(rel: Path, suffix: str) -> Path:
        if suffix in JPEG_EXTENSIONS:
            return rel.with_suffix(".webp")
        return rel

    @staticmethod
    def gallery_video_thumb_rel_path(rel: Path) -> Path:
        return rel.with_suffix(".webp")

    @staticmethod
    def resize_image_if_needed(image, max_dimension: int, resample_filter):
        width, height = image.size
        largest_side = max(width, height)
        if largest_side <= max_dimension:
            return image

        scale = max_dimension / largest_side
        new_size = (
            max(1, round(width * scale)),
            max(1, round(height * scale)),
        )
        return image.resize(new_size, resample_filter)

    @staticmethod
    def extract_video_thumbnail(
        ffmpeg_executable: str,
        video_path: Path,
        thumb_target: Path,
        frame_index: int,
    ) -> bool:
        filter_chain = (
            f"select=eq(n\\,{frame_index}),"
            f"scale={GALLERY_THUMB_SIZE[0]}:{GALLERY_THUMB_SIZE[1]}:force_original_aspect_ratio=increase,"
            f"crop={GALLERY_THUMB_SIZE[0]}:{GALLERY_THUMB_SIZE[1]}"
        )
        command = [
            ffmpeg_executable,
            "-y",
            "-i",
            str(video_path),
            "-vf",
            filter_chain,
            "-frames:v",
            "1",
            str(thumb_target),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return thumb_target.is_file()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def process_gallery_assets(self) -> None:
        gallery_root = self.assets_src / "gallery"
        if not gallery_root.is_dir():
            return

        from PIL import Image, ImageOps

        full_root = self.assets_out / "gallery" / "full"
        thumb_root = self.assets_out / "gallery" / "thumbs"

        ffmpeg_executable: str | None = None
        try:
            import imageio_ffmpeg

            ffmpeg_executable = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            print(
                "WARNING: imageio-ffmpeg is not installed. "
                "Video thumbnails are skipped.",
                file=sys.stderr,
            )

        for file_path in sorted(gallery_root.rglob("*")):
            if not file_path.is_file():
                continue

            suffix = file_path.suffix.lower()
            rel = file_path.relative_to(gallery_root)
            output_rel = self.gallery_output_rel_path(rel, suffix)

            if suffix in VIDEO_EXTENSIONS:
                full_target = full_root / output_rel
                full_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, full_target)

                if ffmpeg_executable:
                    video_thumb_rel = self.gallery_video_thumb_rel_path(rel)
                    thumb_target = thumb_root / video_thumb_rel
                    thumb_target.parent.mkdir(parents=True, exist_ok=True)

                    extracted = self.extract_video_thumbnail(
                        ffmpeg_executable,
                        file_path,
                        thumb_target,
                        GALLERY_VIDEO_THUMB_FRAME_INDEX,
                    )
                    if not extracted:
                        self.extract_video_thumbnail(ffmpeg_executable, file_path, thumb_target, 0)
                continue

            if suffix not in IMAGE_EXTENSIONS:
                continue

            full_target = full_root / output_rel
            full_target.parent.mkdir(parents=True, exist_ok=True)
            thumb_target = thumb_root / output_rel
            thumb_target.parent.mkdir(parents=True, exist_ok=True)

            with Image.open(file_path) as src_image:
                source_image = ImageOps.exif_transpose(src_image)
                full_image = self.resize_image_if_needed(
                    source_image,
                    GALLERY_MAX_DIMENSION,
                    Image.Resampling.LANCZOS,
                )

                full_save_kwargs: dict[str, int | bool | str] = {}
                if suffix in JPEG_EXTENSIONS:
                    if full_image.mode not in ("RGB", "L"):
                        full_image = full_image.convert("RGB")
                    full_save_kwargs = {"format": "WEBP", "quality": 85, "method": 6}
                elif suffix == ".png":
                    full_save_kwargs = {"optimize": True}
                elif suffix == ".webp":
                    full_save_kwargs = {"quality": 85}
                full_image.save(full_target, **full_save_kwargs)

                thumb_image = ImageOps.fit(
                    source_image,
                    GALLERY_THUMB_SIZE,
                    method=Image.Resampling.LANCZOS,
                )

                save_kwargs: dict[str, int | bool | str] = {}
                if suffix in JPEG_EXTENSIONS:
                    if thumb_image.mode not in ("RGB", "L"):
                        thumb_image = thumb_image.convert("RGB")
                    save_kwargs = {"format": "WEBP", "quality": 80, "method": 6}
                elif suffix == ".webp":
                    save_kwargs = {"quality": 85}
                elif suffix == ".png":
                    save_kwargs = {"optimize": True}
                thumb_image.save(thumb_target, **save_kwargs)

    @staticmethod
    def parse_gallery_folder_name(folder_name: str) -> tuple[str, bool]:
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(.+)$", folder_name)
        if not match:
            return folder_name, False

        year, month, day, title = match.groups()
        return f"{day}.{month}.{year} - {title}", True

    @staticmethod
    def parse_media_title_and_rotation(file_path: Path) -> tuple[str, str | None]:
        stem = file_path.stem
        rotation: str | None = None
        if stem.endswith(VIDEO_ROTATE_LEFT_SUFFIX):
            rotation = "left"
            stem = stem[: -len(VIDEO_ROTATE_LEFT_SUFFIX)]
        elif stem.endswith(VIDEO_ROTATE_RIGHT_SUFFIX):
            rotation = "right"
            stem = stem[: -len(VIDEO_ROTATE_RIGHT_SUFFIX)]
        return stem.replace("_", " ").strip(), rotation

    @staticmethod
    def render_gallery_asset_includes() -> str:
        return """
<link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/glightbox/dist/css/glightbox.min.css\" />
<link rel=\"stylesheet\" href=\"/assets/bilder-gallery.css\" />
<script src=\"https://cdn.jsdelivr.net/npm/glightbox/dist/js/glightbox.min.js\"></script>
<script src=\"/assets/bilder-gallery.js\"></script>
"""

    def collect_gallery_images(self) -> dict[str, dict[str, list[tuple[str, str, str, str, str | None]]]]:
        gallery_root = self.assets_src / "gallery"
        grouped: dict[str, dict[str, list[tuple[str, str, str, str, str | None]]]] = {}
        if not gallery_root.is_dir():
            return grouped

        for file_path in sorted(gallery_root.rglob("*")):
            if not file_path.is_file():
                continue
            suffix = file_path.suffix.lower()
            if suffix not in IMAGE_EXTENSIONS and suffix not in VIDEO_EXTENSIONS:
                continue

            rel = file_path.relative_to(gallery_root).as_posix()
            output_rel = self.gallery_output_rel_path(Path(rel), suffix).as_posix()
            thumb_rel = output_rel
            if suffix in VIDEO_EXTENSIONS:
                thumb_rel = self.gallery_video_thumb_rel_path(Path(rel)).as_posix()

            parts = rel.split("/")
            if len(parts) >= 3:
                level1, level2 = parts[0], parts[1]
            elif len(parts) == 2:
                level1, level2 = parts[0], "Sonstiges"
            else:
                level1, level2 = "Sonstiges", "Sonstiges"

            full_src = f"{self.gallery_media_base_url}/full/{output_rel}"
            thumb_src = f"{self.gallery_media_base_url}/thumbs/{thumb_rel}"
            title, rotation = self.parse_media_title_and_rotation(file_path)
            media_type = "video" if suffix in VIDEO_EXTENSIONS else "image"
            grouped.setdefault(level1, {}).setdefault(level2, []).append(
                (full_src, thumb_src, title, media_type, rotation)
            )

        return grouped

    def resolve_gallery_folder(self, folder_path: str, source_dir: Path) -> tuple[Path, str] | None:
        raw_path = Path(folder_path)
        assets_root = self.assets_src.resolve()
        source_root = self.assets_src.parent
        candidates = [source_dir / raw_path, source_root / raw_path, self.assets_src / raw_path]

        for candidate in candidates:
            candidate_resolved = candidate.resolve()
            if not candidate_resolved.is_dir():
                continue
            try:
                rel_path = candidate_resolved.relative_to(assets_root).as_posix()
            except ValueError:
                continue
            return candidate_resolved, rel_path

        return None

    def _render_media_item(
        self,
        full_src: str,
        thumb_src: str,
        caption: str,
        media_type: str,
        rotation: str | None,
        gallery_id: str,
    ) -> str:
        if media_type == "video":
            rotate_attr = f' data-rotate="{rotation}"' if rotation else ""
            return (
                f'<a href="{full_src}" class="glightbox galerie-item" data-gallery="{gallery_id}" '
                f'data-type="video" data-title="{caption}" aria-label="{caption}"{rotate_attr}>'
                f'<div class="galerie-video-container">'
                f'<img src="{thumb_src}" class="galerie-video-thumb" alt="{caption}" width="210" height="128" loading="lazy">'
                f'<div class="galerie-play-button">▶</div>'
                f'</div></a>'
            )
        return (
            f'<a href="{full_src}" class="glightbox galerie-item" data-gallery="{gallery_id}" '
            f'data-title="{caption}" aria-label="{caption}">'
            f'<img src="{thumb_src}" alt="{caption}" width="210" height="128" loading="lazy"></a>'
        )

    def render_gallery_for_folder(self, folder_path: str, source_dir: Path) -> str:
        resolved = self.resolve_gallery_folder(folder_path, source_dir)
        if resolved is None:
            return ""

        gallery_root, gallery_rel = resolved
        output_rel = gallery_rel.removeprefix("gallery/")
        items = []
        for file_path in sorted(gallery_root.rglob("*")):
            if not file_path.is_file():
                continue

            suffix = file_path.suffix.lower()
            if suffix not in IMAGE_EXTENSIONS and suffix not in VIDEO_EXTENSIONS:
                continue

            rel = file_path.relative_to(gallery_root).as_posix()
            output_media_rel = self.gallery_output_rel_path(Path(rel), suffix).as_posix()
            thumb_media_rel = output_media_rel
            if suffix in VIDEO_EXTENSIONS:
                thumb_media_rel = self.gallery_video_thumb_rel_path(Path(rel)).as_posix()

            full_src = f"{self.gallery_media_base_url}/full/{output_rel}/{output_media_rel}"
            thumb_src = f"{self.gallery_media_base_url}/thumbs/{output_rel}/{thumb_media_rel}"
            title, rotation = self.parse_media_title_and_rotation(file_path)
            media_type = "video" if suffix in VIDEO_EXTENSIONS else "image"
            items.append(
                self._render_media_item(
                    full_src, thumb_src, html.escape(title), media_type, rotation,
                    "folder-gallery",
                )
            )

        if not items:
            return ""
        return f"""
<div class=\"galerie-grid\">{' '.join(items)}</div>
"""

    def find_gallery_folder_for_date(self, date_str: str) -> str | None:
        gallery_root = self.assets_src / "gallery"
        if not gallery_root.is_dir():
            return None
        for year_dir in sorted(gallery_root.iterdir()):
            if not year_dir.is_dir():
                continue
            for folder in sorted(year_dir.iterdir()):
                if folder.is_dir() and folder.name.startswith(date_str):
                    return folder.name
        return None

    def render_bilder_gallery(self) -> str:
        grouped = self.collect_gallery_images()
        if not grouped:
            return "<p>Zurzeit sind keine Galerie-Bilder vorhanden.</p>"

        sections: list[str] = []
        accordion_index = 0
        for level1 in sorted(grouped.keys(), reverse=True):
            level1_sections: list[str] = []
            for level2 in sorted(grouped[level1].keys(), reverse=True):
                media_items = grouped[level1][level2]
                items = [
                    self._render_media_item(
                        full_src, thumb_src, html.escape(title), media_type, rotation,
                        f"bilder-{accordion_index}",
                    )
                    for full_src, thumb_src, title, media_type, rotation in media_items
                ]

                first_image = next((item for item in media_items if item[3] == "image"), None)
                if first_image is not None:
                    _, thumb_src, title, _, _ = first_image
                else:
                    _, thumb_src, title, _, _ = media_items[0]
                preview_caption = html.escape(title)
                preview_thumb = (
                    f'<img src="{thumb_src}" alt="{preview_caption}" width="100" height="50" '
                    f'loading="lazy">'
                )

                level2_display, _ = self.parse_gallery_folder_name(level2)
                section_id = f"galerie-panel-{accordion_index}"
                date_m2 = re.match(r"^(\d{4}-\d{2}-\d{2})-", level2)
                gallery_date_attr = f' data-gallery-date="{date_m2.group(1)}"' if date_m2 else ""
                level1_sections.append(
                    f'<article class="galerie-accordion-item" data-accordion-item{gallery_date_attr}>'
                    f'<button type="button" class="galerie-accordion-toggle" aria-expanded="false" '
                    f'aria-controls="{section_id}">'
                    f'<span class="galerie-accordion-thumb">{preview_thumb}</span>'
                    f'<span class="galerie-accordion-title">{html.escape(level2_display)}</span>'
                    f'</button>'
                    f'<div id="{section_id}" class="galerie-accordion-panel" hidden>'
                    f'<div class="galerie-grid">{" ".join(items)}</div>'
                    f'</div>'
                    f'</article>'
                )
                accordion_index += 1

            sections.append(
                f"<section class=\"galerie-block\"><h3>{html.escape(level1)}</h3>"
                f"{''.join(level1_sections)}</section>"
            )

        return "\n".join(sections)
