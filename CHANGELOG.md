% Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [0.1.1] - 2025-09-10
### Added
- CodexClient synchronous wrapper with defaults
- Python API `run_exec` with robust error handling

### Changed
- Switch publish workflow to PyPI Trusted Publishing (OIDC)
- Docs and Makefile updates

## [0.1.0] - 2025-09-10
### Added
- Initial project scaffold with Python 3.13+
- Packaging with Hatchling and uv build/publish
- CI workflow (lint + test)
- Publishing workflow on `v*` tags
- Dev tooling: ruff, pytest, mypy, Makefile
- Typing marker (`py.typed`)
- MIT License

[0.1.0]: https://github.com/gersmann/codex-python/releases/tag/v0.1.0
[0.1.1]: https://github.com/gersmann/codex-python/releases/tag/v0.1.1
