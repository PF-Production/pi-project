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

## License

This project is licensed under the MIT License.