# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Raspberry Pi audio playback application designed for immersive soundscapes using multiple speakers. Supports 2-channel (1.1 mix) and 4-channel (surround) playback modes with independent per-channel volume and 4-band parametric EQ.

## Build & Development Commands

Uses [uv](https://github.com/astral-sh/uv) for Python package management and [just](https://github.com/casey/just) as a task runner.

```bash
just setup          # Install all dependencies (creates .env.local, downloads audio files)
just setup-eq       # Install scipy/numpy for EQ on macOS (Pi uses apt packages)
just check          # Format and lint with ruff
just play           # Run the player (respects schedule in .env.local)
just play-now       # Run immediately, ignoring schedule
just config         # Interactive configuration wizard
just info           # Show audio devices and current config
just remote [host]  # Connect to running player via TCP
just restart        # Restart systemd service after code changes
```

## Architecture

### Core Modules

- **`main.py`** - Entry point, CLI argument parsing, and `RemoteControl` TCP server for runtime control
- **`mp3_player.py`** - `MP3Player` class handling dual-mode playback:
  - Linux/Pi: `aplay` subprocesses to route audio to specific ALSA devices
  - macOS: pygame mixer fallback for development
  - Manages scheduling, loop mask track timing, and per-channel volume/EQ
- **`eq_processor.py`** - `EQProcessor` with 4-band parametric EQ using scipy biquad filters. Processes WAV files in-memory via temp files

### Scripts (`scripts/`)

- `configure.py` - Interactive setup wizard, writes to `.env.local`
- `remote.py` - TCP client for remote control commands
- `download_files.py` - Downloads audio files from URLs in `.env.local`
- `system_info.py` - Displays audio devices, config status, network info

### Configuration

All runtime config lives in `.env.local` (created from `.env.template`). Key settings:
- `PLAYBACK_MODE` - "2ch" or "4ch"
- `AUDIO_DEVICE_1/2` - ALSA device strings (use stable `plughw:CARD=<name>,DEV=0` format)
- `VOX_VOLUME`, `SUB_VOLUME`, `SURROUND_LEFT/RIGHT_VOLUME` - Per-channel volumes (0.0-1.0)
- `PLAY_START_TIME`, `PLAY_END_TIME` - Schedule in 24h HH:MM format
- `EQ_<VOX|SUB|SURROUND>_BAND<1-4>_<FREQ|GAIN|WIDTH>` - Parametric EQ settings

### Audio File Conventions

Files in `files/` directory:
- `sum.wav` - Stereo 1.1 mix for 2ch mode (L=vox/mono, R=sub)
- `vox_sub.wav` - Stereo for 4ch mode (L=vox/centre, R=sub)
- `instruments.wav` - Stereo surround for 4ch mode (L=surround L, R=surround R)
- `loop.wav` - Optional loop mask track to smooth loop transitions

### Playback Modes

**2ch mode**: Single stereo output from `sum.wav` with independent L/R (vox/sub) volume control

**4ch mode**: Two stereo outputs:
- Device 1: `vox_sub.wav` → vox (L) + sub (R)
- Device 2: `instruments.wav` → surround L + surround R

### Remote Control Protocol

TCP server on `REMOTE_PORT`. Commands include: `status`, `play`, `stop`, `vox <0-1>`, `sub <0-1>`, `surround <0-1>`, `eq <track> <band> <param> <value>`, `eq apply`, `save`, `reboot`

## Deployment

For Raspberry Pi production deployment:
```bash
just install-service  # Generates and installs systemd service
just restart          # After code updates via git pull
```

Service logs: `sudo journalctl -u pi-mp3.service -f`
