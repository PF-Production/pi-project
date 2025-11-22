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
    @if ! [ -f .env.local ]; then \
        echo "Creating .env.local from template..."; \
        cp .env.template .env.local; \
    fi
    @echo "Creating files directory..."
    @mkdir -p files
    @echo "Downloading audio files..."
    @if [ ! -f files/centre.wav ] || [ ! -f files/stereo.wav ]; then \
        uv run scripts/download_files.py || echo "Note: Download failed. Please manually populate .env.local with URLs and run 'just download'"; \
    else \
        echo "Audio files already exist, skipping download"; \
    fi
    @if command -v apt-get &> /dev/null; then \
        echo "Installing Raspberry Pi dependencies..."; \
        sudo apt-get update; \
        sudo apt-get install -y python3-dev libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libfreetype6-dev libportmidi-dev libjpeg-dev pkg-config alsa-utils; \
    fi
    @echo "✓ Setup complete"

# Download audio files from URLs in .env.local
download:
    @echo "Downloading audio files..."
    uv run scripts/download_files.py
    @echo "✓ Files downloaded"

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

# Show system info and audio devices
info:
    uv run scripts/system_info.py

# Configure audio devices and volume settings
config:
    uv run scripts/configure.py

# Start the audio player
play:
    uv run main.py
