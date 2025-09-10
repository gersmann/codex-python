# codex-python

A minimal Python library scaffold using `uv` with Python 3.13+.

## Quickstart

- Requires Python 3.13+.
- Package import name: `codex`.
- Distribution name (PyPI): `codex-python`.

### Repo

- Git: `git@github.com:gersmann/codex-python.git`
- URL: https://github.com/gersmann/codex-python

## Usage

Basic non-interactive execution via Codex CLI:

```
from codex import run_exec

out = run_exec("explain this repo")
print(out)
```

Options:

- Choose model: `run_exec("...", model="gpt-4.1")`
- Full auto: `run_exec("scaffold a cli", full_auto=True)`
- Run in another dir: `run_exec("...", cd="/path/to/project")`

### Install uv

- macOS (Homebrew): `brew install uv`
- Or via install script:
  - Unix/macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `iwr https://astral.sh/uv/install.ps1 -UseBasicParsing | iex`

See: https://docs.astral.sh/uv/

### Create a virtual env (optional)

```
uv python install 3.13
uv venv --python 3.13
. .venv/bin/activate  # or .venv\Scripts\activate on Windows
```

### Build

```
uv build
```

Artifacts appear in `dist/` (`.whl` and `.tar.gz`).

### Publish to PyPI

- Manual:

```
export PYPI_API_TOKEN="pypi-XXXX"  # create at https://pypi.org/manage/account/token/
uv publish --token "$PYPI_API_TOKEN"
```

- GitHub Actions: add a repository secret `PYPI_API_TOKEN` and push a tag like `v0.1.0`.
  The workflow at `.github/workflows/publish.yml` builds and publishes with `uv` on `v*` tags.

### Dev tooling

- Lint: `make lint` (ruff + mypy)
- Tests: `make test` (pytest)
- Format: `make fmt` (ruff formatter)
 - Pre-commit: `uvx pre-commit install && uvx pre-commit run --all-files`

## Project Layout

```
.
├── codex/              # package root (import name: codex)
│   └── __init__.py     # version lives here
├── pyproject.toml      # PEP 621 metadata, hatchling build backend
├── README.md
└── .gitignore
```

## Versioning

Version is managed via `codex/__init__.py` and exposed as `__version__`. The build uses Hatch’s version source.

## Python Compatibility

- Requires Python `>=3.13`.
