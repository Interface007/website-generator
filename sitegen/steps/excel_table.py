"""Step: render rows from an Excel workbook into an HTML template.

Port of the hp MOOC table generation (Program.cs): reads the course list,
sorts it, formats one <tr> per row and splices the rows into the template
between ``marker_open`` + ``marker_close`` (originally ``<tbody></tbody>``).

Options:
  workbook       path to the .xlsx file
  sheet          1-based worksheet index (default 1)
  skip_rows      header rows to skip (default 1)
  columns        list of column specs: {index: <1-based>, type: text|date,
                 format: <strftime, for date>}
  sort_by        0-based position in `columns` to sort by (default: none)
  sort_desc      sort descending (default true)
  row_template   Python format string; {0}, {1}, ... are the column values
  template_file  HTML file to splice the rows into
  template_from_output  if true, template_file is relative to the output
                 dir (splice into a page rendered by an earlier step)
  marker_open    e.g. "<tbody>"
  marker_close   e.g. "</tbody>"
  output         output file name below the output dir
"""

from __future__ import annotations

from datetime import date, datetime

import openpyxl

from ..config import BuildContext
from ..textutil import try_parse_date


def _cell_value(cell, spec: dict) -> str:
    value = cell.value
    if value is None:
        return ""
    if spec.get("type") == "date":
        fmt = spec.get("format", "%Y-%m-%d")
        if isinstance(value, (datetime, date)):
            return value.strftime(fmt)
        parsed = try_parse_date(str(value))
        if parsed is None:
            raise ValueError(f"Cannot parse date cell value: {value!r}")
        return parsed.strftime(fmt)
    return str(value)


def run(ctx: BuildContext, options: dict) -> None:
    workbook_path = ctx.config.resolve_path(options["workbook"])
    workbook = openpyxl.load_workbook(workbook_path, data_only=True)
    worksheet = workbook.worksheets[options.get("sheet", 1) - 1]

    columns = options["columns"]
    skip_rows = options.get("skip_rows", 1)

    rows: list[list[str]] = []
    for row in worksheet.iter_rows(min_row=skip_rows + 1):
        if all(cell.value is None for cell in row):
            continue  # ClosedXML's RowsUsed() also skipped empty rows
        rows.append([_cell_value(row[spec["index"] - 1], spec) for spec in columns])

    sort_by = options.get("sort_by")
    if sort_by is not None:
        # Python's sort is stable also with reverse=True, matching LINQ's
        # stable OrderByDescending.
        rows.sort(key=lambda r: r[sort_by], reverse=options.get("sort_desc", True))

    row_template = options["row_template"]
    rendered = [row_template.format(*row) for row in rows]

    if options.get("template_from_output"):
        template_path = ctx.out_dir / options["template_file"]
    else:
        template_path = ctx.config.resolve_path(options["template_file"])
    with open(template_path, encoding="utf-8", newline="") as handle:
        template_html = handle.read()

    marker_open = options.get("marker_open", "<tbody>")
    marker_close = options.get("marker_close", "</tbody>")
    marker = marker_open + marker_close
    if marker not in template_html:
        raise ValueError(f"Marker {marker!r} not found in {template_path}")

    nl = ctx.newline
    replacement = f"{marker_open}{nl}{nl.join(rendered)}{nl}{marker_close}"
    ctx.write_output(options["output"], template_html.replace(marker, replacement))
    print(f"Rendered {options['output']} with {len(rows)} row(s).")
