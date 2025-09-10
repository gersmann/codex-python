% Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [0.2.0] - 2025-09-10
### Added
- Fully-typed Pydantic config `CodexConfig` mirroring Rust `ConfigOverrides`.
- Native helper `codex.native.preview_config()` to inspect effective configuration.
- Export `EventMsg` at `codex.EventMsg` for convenience.

### Changed
- Consolidated on native bindings; removed subprocess CLI wrapper from public path.
- Regenerated protocol models with `extra='allow'` and placed `model_config` at class end.
- Event envelope now uses typed union: `Event.msg: EventMsg`.

### CI/Build
- `make gen-protocol` prefers `codex generate-ts --out` with cargo fallback.
- Native wheels CI builds for CPython 3.12/3.13 (attempts 3.14) with PyPI Trusted Publishing.

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
[0.2.0]: https://github.com/gersmann/codex-python/releases/tag/v0.2.0
