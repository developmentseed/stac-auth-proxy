.PHONY: help test test-coverage test-fast lint format clean install dev-install docs

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	uv sync

dev-install: ## Install development dependencies
	uv sync --group dev

test: ## Run tests
	uv run pytest

test-fast: ## Run tests in parallel
	uv run pytest -n auto

test-coverage: ## Run tests with coverage
	@echo "🧪 Running tests with coverage..."
	uv run pytest \
		--cov=src/stac_auth_proxy \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=xml \
		--cov-fail-under=85 \
		-v
	@echo "✅ Coverage report generated!"
	@echo "📊 HTML report available at: htmlcov/index.html"
	@echo "📄 XML report available at: coverage.xml"
	@if [ "$(CI)" = "true" ]; then \
		echo "🚀 Running in CI environment"; \
	else \
		echo "💻 Running locally - opening HTML report..."; \
		if command -v open >/dev/null 2>&1; then \
			open htmlcov/index.html; \
		elif command -v xdg-open >/dev/null 2>&1; then \
			xdg-open htmlcov/index.html; \
		else \
			echo "Please open htmlcov/index.html in your browser to view the coverage report"; \
		fi; \
	fi

lint: ## Run linting
	uv run pre-commit run ruff-check --all-files
	uv run pre-commit run mypy --all-files

format: ## Format code
	uv run pre-commit run ruff-format --all-files

clean: ## Clean up generated files
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf .pytest_cache/
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

ci: ## Run CI checks locally
	uv run pre-commit run --all-files
	@echo "🧪 Running tests with coverage..."
	uv run pytest \
		-n auto \
		--cov=src/stac_auth_proxy \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=xml \
		--cov-fail-under=85 \
		-v
	@echo "✅ CI checks completed!"

docs: ## Serve documentation locally
	uv sync --extra docs
	DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run mkdocs serve