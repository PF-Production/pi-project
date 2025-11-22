# Pi Project

This is a test project designed to run on a Raspberry Pi. The goal is to experiment with Raspberry Pi hardware and software capabilities.

## Features

- Easy setup and deployment
- Modular codebase for quick prototyping
- Compatible with Raspberry Pi OS

## Getting Started

1. Clone this repository.
2. Run `just setup` to install dependencies, create `.env.local`, and download audio files.
3. Populate `.env.local` with your audio file URLs (if not downloaded automatically).
4. Run `just play` to start the audio player on your Raspberry Pi or macOS.

Clone the repository:

```bash
git clone https://github.com/PF-Production/pi-project.git
cd pi-project
```

Install system dependencies and set up the project:

```bash
just setup
```

This command will:

- Install Python dependencies via `uv`
- Install `ruff` for code linting and formatting
- Create `.env.local` from `.env.template` (used for audio file URLs)
- Create a `files/` directory and download audio files from the URLs you provide
- On Raspberry Pi: automatically install system packages (libsdl2, alsa-utils, etc.)
- On macOS: skip system packages (handled by Homebrew)

## Audio Files

The project expects audio files in the `files/` directory:

- `files/centre.wav` – Centre channel audio (both channels contain centre information)
- `files/stereo.wav` – Stereo audio (left and right channels)

**Note:** Despite their names, both files are actually stereo files. The "centre" file carries the same audio in both channels, while the "stereo" file carries independent left and right content.

To download files automatically during setup, populate `.env.local` with URLs:

```bash
WAV_CENTRE_URL=https://example.com/centre.wav
WAV_STEREO_URL=https://example.com/stereo.wav
MP3_CENTRE_URL=https://example.com/centre.mp3
MP3_STEREO_URL=https://example.com/stereo.mp3
```

Then run:

```bash
just download-files
```

## Just Commands

The project uses [just](https://github.com/casey/just) for common tasks:

```bash
just setup    # Install dependencies and system packages (Pi-aware)
just download # Download audio files specified in .env.local
just play     # Run the audio player (uv run main.py)
just check    # Check code formatting and linting with ruff
just clean    # Remove build artifacts, cache files, and virtual environments
just          # List all available commands
```

## Checking audio playback

- Ensure your speakers or headphones are connected to the Raspberry Pi.
- Run command to determine audio device
- Update the `AUDIODEV` variable in the code with the correct `CARD` and `DEVICE` values.

```bash
aplay -l
```

## Quick start (dev and Pi)

These short instructions show how to run the project locally on macOS for development and on a Raspberry Pi with multiple ALSA outputs.

### 1) On macOS (development)

- Install Python dependencies (pygame is used for local playback):

```bash
python3 -m pip install --user pygame
```

- Run the example `main.py` (use the default system audio device):

```bash
python3 main.py
```

- If you call `MP3Player` directly for local testing, pass `audio_device=None` (or omit the argument). Example:

```py
from mp3_player import MP3Player
player = MP3Player("./files/centre.wav", second_path="./files/stereo.wav", volume=0.1, audio_device=None)
player.play_loop()
```

### 2) On Raspberry Pi (two outputs)

- Install ALSA utilities if not already present:

```bash
sudo apt update
sudo apt install -y alsa-utils python3-pip
```

- Find available ALSA devices:

```bash
aplay -l
```

- Update `main.py` (or construct `MP3Player`) to pass a tuple of device names returned by `aplay`.
  Example using two hardware devices `hw:1,0` and `hw:2,0`:

```py
from mp3_player import MP3Player
player = MP3Player("./files/centre.wav", second_path="./files/stereo.wav", audio_device=("hw:1,0","hw:2,0"))
player.play_loop()
```

- Run the script on the Pi:

```bash
python3 main.py
```

You can pass ALSA devices via CLI arguments. Examples:

```bash

# if you use the 'uv' runner
uv run main.py --device1 hw:1,0 --device2 hw:2,0
```

If you omit `--device1`/`--device2` the script will fall back to the default audio path (pygame/local default) or to `AUDIO_DEVICE_1`/`AUDIO_DEVICE_2` environment variables if set.

Notes for Pi:

- The code uses `aplay` subprocess loops to send each file to the specified ALSA device. This avoids initializing SDL/pygame on headless setups and prevents one process from grabbing a hardware device.
- Per-device software volume is not managed by the Python code when using `aplay`. Use `amixer` or system mixer controls to adjust levels.

### ALSA / amixer notes (per-device volume on the Pi)

- The repository now includes best-effort helpers that call `amixer` to set mixer controls on a card derived from strings like `hw:1,0`.
- `amixer` controls operate at the card level and depend on the card's available mixer controls (common names: `Master`, `PCM`, `Digital`, `Speaker`, `Headphone`). The code tries several controls automatically but may fail for uncommon hardware.

Quick checks and example commands:

```bash
# list ALSA devices
aplay -l

# list mixer controls for card 1 (replace with your card index)
amixer -c 1 scontrols

# set card 1 Master control to 60%
amixer -c 1 set Master 60%
```

Runtime volume from Python (examples):

```py
# set main device to 60%
player.set_volume(0.6)

# set second device to 20%
player.set_second_volume(0.2)
```

Notes:

- If `amixer` isn't installed, install `alsa-utils` on the Pi: `sudo apt install alsa-utils`.
- If the automatic control probes fail, use `amixer -c <card> scontrols` to list available controls and pick one to set manually or extend the code to try that control.

### pygame limitations (local dev)

- `pygame` (SDL backend) provides per-sound and per-channel software volume but does not reliably allow routing different streams to different physical hardware devices across platforms.
- For local macOS testing you can set independent software volumes for each track (see runtime examples above), but to route separate streams to distinct hardware outputs you need OS-level routing (ALSA device selection, PulseAudio, JACK) or the ALSA `aplay -D` approach used on the Pi.

## Examples

- Single-output local test (macOS): use `audio_device=None` and pygame.
- Multi-output Pi: pass a tuple `("hw:X,Y","hw:Z,W")` when creating `MP3Player`.
- Both `centre.wav` and `stereo.wav` files are stereo; they contain different channel configurations for testing multi-output routing.

## Troubleshooting

- If audio doesn't play on Pi, confirm `aplay -l` shows the devices and that your device names match the strings passed to `MP3Player`.
- If `aplay` is missing the code will fall back to `pygame` (single output). Install `alsa-utils` to enable Pi mode.
- For permission problems with audio devices, ensure your user is in the `audio` group or run under appropriate privileges.
- Remember to use uv to run scripts that depend on installed packages, not plain python.
