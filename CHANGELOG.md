% Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [0.2.12] - 2025-09-14
### Changed
- Unify protocol generation to TS → JSON Schema → Pydantic v2 using a native helper binary (`codex-protocol-schema`).
- Generate readable union variants (e.g., `EventMsgError`, `ClientRequestNewConversation`) via schema post‑processing.
- Allow extra fields on generated models via a shared `BaseModelWithExtras`.

### Removed
- Old TS→Python converter script (`scripts/generate_protocol_py.py`) and legacy Makefile flow.

### Dev
- Add `datamodel-code-generator` to dev deps; new Makefile `gen-protocol` target runs the full pipeline.
- Keep generated unions lint‑clean and forward‑ref safe with small post‑processing scripts.

[0.2.12]: https://github.com/gersmann/codex-python/releases/tag/v0.2.12

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
## [0.2.1] - 2025-09-10
### Changed
- Consolidate PyPI Trusted Publishing into a single publish.yml workflow: builds native wheels (Linux/macOS/Windows) and sdist, then publishes via OIDC.
- Remove separate native-wheels.yml to avoid split workflows.

[0.2.1]: https://github.com/gersmann/codex-python/releases/tag/v0.2.1

## [0.2.2] - 2025-09-10
### Fixed
- sdist build: add `crates/codex_native/pyproject.toml` (maturin PEP 517) so `maturin sdist -m crates/codex_native/Cargo.toml` succeeds under publish.yml.
- Ensure distribution naming is consistent for sdist and wheels (`codex-python`).

[0.2.2]: https://github.com/gersmann/codex-python/releases/tag/v0.2.2
\n+## [0.2.3] - 2025-09-11
### Fixed
- Publish workflow: flatten downloaded artifacts with `merge-multiple: true` so `twine` sees files directly in `dist/` (resolves "Unknown distribution format: 'sdist'" / "no packages in dist/").

[0.2.3]: https://github.com/gersmann/codex-python/releases/tag/v0.2.3
