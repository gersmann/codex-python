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
