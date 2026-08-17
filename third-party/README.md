# Third-party assets

Assets in this repository that are not covered by the root
[`LICENSE`](../LICENSE) (MIT) or by [`LICENSE-CONTENT`](../LICENSE-CONTENT).

| Asset | Location | Origin | Licence | Status |
|---|---|---|---|---|
| Material Symbols icons | `templates/matzen/icons/project/*.svg` | [google/material-design-icons](https://github.com/google/material-design-icons) | Apache-2.0 | ✅ attributed — see [`material-symbols/`](material-symbols/) |
| Brand icons | `templates/matzen/icons/brand/*.svg` | **unknown** | **unresolved** | ⚠️ see below |
| jQuery, DataTables, umami | loaded from public CDNs at runtime | upstream | own licences | not redistributed here |

## ⚠️ Unresolved: brand icons

`templates/matzen/icons/brand/*.svg` (7 files: azure, facebook, github,
linkedin, mastodon, stackoverflow, xing) are on a 24×24 grid, which is a common
convention, but they are **not** Simple Icons — the path data differs:

```
local        github.svg   M12 0C5.374 0 0 5.373 0 12 0 17.302 3.438 21.8 8.207 23.387…
Simple Icons github       M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385…
```

Their origin and licence are therefore undetermined, and no attribution can be
written for them until that is resolved. Two ways out:

1. Establish the source and document it here, mirroring `material-symbols/`.
2. Replace all seven with [Simple Icons](https://github.com/simple-icons/simple-icons)
   (CC0-1.0, no attribution required), leaving only a trademark note:
   *brand icons are trademarks of their respective owners and are used here to
   reference the linked profiles.*

Until then these seven files are **not** covered by the MIT grant in the root
`LICENSE`.
