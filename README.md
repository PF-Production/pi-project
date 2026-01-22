# Pi Project

A Python audio playback application for Raspberry Pi with multi-device output support. Supports two playback modes with independent volume and EQ control per channel. Playback is looped.

Made to create immersive soundscapes using multiple speakers connected to a single Raspberry Pi.

## Playback Modes

### 4-Channel Mode (default)

Uses 2 stereo audio files routed to 2 separate hardware outputs:

- **vox_sub.wav**: L channel → Vox (centre speaker), R channel → Sub
- **instruments.wav**: L channel → Surround Left, R channel → Surround Right

### 2-Channel Mode

Uses a single stereo file for 1.1 playback with independent left/right volume control:

- **sum.wav**: L channel → Vox (mono/centre), R channel → Sub

## Features

- **Multi-output support**: Route different audio streams to separate ALSA devices on Raspberry Pi
- **2ch/4ch modes**: Switch between 1.1 mix or split 4-channel surround
- **Per-channel volume control**: Adjust Vox (left), Sub (right), and Surround L/R independently
- **Per-channel EQ**: 4-band parametric EQ for vox (left), sub (right), and surround
- **Easy configuration**: Interactive setup wizard to detect and configure audio devices
- **Remote Control**: Control playback, volume, and EQ remotely via TCP
- **Cross-platform**: Works on Raspberry Pi (ALSA) and macOS (pygame)
- **Simple deployment**: Just one command to set up everything

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/PF-Production/pi-project.git
cd pi-project
curl -LsSf https://astral.sh/uv/install.sh | sh
uv run just setup
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
just ip
```

This shows available audio devices, the device's current local time, existing configuration, and audio file status. Run `just ip` to see your Pi's network IP address. Write it down for remote control later.

### 3. Configure Audio Devices

```bash
just config
```

This interactive wizard lets you:

- Select playback mode (2ch or 4ch)
- Select which audio device to use for each output
- Set volume levels for each channel (Vox, Sub, Surround L/R)
- Define daily start/stop times for playback using the Pi's internal clock
- Configure a remote control port
- Save configuration to `.env.local`

### 4. Start Playing

```bash
just play
```

The application loads your configuration and starts playback, looping the audio files to their respective devices. It respects the configured start and stop times. To ignore the schedule and start immediately, run `just play-now`.

### 5. Install as Service (Raspberry Pi)

To run automatically on boot and after power cycles:

```bash
just install-service
```

This command:

- Generates a `pi-mp3.service` file with your current username and working directory
- Installs it to `/etc/systemd/system/`
- Enables the service to start automatically on every boot
- Starts the service immediately

The service will now run on boot and survive power cycles. Each Pi's unique `PLAY_START_TIME` and `PLAY_END_TIME` from `.env.local` control when playback occurs.

**Note:** After updating code (e.g., via `git pull`), restart the service to load changes:

```bash
just restart
```

### 6. Remote Control

Connect to the running player from another terminal:

```bash
# Connect to local player
just remote

# Connect to remote Pi. Try 127.0.0.1 first if on the same machine
just remote <PI_IP_ADDRESS>
```

Once connected, use commands to control playback and volume without needing SSH access.

## Just Commands

The project uses [just](https://github.com/casey/just) for common tasks:

```bash
just setup     # Install dependencies and system packages
just setup-eq  # Install EQ dependencies (scipy/numpy) - macOS only
just info      # Show audio devices and current configuration
just config    # Interactive setup wizard for devices and volumes
just play      # Run the audio player. Run `just play-now` to ignore schedule
just download  # Download audio files specified in .env.local
just refresh   # Redownload audio files, replacing existing ones
just install-service # Install systemd service on Raspberry Pi
just restart   # Restart the service after code changes
just remote    # Connect to running player via TCP
just enable-ssh # Enable SSH on Raspberry Pi
just ip        # Show network IP address
just check     # Check code formatting and linting with ruff
just clean     # Remove build artifacts and cache files
```

---

## Detailed Documentation

### Audio Files

The project expects audio files in the `files/` directory:

- `files/sum.wav` – Full stereo mix (used in 2ch mode)
- `files/instruments.wav` – L-R instruments/surround (used in 4ch mode)
- `files/vox_sub.wav` – L=Vox (centre speaker), R=Sub (used in 4ch mode)

To download files automatically, populate `.env.local` with URLs:

```bash
WAV_SUM_URL=https://example.com/sum.wav
WAV_INSTRUMENTS_URL=https://example.com/instruments.wav
WAV_VOX_SUB_URL=https://example.com/vox_sub.wav
```

Then run:

```bash
just download
```

### Configuration Reference

Settings are saved in `.env.local` with the following variables:

```bash
# Playback mode: "2ch" or "4ch"
PLAYBACK_MODE=4ch

# Use stable device names (recommended) - these don't change on reboot
AUDIO_DEVICE_1=plughw:CARD=Headphones,DEV=0   # Device 1 (vox+sub in both 2ch and 4ch)
AUDIO_DEVICE_2=plughw:CARD=Device,DEV=0       # Device 2 (surround in 4ch mode only)

# Volume settings (0.0 to 1.0)
# VOX and SUB are used in both 2ch and 4ch modes
VOX_VOLUME=0.5              # Vox (left channel) volume
SUB_VOLUME=0.5              # Sub (right channel) volume
SURROUND_LEFT_VOLUME=0.5    # Surround left volume (4ch mode only)
SURROUND_RIGHT_VOLUME=0.5   # Surround right volume (4ch mode only)

# Schedule
PLAY_START_TIME=08:00       # Optional local start time (HH:MM, 24h)
PLAY_END_TIME=18:00         # Optional local stop time  (HH:MM, 24h)
REMOTE_PORT=5000            # TCP port for remote control (0 to disable)
```

Use `just configure` to set these interactively, or edit `.env.local` directly.

### Playback Schedule

- Scheduling uses the Raspberry Pi's local clock. Run `just info` to confirm the reported time after the device boots.
- Set both `PLAY_START_TIME` and `PLAY_END_TIME` (HH:MM, 24-hour) to delay playback until the start time is reached and stop it automatically at the end time.
- Windows that wrap past midnight (e.g., `21:00` to `05:00`) are supported. If the times match, playback runs continuously.
- Leaving either value blank disables scheduling so the player starts immediately after boot.
- Use `just play-now` (or pass `--ignore-schedule`) to force an immediate manual run without waiting for the next start window.

### Command-Line Arguments

You can also pass device and mode settings via CLI arguments:

```bash
# 4ch mode with specific devices
uv run main.py --mode 4ch --device1 "plughw:CARD=Headphones,DEV=0" --device2 "plughw:CARD=Device,DEV=0"

# 2ch mode
uv run main.py --mode 2ch --device1 "plughw:CARD=Headphones,DEV=0"

# Ignore schedule and start immediately
uv run main.py --ignore-schedule
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

The output shows device cards with both names and numbers:

```bash
card 0: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones]
card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]
```

**Use stable device names** to avoid issues when card numbers change on reboot:

- `plughw:CARD=Headphones,DEV=0` instead of `hw:0,0`
- `plughw:CARD=Device,DEV=0` instead of `hw:1,0`

The configuration wizard (`just config`) automatically uses the stable format.

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
# set vox (left channel) volume - works in both 2ch and 4ch modes
player.set_vox_volume(0.6)

# set sub (right channel) volume - works in both 2ch and 4ch modes
player.set_sub_volume(0.5)

# set surround volumes (4ch mode only)
player.set_surround_volumes(left_volume=0.5, right_volume=0.5)
```

### Remote Control

Use the remote client to control playback without SSH:

```bash
# From another terminal on the same network
just remote <PI_IP_ADDRESS>
```

Once connected, you can:

- `status` – Check if playing, mode, current volumes, and schedule
- `play` – Start playback immediately
- `stop` – Stop playback immediately
- `vox <0-1>` – Set vox (left channel) volume
- `sub <0-1>` – Set sub (right channel) volume
- `surround <0-1>` – Set surround volume (both L/R, 4ch mode only)
- `time` – Show current schedule times
- `time start <HH:MM>` – Set start time (24h format)
- `time stop <HH:MM>` – Set stop time (24h format)
- `time clear` – Clear schedule (play immediately on boot)
- `eq` – Show all EQ settings
- `eq vox|sub|surround` – Show EQ for specific track
- `eq <track> <band> freq|gain|width <value>` – Set EQ parameter
- `eq apply` – Apply EQ changes
- `save` – Save current settings to .env.local
- `reboot` – Reboot the Raspberry Pi

Schedule interaction:

- If scheduling is configured, the player auto-starts once per playback window (including on boot if already inside the window).
- If you send `stop` during an active window, playback stops and will not auto-restart until the next window/day.
- Sending `play` always starts playback immediately. If sent during an active window, playback will stop at the end of that window.

### Checking Logs

View service status and logs:

```bash
sudo systemctl status pi-mp3.service
sudo journalctl -u pi-mp3.service -f  # Follow logs in real-time
```

### SSH Access

Enable SSH on your Pi for full remote management:

```bash
just enable-ssh
just ip  # Shows your Pi's IP address
```

Then SSH in from another machine:

```bash
ssh pi@<IP_ADDRESS>
```

## Deployment to Multiple Raspberry Pi Devices

To deploy to Pis with different configurations:

1. **On each Pi**, clone and setup:

   ```bash
   git clone https://github.com/PF-Production/pi-project.git
   cd pi-project
   just setup
   ```

2. **Configure each Pi uniquely:**

   ```bash
   just config
   ```

   Set different `PLAY_START_TIME` and `PLAY_END_TIME` for each device.

3. **Install as service:**

   ```bash
   just install-service
   ```

4. **Verify it's running:**

   ```bash
   systemctl status pi-mp3.service
   ```

Each Pi will now run independently with its own schedule and settings. The service persists across power cycles and reboots.

---

## Remote Access & Management

Once deployed, you can manage your Pis remotely from your laptop on the same WiFi network.

### Quick Remote Control (No SSH)

The easiest way to control playback remotely:

1. **On your laptop**, find the Pi's IP address:

   ```bash
   # On the Pi
   just ip
   ```

2. **From your laptop**, connect to the remote player:

   ```bash
   just remote <PI_IP_ADDRESS>
   ```

   Example: `just remote 192.168.1.42`

3. **Once connected**, use the interactive interface:

   ```bash
   > status
   status: playing centre=0.50 sub=0.50 stereo=0.50
   > centre 0.8
   ok: centre=0.8
   > save
   ok: saved
   > stop
   ok
   > exit
   ```

This works from anywhere on your WiFi network without needing SSH or terminal access to the Pi.

### Full Remote SSH Access

For complete control and troubleshooting:

1. **Enable SSH on the Pi** (run once):

   ```bash
   just enable-ssh
   ```

2. **Find the Pi's hostname and IP**:

   ```bash
   # On the Pi
   just ip
   ```

3. **From your laptop**, SSH in:

   ```bash
   ssh pi@<PI_IP_ADDRESS>
   # or use the hostname
   ssh pi@raspberrypi.local
   ```

4. **Once logged in**, you have full access:

   ```bash
   # Check service status
   systemctl status pi-mp3.service
   
   # View live logs
   sudo journalctl -u pi-mp3.service -f
   
   # Reconfigure settings
   just config
   
   # Restart the service
   sudo systemctl restart pi-mp3.service
   ```

### Troubleshooting Remote Connection

If `just remote <IP>` fails:

1. **Verify the Pi is on the network**:

   ```bash
   ping <PI_IP_ADDRESS>
   ```

2. **Check if remote port is enabled** on the Pi:

   ```bash
   # SSH into the Pi and check
   ssh pi@<PI_IP_ADDRESS>
   grep REMOTE_PORT .env.local
   ```

   If it shows `0`, run `just config` to set a port (e.g., 5000).

3. **Check if the service is running**:

   ```bash
   ssh pi@<PI_IP_ADDRESS>
   systemctl status pi-mp3.service
   ```

4. **Restart the service**:

   ```bash
   ssh pi@<PI_IP_ADDRESS>
   sudo systemctl restart pi-mp3.service
   ```
