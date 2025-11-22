# Pi Project

A Python audio playback application for Raspberry Pi with multi-device output support. Routes mono (centre) and stereo audio to separate hardware outputs with independent volume control per channel.

## Features

- **Multi-output support**: Route different audio streams to separate ALSA devices on Raspberry Pi
- **Per-channel volume control**: Adjust left/right volumes independently for each output
- **Easy configuration**: Interactive setup wizard to detect and configure audio devices
- **Cross-platform**: Works on Raspberry Pi (ALSA) and macOS (pygame)
- **Simple deployment**: Just one command to set up everything

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/PF-Production/pi-project.git
cd pi-project
just setup
```

The `just setup` command will:

- Install Python dependencies via `uv`
- Install development tools (ruff for linting)
- Create `.env.local` from `.env.template`
- Create `files/` directory and download audio files
- On Raspberry Pi: install system packages (SDL2, ALSA utilities)

### 2. Check Your Audio Devices

```bash
just info
```

This shows available audio devices, the device's current local time, existing configuration, and audio file status.

### 3. Configure Audio Devices

```bash
just config
```

This interactive wizard lets you:

- Select which audio device to use for each output
- Set volume levels for centre sound file `(left - i.e. centre) / right - i.e. sub)`
- Set volume levels for stereo sound file `(left/right)`
- Define daily start/stop times for playback using the Pi's internal clock
- Save configuration to `.env.local`

### 4. Start Playing

```bash
just play
```

The application loads your configuration and starts playback.

## Just Commands

The project uses [just](https://github.com/casey/just) for common tasks:

```bash
just setup     # Install dependencies and system packages
just info      # Show audio devices and current configuration
just config    # Interactive setup wizard for devices and volumes
just play      # Run the audio player. Run `just play:now` to ignore schedule
just download  # Download audio files specified in .env.local
just check     # Check code formatting and linting with ruff
just clean     # Remove build artifacts and cache files
```

---

## Detailed Documentation

### Audio Files

The project expects audio files in the `files/` directory:

- `files/centre.wav` – Centre channel audio (mono content, same in both channels)
- `files/stereo.wav` – Stereo audio (independent left and right channels)

**Note:** Both files are stereo WAV files. The "centre" file contains the same audio in both channels, while the "stereo" file contains independent left and right content.

To download files automatically, populate `.env.local` with URLs:

```bash
WAV_CENTRE_URL=https://example.com/centre.wav
WAV_STEREO_URL=https://example.com/stereo.wav
MP3_CENTRE_URL=https://example.com/centre.mp3
MP3_STEREO_URL=https://example.com/stereo.mp3
```

Then run:

```bash
just download
```

### Configuration Reference

Settings are saved in `.env.local` with the following variables:

```bash
AUDIO_DEVICE_1=hw:0,0           # Main output device (centre channel)
AUDIO_DEVICE_2=hw:1,0           # Secondary output device (stereo channel)
CENTRE_LEFT_VOLUME=0.5          # Centre channel left volume (0.0-1.0)
CENTRE_RIGHT_VOLUME=0.5         # Centre channel right volume (0.0-1.0)
STEREO_LEFT_VOLUME=0.5          # Stereo channel left volume (0.0-1.0)
STEREO_RIGHT_VOLUME=0.5         # Stereo channel right volume (0.0-1.0)
PLAY_START_TIME=08:00           # Optional local start time (HH:MM, 24h)
PLAY_END_TIME=18:00             # Optional local stop time  (HH:MM, 24h)
```

Use `just configure` to set these interactively, or edit `.env.local` directly.

### Playback Schedule

- Scheduling uses the Raspberry Pi's local clock. Run `just info` to confirm the reported time after the device boots.
- Set both `PLAY_START_TIME` and `PLAY_END_TIME` (HH:MM, 24-hour) to delay playback until the start time is reached and stop it automatically at the end time.
- Windows that wrap past midnight (e.g., `21:00` to `05:00`) are supported. If the times match, playback runs continuously.
- Leaving either value blank disables scheduling so the player starts immediately after boot.
- Use `just play:now` (or pass `--ignore-schedule`) to force an immediate manual run without waiting for the next start window.

### Command-Line Arguments

You can also pass device and volume settings via CLI arguments:

```bash
uv run main.py --device1 hw:0,0 --device2 hw:1,0 --volume 0.7 --second-volume 0.5
```

### Development

Using the MP3Player class directly:

```python
from mp3_player import MP3Player

# macOS (development) - uses pygame, default system output
player = MP3Player(
    "./files/centre.wav",
    second_path="./files/stereo.wav",
    volume=0.1,
    audio_device=None
)
player.play_loop()

# Raspberry Pi - send to specific ALSA devices
player = MP3Player(
    "./files/centre.wav",
    second_path="./files/stereo.wav",
    audio_device=("hw:1,0", "hw:2,0"),
    main_left_volume=0.6,
    main_right_volume=0.7,
    second_left_volume=0.5,
    second_right_volume=0.5
)
player.play_loop()
```

### Technical Details

#### On Raspberry Pi

- Uses `aplay` subprocess loops to send each audio stream to its specified ALSA device
- Automatically tries common mixer controls (Master, PCM, Digital, Speaker, Headphone) via `amixer`
- Falls back to pygame if `aplay` is not available
- Avoids initializing SDL/pygame on headless setups

#### On macOS (Development)

- Uses pygame for audio playback through the default system output
- Per-channel volumes are applied via software mixing

#### ALSA Device Selection

Find available devices on Raspberry Pi:

```bash
aplay -l
```

The output shows device names like `hw:0,0`, `hw:1,0`, etc. Use these device IDs with the configuration wizard or pass them directly.

#### Volume Control on Raspberry Pi

The code includes helpers that attempt to set mixer controls via `amixer`. It tries common control names (Master, PCM, Digital, Speaker, Headphone) automatically.

Quick commands:

```bash
# list mixer controls for card 1
amixer -c 1 scontrols

# set card 1 Master control to 60%
amixer -c 1 set Master 60%
```

Runtime volume adjustments:

```python
# set main device to 60%
player.set_volume(0.6)

# set second device to 20%
player.set_second_volume(0.2)

# set independent left/right volumes
player.set_main_channel_volumes(left_volume=0.6, right_volume=0.7)
player.set_second_channel_volumes(left_volume=0.5, right_volume=0.4)
```

### Troubleshooting

- **No audio on Pi**: Confirm `aplay -l` shows devices and device names match what you configured
- **`aplay` not found**: Install `alsa-utils` on the Pi: `sudo apt install alsa-utils`
- **Mixer control fails**: Use `amixer -c <card> scontrols` to see available controls on your hardware
- **Permission issues**: Ensure your user is in the `audio` group: `sudo usermod -aG audio $USER`
- **pygame fallback on Pi**: If ALSA mode doesn't activate, ensure `aplay` is installed and `AUDIO_DEVICE_1`/`AUDIO_DEVICE_2` are set

### Systemd Service Files

The `systemd/` folder contains unit files for running the audio player as a systemd service on Raspberry Pi:

- `pi-mp3.service` – Main service that runs the player
- `pi-mp3-start.timer` – Timer to start the player at a scheduled time
- `pi-mp3-stop.timer` – Timer to stop the player at a scheduled time
- `main-py-*` – Alternative service/timer files for different startup scenarios

**Deployment:**

Copy the desired `.service` and `.timer` files to `/etc/systemd/system/` on the Pi:

```bash
sudo cp systemd/pi-mp3.service /etc/systemd/system/
sudo cp systemd/pi-mp3-start.timer /etc/systemd/system/
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pi-mp3.service
sudo systemctl start pi-mp3.service
```

Check status:

```bash
sudo systemctl status pi-mp3.service
sudo journalctl -u pi-mp3.service -f
```
