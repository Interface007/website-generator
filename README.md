# website-generator

Website Generator generates a static website from markdown, images and other source files

## Licensing

This repository is licensed in two parts.

| Part | Licence | Covers |
|------|---------|--------|
| **Software** | [MIT](LICENSE) | `sitegen/`, `generate.py`, `conftest.py`, `tests/`, `configs/`, the HTML/CSS/JS template markup in `templates/` |
| **Website content & media** | [All rights reserved](LICENSE-CONTENT) | `content/**` and the personal images, icons, branding and audio under `templates/matzen/static/` |

The generator is free software — use it, fork it, ship it. The site content
that ships with it is only there so the generator can be run and understood
end to end; it is **not** licensed for reuse. To build your own site, replace
`content/` and the media listed in [`LICENSE-CONTENT`](LICENSE-CONTENT) with
your own files.

### Third-party assets

The icons in `templates/matzen/icons/project/` are Google Material Symbols,
used under the Apache License 2.0 — see [`NOTICE`](NOTICE) and
[`third-party/material-symbols/`](third-party/material-symbols/). The generator
inlines them into the pages it builds, so sites built with it carry the same
obligation.

The brand icons in `templates/matzen/icons/brand/` are of **unresolved origin**
and are not covered by the MIT grant; see
[`third-party/README.md`](third-party/README.md). The generated pages also load
jQuery, DataTables and umami from public CDNs; those keep their own licences and
are not redistributed here.

### First run

Create and activate an environment, the install requirements:

``` PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the generator:
```
python generate.py --config ./configs/matzen.yaml
```