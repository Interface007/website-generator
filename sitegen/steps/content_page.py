"""Step: render standalone Markdown content pages (hp flavour), e.g. the
privacy policy or the hand-maintained static pages. Port of the C#
ContentPageRenderer, extended with a directory mode.

Options:
  markdown_file   a single source .md file, or
  markdown_dir    a directory whose *.md files are all rendered; each file
                  can override rendering via front matter (Template,
                  PageTitle, Heading, OgType, Canonical, FootScripts, ... —
                  see HpPageRenderer)
  disclaimers     optional snippet templates appended to the page
  title_suffix / portrait_image / portrait_modifier  see HpPageRenderer
"""

from __future__ import annotations

from ..config import BuildContext
from ..hp_pages import HpPageRenderer, read_content


def run(ctx: BuildContext, options: dict) -> None:
    if "markdown_dir" in options:
        markdown_paths = sorted(ctx.config.resolve_path(options["markdown_dir"]).glob("*.md"))
        if not markdown_paths:
            raise FileNotFoundError(
                f"content_page: no .md files in {options['markdown_dir']}"
            )
    else:
        markdown_paths = [ctx.config.resolve_path(options["markdown_file"])]

    renderer = HpPageRenderer(ctx, options)
    disclaimers = tuple(options.get("disclaimers", []))
    for markdown_path in markdown_paths:
        article = read_content(markdown_path)
        ctx.write_output(
            article.output_file_name,
            renderer.render_page(article, disclaimers),
        )
        print(f"Rendered content page '{article.output_file_name}'.")
