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
