.PHONY: help venv fmt lint test build publish clean

help:
	@echo "Common targets:"
	@echo "  make lint     - Run ruff and mypy"
	@echo "  make test     - Run pytest"
	@echo "  make build    - Build sdist and wheel with uv"
	@echo "  make publish  - Publish to PyPI via uv (uses PYPI_API_TOKEN)"
	@echo "  make clean    - Remove build artifacts"
	@echo "  make gen-stubs    - Generate .pyi stubs for the wheel-tag shim module"
	@echo "  make wheelhouse-linux    - Prebuild manylinux & musllinux wheels (x86_64, aarch64)"
	@echo "  make wheelhouse-clean    - Remove wheelhouse/"

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
	$(MAKE) gen-stubs

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

.PHONY: build-native dev-native

build-native:
	@echo "Building native extension with maturin..."
	@$(MATURIN) build -m crates/codex_native/Cargo.toml --release

dev-native:
	@echo "Installing native extension in dev mode..."
	@# Use a virtualenv when present; otherwise, fall back to build+pip install.
	@if [ -n "$$VIRTUAL_ENV" ] || [ -n "$$CONDA_PREFIX" ] || [ -d .venv ]; then \
		echo "Detected virtual environment; using maturin develop"; \
		$(MATURIN) develop -m crates/codex_native/Cargo.toml; \
	else \
		echo "No virtualenv detected; building wheel and installing via pip"; \
		$(MATURIN) build -m crates/codex_native/Cargo.toml --release; \
		python -m pip install --force-reinstall --no-deps crates/codex_native/target/wheels/*.whl; \
	fi
	$(MAKE) gen-stubs

.PHONY: gen-stubs
gen-stubs:
	@echo "Generating type stubs (.pyi) for codex_native..."
	@# Prefer the pyo3-stubgen CLI if available; fall back to the Python script; otherwise skip.
	@{ \
		uvx -q pyo3-stubgen codex_native -o . >/dev/null 2>&1 && echo "stubs: wrote codex_native.pyi"; \
	} || { \
		uv run --group dev python scripts/gen_stubs.py >/dev/null 2>&1 && echo "stubs: generated via pyo3_introspection" || echo "stubs: skipped (tools not available)"; \
	}

# -----------------------------------------------------------------------------
# Prebuild portable Linux wheels (manylinux and musllinux) via Docker maturin
# Produces wheels in ./wheelhouse suitable for offline installs:
#   pip install --only-binary=:all: --no-index --find-links wheelhouse codex-python
# Requires Docker; for cross-arch builds ensure binfmt/qemu is enabled.
# -----------------------------------------------------------------------------
.PHONY: wheelhouse-linux wheelhouse-clean wheelhouse-linux-amd64 wheelhouse-linux-arm64 wheelhouse-musl-amd64 wheelhouse-musl-arm64

WHEELHOUSE ?= wheelhouse
MANYLINUX_X86 ?= quay.io/pypa/manylinux2014_x86_64
MANYLINUX_ARM ?= quay.io/pypa/manylinux2014_aarch64
MUSLLINUX_X86 ?= quay.io/pypa/musllinux_1_2_x86_64
MUSLLINUX_ARM ?= quay.io/pypa/musllinux_1_2_aarch64

wheelhouse-clean:
	rm -rf $(WHEELHOUSE)

wheelhouse-linux: wheelhouse-clean
	@echo "Building manylinux2014 and musllinux_1_2 wheels for x86_64 and aarch64..."
	@mkdir -p $(WHEELHOUSE)
	# manylinux x86_64 (quay.io/pypa) — ABI3: build once with Python 3.12
	docker run --rm --platform linux/amd64 -v "$(PWD)":/io $(MANYLINUX_X86) \
            bash -lc 'set -e; \
              yum -y install curl perl-core >/dev/null 2>&1 || true; \
              (perl -MText::Template -e1 >/dev/null 2>&1 || (curl -sL https://cpanmin.us | perl - App::cpanminus Text::Template >/dev/null)); \
              curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal && \
              . $$HOME/.cargo/env && \
              P=$$(ls -1 /opt/python/cp312*/bin/python | head -n1); \
              $$P -m pip install -U pip maturin && \
              export CFLAGS="$$CFLAGS -D_DEFAULT_SOURCE -D_BSD_SOURCE"; \
              PATH=$$HOME/.cargo/bin:$$PATH $$P -m maturin build --release -m /io/crates/codex_native/Cargo.toml -i $$P -o /io/$(WHEELHOUSE)'
	# manylinux aarch64 (quay.io/pypa) — ABI3: build once with Python 3.12
	docker run --rm --platform linux/arm64 -v "$(PWD)":/io $(MANYLINUX_ARM) \
            bash -lc 'set -e; \
              yum -y install curl perl-core >/dev/null 2>&1 || true; \
              (perl -MText::Template -e1 >/dev/null 2>&1 || (curl -sL https://cpanmin.us | perl - App::cpanminus Text::Template >/dev/null)); \
              curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal && \
              . $$HOME/.cargo/env && \
              P=$$(ls -1 /opt/python/cp312*/bin/python | head -n1); \
              $$P -m pip install -U pip maturin && \
              export CFLAGS="$$CFLAGS -D_DEFAULT_SOURCE -D_BSD_SOURCE"; \
              PATH=$$HOME/.cargo/bin:$$PATH $$P -m maturin build --release -m /io/crates/codex_native/Cargo.toml -i $$P -o /io/$(WHEELHOUSE)'
	# musllinux (Alpine) x86_64 (quay.io/pypa) — ABI3
	docker run --rm --platform linux/amd64 -v "$(PWD)":/io $(MUSLLINUX_X86) \
            bash -lc 'set -e; \
              apk add --no-cache curl perl perl-text-template >/dev/null 2>&1 || true; \
              curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal && \
              . $$HOME/.cargo/env && \
              P=$$(ls -1 /opt/python/cp312*/bin/python | head -n1); \
              $$P -m pip install -U pip maturin && \
              export CFLAGS="$$CFLAGS -D_DEFAULT_SOURCE -D_BSD_SOURCE"; \
              PATH=$$HOME/.cargo/bin:$$PATH $$P -m maturin build --release -m /io/crates/codex_native/Cargo.toml -i $$P --compatibility musllinux_1_2 -o /io/$(WHEELHOUSE)'
	# musllinux (Alpine) aarch64 (quay.io/pypa) — ABI3
	docker run --rm --platform linux/arm64 -v "$(PWD)":/io $(MUSLLINUX_ARM) \
            bash -lc 'set -e; \
              apk add --no-cache curl perl perl-text-template >/dev/null 2>&1 || true; \
              curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal && \
              . $$HOME/.cargo/env && \
              P=$$(ls -1 /opt/python/cp312*/bin/python | head -n1); \
              $$P -m pip install -U pip maturin && \
              export CFLAGS="$$CFLAGS -D_DEFAULT_SOURCE -D_BSD_SOURCE"; \
              PATH=$$HOME/.cargo/bin:$$PATH $$P -m maturin build --release -m /io/crates/codex_native/Cargo.toml -i $$P --compatibility musllinux_1_2 -o /io/$(WHEELHOUSE)'
	@echo "Wheelhouse contents:" && ls -al $(WHEELHOUSE)

# Build only manylinux x86_64 (useful to avoid cross-arch emulation)
	wheelhouse-linux-amd64: wheelhouse-clean
		@mkdir -p $(WHEELHOUSE)
	docker run --rm --platform linux/amd64 -v "$(PWD)":/io $(MANYLINUX_X86) \
            bash -lc 'set -e; yum -y install curl perl-core >/dev/null 2>&1 || true; \
              (perl -MText::Template -e1 >/dev/null 2>&1 || (curl -sL https://cpanmin.us | perl - App::cpanminus Text::Template >/dev/null)); \
              curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal; \
              . $$HOME/.cargo/env; P=$$(ls -1 /opt/python/cp312*/bin/python | head -n1); \
              $$P -m pip install -U pip maturin; \
              export CFLAGS="$$CFLAGS -D_DEFAULT_SOURCE -D_BSD_SOURCE"; \
              PATH=$$HOME/.cargo/bin:$$PATH $$P -m maturin build --release -j $$(( $$(nproc) )) -m /io/crates/codex_native/Cargo.toml -i $$P -o /io/$(WHEELHOUSE)'

# Build only manylinux aarch64 (fast on Apple Silicon; slow on x86_64)
	wheelhouse-linux-arm64: wheelhouse-clean
		@mkdir -p $(WHEELHOUSE)
	docker run --rm --platform linux/arm64 -v "$(PWD)":/io $(MANYLINUX_ARM) \
            bash -lc 'set -e; yum -y install curl perl-core >/dev/null 2>&1 || true; \
              (perl -MText::Template -e1 >/dev/null 2>&1 || (curl -sL https://cpanmin.us | perl - App::cpanminus Text::Template >/dev/null)); \
              curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal; \
              . $$HOME/.cargo/env; P=$$(ls -1 /opt/python/cp312*/bin/python | head -n1); \
              $$P -m pip install -U pip maturin; \
              export CFLAGS="$$CFLAGS -D_DEFAULT_SOURCE -D_BSD_SOURCE"; \
              PATH=$$HOME/.cargo/bin:$$PATH $$P -m maturin build --release -j $$(( $$(nproc) )) -m /io/crates/codex_native/Cargo.toml -i $$P -o /io/$(WHEELHOUSE)'

# Build only musllinux x86_64 (Alpine)
	wheelhouse-musl-amd64: wheelhouse-clean
		@mkdir -p $(WHEELHOUSE)
	docker run --rm --platform linux/amd64 -v "$(PWD)":/io $(MUSLLINUX_X86) \
            bash -lc 'set -e; apk add --no-cache curl perl perl-text-template >/dev/null 2>&1 || true; \
              curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal; \
              . $$HOME/.cargo/env; P=$$(ls -1 /opt/python/cp312*/bin/python | head -n1); \
              $$P -m pip install -U pip maturin; \
              export CFLAGS="$$CFLAGS -D_DEFAULT_SOURCE -D_BSD_SOURCE"; \
              PATH=$$HOME/.cargo/bin:$$PATH $$P -m maturin build --release --compatibility musllinux_1_2 -j $$(( $$(nproc) )) -m /io/crates/codex_native/Cargo.toml -i $$P -o /io/$(WHEELHOUSE)'

# Build only musllinux aarch64 (Alpine)
	wheelhouse-musl-arm64: wheelhouse-clean
		@mkdir -p $(WHEELHOUSE)
	docker run --rm --platform linux/arm64 -v "$(PWD)":/io $(MUSLLINUX_ARM) \
            bash -lc 'set -e; apk add --no-cache curl perl perl-text-template >/dev/null 2>&1 || true; \
              curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal; \
              . $$HOME/.cargo/env; P=$$(ls -1 /opt/python/cp312*/bin/python | head -n1); \
              $$P -m pip install -U pip maturin; \
              export CFLAGS="$$CFLAGS -D_DEFAULT_SOURCE -D_BSD_SOURCE"; \
              PATH=$$HOME/.cargo/bin:$$PATH $$P -m maturin build --release --compatibility musllinux_1_2 -j $$(( $$(nproc) )) -m /io/crates/codex_native/Cargo.toml -i $$P -o /io/$(WHEELHOUSE)'
.PHONY: help venv fmt lint test build publish clean gen-stubs build-native dev-native

# Prefer uvx-managed maturin; fall back to system if present
MATURIN ?= uvx maturin
