.PHONY: help venv fmt lint test build publish clean

help:
	@echo "Common targets:"
	@echo "  make lint     - Run ruff and mypy"
	@echo "  make test     - Run pytest"
	@echo "  make build    - Build sdist and wheel with uv"
	@echo "  make publish  - Publish to PyPI via uv (uses PYPI_API_TOKEN)"
	@echo "  make clean    - Remove build artifacts"
	@echo "  make gen-protocol - Generate Python protocol bindings from codex-rs"

venv:
	uv venv --python 3.13
	@echo "Run: . .venv/bin/activate"

fmt:
	uv run --group dev ruff format .

lint:
	uv run --group dev ruff format .
	uv run --group dev ruff check --fix --unsafe-fixes .
	uv run --group dev mypy codex

test:
	@bash -lc 'uv run --group dev pytest -q; ec=$$?; if [ $$ec -eq 5 ]; then echo "No tests collected"; exit 0; else exit $$ec; fi'

build:
	uv build

publish: build
	@# Load local environment if present
	@set -e; \
	if [ -f .env ]; then set -a; . ./.env; set +a; fi; \
	if [ -n "$${UV_PUBLISH_TOKEN:-}" ]; then \
		echo "Publishing with token (UV_PUBLISH_TOKEN)"; \
		uv publish --token "$${UV_PUBLISH_TOKEN}"; \
	elif [ -n "$${PYPI_API_TOKEN:-}" ]; then \
		echo "Publishing with token (PYPI_API_TOKEN)"; \
		uv publish --token "$${PYPI_API_TOKEN}"; \
	elif [ -n "$${UV_PUBLISH_USERNAME:-}" ] && [ -n "$${UV_PUBLISH_PASSWORD:-}" ]; then \
		echo "Publishing with username/password (UV_PUBLISH_USERNAME)"; \
		uv publish --username "$${UV_PUBLISH_USERNAME}" --password "$${UV_PUBLISH_PASSWORD}"; \
	elif [ -n "$${PYPI_USERNAME:-}" ] && [ -n "$${PYPI_PASSWORD:-}" ]; then \
		echo "Publishing with username/password (PYPI_USERNAME)"; \
		uv publish --username "$${PYPI_USERNAME}" --password "$${PYPI_PASSWORD}"; \
	else \
		echo "No credentials found. Set UV_PUBLISH_TOKEN or PYPI_API_TOKEN, or UV_PUBLISH_USERNAME/UV_PUBLISH_PASSWORD (or PYPI_USERNAME/PYPI_PASSWORD)."; \
		exit 1; \
	fi

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache

gen-protocol:
	@echo "Generating TypeScript protocol types via codex-proj/codex-rs ..."
	@mkdir -p .generated/ts
	@if command -v codex >/dev/null 2>&1; then \
		if codex --help | grep -q "generate-ts"; then \
			echo "Using 'codex generate-ts'"; \
			codex generate-ts --out .generated/ts; \
		else \
			echo "'codex' installed but no generate-ts; falling back"; \
			cd codex-proj/codex-rs && cargo run -p codex-protocol-ts -- --out ../../.generated/ts; \
		fi; \
	else \
		echo "Using cargo run -p codex-protocol-ts"; \
		cd codex-proj/codex-rs && cargo run -p codex-protocol-ts -- --out ../../.generated/ts; \
	fi
	@echo "Generating Python bindings ..."
	@python3 scripts/generate_protocol_py.py .generated/ts
	@$(MAKE) fmt

.PHONY: build-native dev-native

build-native:
	@echo "Building native extension with maturin..."
	@maturin build -m crates/codex_native/Cargo.toml --release

dev-native:
	@echo "Installing native extension in dev mode..."
	@# Use a virtualenv when present; otherwise, fall back to build+pip install.
	@if [ -n "$$VIRTUAL_ENV" ] || [ -n "$$CONDA_PREFIX" ] || [ -d .venv ]; then \
		echo "Detected virtual environment; using maturin develop"; \
		maturin develop -m crates/codex_native/Cargo.toml; \
	else \
		echo "No virtualenv detected; building wheel and installing via pip"; \
		maturin build -m crates/codex_native/Cargo.toml --release; \
		python -m pip install --force-reinstall --no-deps crates/codex_native/target/wheels/*.whl; \
	fi
