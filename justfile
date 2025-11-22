#!/usr/bin/env just --justfile

# Default recipe
default:
    @just --list

# Setup the development environment
setup:
    @echo "Setting up development environment..."
    @if ! command -v uv &> /dev/null; then \
        echo "uv not found, installing via python3..."; \
        python3 -m pip install --upgrade pip; \
        python3 -m pip install uv; \
    fi
    uv sync
    uv pip install ruff
    @echo "✓ Setup complete"

# Clean build artifacts and cache files
clean:
    @echo "Cleaning project..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name ".DS_Store" -delete 2>/dev/null || true
    rm -rf build/ dist/ .venv/ 2>/dev/null || true
    @echo "✓ Clean complete"

# Check code formatting and linting
check:
    @echo "Checking code formatting and linting..."
    ruff format .
    ruff check . --fix
    ruff check .
    @echo "✓ All checks passed"
