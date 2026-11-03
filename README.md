# website-generator

`sitegen` generates a static website from markdown, images and other source files,
driven by a single YAML config.

The repository ships **only the generator**. Configs, templates and content belong
to the site repository that consumes it — see
[Interface007/hp](https://github.com/Interface007/hp) for a full production setup.

## Licensing

Everything in this repository is [MIT](LICENSE) licensed.

Site content, personal media and brand assets that used to live here have moved to
the site repositories that own them; their licence and third-party attribution
notices moved with them.

## Install

Pin the wheel built and published for a release in a consuming project's
`requirements.txt`:

```
sitegen @ https://github.com/Interface007/website-generator/releases/download/v1.0.5/sitegen-1.0.5-py3-none-any.whl
```

Then build a site:

```
sitegen-build --config path\to\site.yaml
```

`python -m sitegen --config path\to\site.yaml` is equivalent and does not depend on
the console script being on `PATH`.

All paths inside the config are resolved relative to the config file itself
(`~` and environment variables are expanded), so the generator never assumes
anything about where it is installed.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt   # editable install incl. pytest
```

Run the tests:

```powershell
python -m pytest
```

Run the generator straight from the checkout, without installing:

```powershell
python generate.py --config .\configs\shanty.yaml
```

To develop the generator against a site repository, install it editable into that
repository's venv:

```powershell
python -m pip install -e ..\website-generator
```

## Page template variables

`HpPageRenderer` (steps `articles` and `content_page`) passes, among others,
`page_title`, `heading`, `page_lang`, `canonical_url`, `meta_dates`,
`meta_content`, `content`, `disclaimer` and `foot_scripts` to the page template.

For a schema.org `Article` JSON-LD block it additionally passes raw,
**not HTML-encoded** values — output them with Jinja's `|tojson` filter:

| Variable         | Value                                                                  |
|------------------|------------------------------------------------------------------------|
| `is_article`     | `True` only for article pages of the `articles` step (not the overview, not `content_page`) |
| `ld_headline`    | front matter `Heading`, else the title                                 |
| `ld_description` | description (`Thema` / `Description`)                                  |
| `ld_language`    | same as `page_lang`                                                    |
| `ld_url`         | same as `canonical_url`                                                |
| `ld_published`   | content date as `YYYY-MM-DD`, or `None` (→ `null`)                     |
| `ld_modified`    | front matter `Modified` / `DateModified`, else `ld_published`          |

```jinja
{% if is_article %}
<script type="application/ld+json">
{ "@type": "Article", "headline": {{ ld_headline|tojson }}, "url": {{ ld_url|tojson }},
  "datePublished": {{ ld_published|tojson }}, "dateModified": {{ ld_modified|tojson }} }
</script>
{% endif %}
```

On article pages the `articles` step post-processes `application/ld+json`
blocks for audio: if the article has an audio file, the placeholder
`"contentUrl": ""` is replaced by the absolute audio URL; otherwise the whole
`"audio": {...}` member is removed so the block stays valid JSON.

## Releases

Every push to `main` runs the release workflow. It increments the patch version
in `sitegen/__init__.py`, runs the tests, builds the wheel and source distribution,
generates an SPDX 2.3 JSON SBOM for the installed generator and its runtime
dependency tree, then tags the version and publishes all three artifacts as a
GitHub release. The generated version commit and tag are pushed to `main`.

Consumers should pin the matching wheel URL in `requirements.txt`; the release
also includes the source distribution and `sitegen-<version>.spdx.json` SBOM.
