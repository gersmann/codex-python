% Contributing to codex-python

Thanks for considering a contribution! This guide helps you get set up and make changes smoothly.

## Prerequisites
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) installed
- `make` available (optional but recommended)

## Quick Start
```
# Create an isolated environment (optional)
uv venv --python 3.13
. .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dev tools when running via uv
make lint   # ruff + mypy (installs on first run)
make test   # pytest
```

## Project Tasks
- Lint: `make lint`
- Format: `make fmt`
- Tests: `make test`
- Build: `uv build`

## Type Hints
This project is typed and ships a `py.typed` marker. Please keep public APIs typed.

## Commit Style
- Keep commits focused.
- Reference issues where applicable, e.g., `Fixes #123`.

## Release Process
1. Update the version in `codex/__init__.py` (SemVer).
2. Update `CHANGELOG.md`.
3. Merge to `main`.
4. Tag the release: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push --tags`.
5. GitHub Actions (publish workflow) will build and publish to PyPI on `v*` tags.

## Pre-commit (optional but recommended)
```
uvx pre-commit install
uvx pre-commit run --all-files
```

If you prefer, you can install pre-commit globally via `pipx` or `pip`.

## Reporting Issues
Please open an issue with reproduction steps, expected vs actual behavior, and environment info.

## Code of Conduct
By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

