.PHONY: help venv fmt lint test build publish clean

help:
	@echo "Common targets:"
	@echo "  make lint     - Run ruff and mypy"
	@echo "  make test     - Run pytest"
	@echo "  make build    - Build sdist and wheel with uv"
	@echo "  make publish  - Publish to PyPI via uv (uses PYPI_API_TOKEN)"
	@echo "  make clean    - Remove build artifacts"

venv:
	uv venv --python 3.13
	@echo "Run: . .venv/bin/activate"

fmt:
	uv run --group dev ruff format .

lint:
	uv run --group dev ruff format --check .
	uv run --group dev ruff check .
	uv run --group dev mypy codex

test:
	uv run --group dev pytest

build:
	uv build

publish: build
	@if [ -z "$${PYPI_API_TOKEN}" ]; then \
		echo "PYPI_API_TOKEN is not set"; \
		exit 1; \
	fi
	uv publish --token "$$PYPI_API_TOKEN"

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache
