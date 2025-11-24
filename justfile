#!/usr/bin/env just --justfile

# Default recipe
default:
    @just --list

# Setup the development environment
setup:
    @echo "Setting up development environment..."
    @if ! command -v uv &> /dev/null; then \
        echo "uv not found, installing..."; \
        if command -v apt-get &> /dev/null; then \
            echo "Installing uv via curl (recommended for Raspberry Pi)..."; \
            curl -LsSf https://astral.sh/uv/install.sh | sh; \
            export PATH="$$HOME/.cargo/bin:$$PATH"; \
        else \
            echo "Installing uv via pip..."; \
            python3 -m pip install --upgrade pip; \
            python3 -m pip install uv; \
        fi; \
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

# Start immediately, ignoring schedule
play-now:
    uv run main.py --ignore-schedule

# Connect to the running player remotely
remote host="localhost":
    uv run scripts/remote.py {{host}}

# Enable SSH on Raspberry Pi
enable-ssh:
    @if command -v systemctl &> /dev/null; then \
        echo "Checking if SSH is installed..."; \
        if ! systemctl list-unit-files | grep -q ssh.service; then \
            echo "SSH not found, attempting to install openssh-server..."; \
            if command -v apt-get &> /dev/null; then \
                sudo apt-get update; \
                sudo apt-get install -y openssh-server; \
            else \
                echo "Error: apt-get not found. Cannot install openssh-server."; \
                exit 1; \
            fi; \
        fi; \
        echo "Enabling SSH service..."; \
        sudo systemctl enable ssh; \
        sudo systemctl start ssh; \
        echo "✓ SSH enabled and running"; \
        echo ""; \
        echo "To connect, use one of these:"; \
        echo "  ssh $(whoami)@$(hostname).local"; \
        echo "  or get your IP with: just ip"; \
    else \
        echo "Error: systemctl not found. This doesn't appear to be a Raspberry Pi or Linux system."; \
        exit 1; \
    fi

# Install systemd service to run on boot
install-service:
    @echo "Installing systemd service..."
    @if [ -f systemd/pi-mp3.service ]; then \
        echo "Generating service file with current paths..."; \
        sed "s|User=pi|User=$(whoami)|g" systemd/pi-mp3.service > pi-mp3.service.tmp; \
        sed -i "s|WorkingDirectory=/home/pi/pi-project|WorkingDirectory=$(pwd)|g" pi-mp3.service.tmp; \
        sed -i "s|ExecStart=/usr/bin/env uv|ExecStart=$(which uv)|g" pi-mp3.service.tmp; \
        echo "Installing to /etc/systemd/system/pi-mp3.service..."; \
        sudo mv pi-mp3.service.tmp /etc/systemd/system/pi-mp3.service; \
        sudo systemctl daemon-reload; \
        sudo systemctl enable pi-mp3.service; \
        sudo systemctl start pi-mp3.service; \
        echo "✓ Service installed and started"; \
        echo "Check status with: systemctl status pi-mp3.service"; \
    else \
        echo "Error: systemd/pi-mp3.service not found"; \
    fi

# Show network information (IP address)
ip:
    @echo "Network Interfaces:"
    @if command -v ip &> /dev/null; then \
        ip -4 addr show | grep -v "127.0.0.1" | grep inet; \
    else \
        ifconfig | grep "inet " | grep -v 127.0.0.1; \
    fi
    @echo "\nTo connect via SSH:"
    @echo "  ssh $USER@$(hostname).local"
    @echo "  or"
    @echo "  ssh $USER@<IP_ADDRESS>"
