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

Pin a tag from a consuming project's `requirements.txt`:

```
sitegen @ git+https://github.com/Interface007/website-generator.git@v1.0.0
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

## Releasing

The version lives in `sitegen/__init__.py` and is picked up by `pyproject.toml`.
Bump it, commit, then tag — consumers pin the tag:

```powershell
git tag v1.0.0
git push origin v1.0.0
```
