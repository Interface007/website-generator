# Google Material Symbols

**Upstream:** https://github.com/google/material-design-icons
**Licence:** Apache License 2.0 (full text in [`LICENSE`](LICENSE))
**Style / size:** Material Symbols Outlined, 24px (`viewBox="0 -960 960 960"`)

## Where they are used

`templates/matzen/icons/project/*.svg` — 16 files. The `cards` pipeline step
inlines them into the generated pages, so they also end up embedded in every
built HTML file rather than being served as separate assets.

## Verification

Path geometry was compared byte for byte against the upstream repository on
2026-08-13 (upstream master at commit `50f0603134ce7b70b2d71b686cc13e8b57ccb74c`,
2026-07-31):

| local file | upstream symbol | path identical |
|---|---|---|
| `home.svg` | `home` | yes |
| `school.svg` | `school` | yes |
| `cloud.svg` | *(a different cloud symbol, renamed)* | no — see below |

The remaining files carry the same `0 -960 960 960` grid, which is specific to
Material Symbols.

## Modifications (Apache-2.0 §4(b))

The bundled copies differ from the upstream files as follows:

1. **Renamed.** Local file names are descriptive (`briefcase.svg`,
   `desktop.svg`, `hourglass.svg`, `cloud.svg`) and do not always match the
   upstream symbol name. `cloud.svg` in particular holds a different upstream
   cloud symbol than the one named `cloud`.
2. **Presentation attributes added** for inline embedding:
   `class="project-icon-svg"`, `fill="currentColor"`, `aria-hidden="true"`,
   explicit `width`/`height`.

No path geometry was edited; the differences are file naming and wrapper
attributes.

## Attribution

Apache-2.0 §4(a) is satisfied by shipping [`LICENSE`](LICENSE) alongside these
files; §4(b) by this document; §4(c) does not apply (the upstream SVGs carry no
notices); §4(d) does not apply (upstream ships no NOTICE file).

Google states that in-product attribution is welcome but not required:
"We'd love attribution in your app's about screen, but it's not required."
The redistribution obligations above apply regardless.
