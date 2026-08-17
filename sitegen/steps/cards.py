"""Step: render a card collection and splice it into a rendered page.

Cards live as individual Markdown files under ``collection`` (clean prose
in the body, style names + structured data in the front matter). They are
rendered through ``card_template`` into a ``grid_class`` grid and inserted
into ``page`` (already produced by an earlier ``content_page`` step) by
replacing ``placeholder`` — the same splice pattern used by ``excel_table``.

Options:
  collection      directory of card ``*.md`` files (sorted by name)
  card_template   Jinja template rendering one card
  grid_class      CSS class of the wrapping grid div
  page            output-relative HTML file to splice into
  placeholder     marker in the page replaced by the grid
                  (default ``<!-- cards -->``)
  icon_dir        sub-directory of the templates ``icons/`` folder holding
                  the SVG library (omit for card types without icons)
  icon_key        front-matter field naming the icon (default: ``glyph``
                  when ``icon_dir`` is set)
"""

from __future__ import annotations

from ..cards import CardError, load_cards, load_icon_library, render_grid
from ..config import BuildContext
from ..md import MarkdownConverter


def run(ctx: BuildContext, options: dict) -> None:
    collection = ctx.config.resolve_path(options["collection"])
    converter = MarkdownConverter(
        flavour=ctx.config.markdown_options.get("flavour", "hp"),
        table_class=ctx.config.markdown_options.get("table_class"),
    )
    cards = load_cards(collection, converter)

    icons: dict[str, str] = {}
    icon_key = None
    if options.get("icon_dir"):
        templates_dir = ctx.config.templates_dir
        icons = load_icon_library(templates_dir / "icons" / options["icon_dir"])
        icon_key = options.get("icon_key", "glyph")

    template = ctx.jinja.get_template(options["card_template"])
    grid = render_grid(cards, template, options["grid_class"], icons, icon_key)

    page_path = ctx.out_dir / options["page"]
    if not page_path.is_file():
        raise CardError(f"cards: page not found (render it first): {page_path}")
    with open(page_path, encoding="utf-8", newline="") as handle:
        page_html = handle.read()

    placeholder = options.get("placeholder", "<!-- cards -->")
    if placeholder not in page_html:
        raise CardError(f"cards: placeholder {placeholder!r} not found in {options['page']}")
    page_html = page_html.replace(placeholder, grid)
    ctx.write_output(options["page"], page_html)
    print(f"Rendered {len(cards)} card(s) into {options['page']}")
