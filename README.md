# Pi Project

This is a test project designed to run on a Raspberry Pi. The goal is to experiment with Raspberry Pi hardware and software capabilities.

## Features

- Easy setup and deployment
- Modular codebase for quick prototyping
- Compatible with Raspberry Pi OS

## Getting Started

1. Clone this repository.
2. Follow the setup instructions in the documentation.
3. Run the project on your Raspberry Pi.

Clone the repository:

```bash
git clone https://github.com/PF-Production/pi-project.git
```

Install the required dependencies:

```bash
sudo apt-get install -y python3-dev libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libfreetype6-dev libportmidi-dev libjpeg-dev pkg-config
```

Resynchronize the repository and update submodules:

```bash
cd ~/pi-project
git pull
uv sync
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
player = MP3Player("./files/karla bidi - instruments stereo.wav", second_path="./files/Karla Bidi - Mono Vox.wav", volume=0.1, audio_device=None)
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
player = MP3Player("./files/karla bidi - instruments stereo.wav", second_path="./files/Karla Bidi - Mono Vox.wav", audio_device=("hw:1,0","hw:2,0"))
player.play_loop()
```

- Run the script on the Pi:

```bash
python3 main.py
```

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

## Troubleshooting

- If audio doesn't play on Pi, confirm `aplay -l` shows the devices and that your device names match the strings passed to `MP3Player`.
- If `aplay` is missing the code will fall back to `pygame` (single output). Install `alsa-utils` to enable Pi mode.
- For permission problems with audio devices, ensure your user is in the `audio` group or run under appropriate privileges.

## Checklist

- [x] Run locally on macOS using `pygame` (single output)
- [x] Run on Raspberry Pi using `aplay` subprocesses for multiple outputs
- [ ] Optional: per-device volume controls (use `amixer`)


## Checklist

- [ ] Confirm playback through multiple outputs.
- [ ] 3 files required to playback on devices. 2 files are mono and should be played through left and right channels. 1 file is stereo and should be played through both channels.
- [ ] Figure out what the default playback outputs are for Raspberry Pi OS and update code accordingly. Or find a way to set the outputs manually.
- [ ] Write setup scripts for easy installation using `justinstall`
- [ ] Check if on device bootup the application starts automatically
- [ ] Test if start times for script can be set using system clock
- [ ] Add --force flag to bypass time checks for testing purposes
- [ ] Figure out how to remote into device via WiFi for onsite debugging and EQ
- [ ] Onsite controls should only be to force playback, adjust volume or change EQ settings.
- [ ] Test devices locally first to ensure they all playback correctly when powered on.
