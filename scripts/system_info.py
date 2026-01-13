#!/usr/bin/env python3
"""
Display system information including audio devices, sample rates, and current configuration.
"""

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv(".env.local")


def get_alsa_devices():
    """Get available ALSA audio devices with stable names.

    Returns devices using 'plughw:CARD=<name>' format which is stable across reboots,
    unlike 'hw:X,Y' format where card numbers can change.
    """
    devices = {}
    try:
        # Use aplay to list devices
        result = subprocess.run(
            ["aplay", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("card"):
                    # Parse lines like:
                    # "card 0: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones]"
                    # "card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]"
                    parts = line.split(":")
                    if len(parts) >= 2:
                        card_num = parts[0].split()[1]
                        # Extract card name from the bracket after colon
                        card_info = parts[1].strip()
                        if " [" in card_info:
                            card_name = card_info.split(" [")[0].strip()
                        else:
                            card_name = card_info.split(",")[0].strip()

                        # Use plughw:CARD=<name> for stable device identification
                        stable_id = f"plughw:CARD={card_name},DEV=0"
                        description = ":".join(parts[1:]).strip()

                        devices[stable_id] = f"{description} (hw:{card_num},0)"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return devices


def get_pulse_audio_devices():
    """Get PulseAudio devices if available."""
    devices = {}
    try:
        result = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        device_id = parts[0]
                        name = " ".join(parts[1:])
                        devices[f"pulse:{device_id}"] = name
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return devices


def get_coreaudio_devices():
    """Get CoreAudio devices on macOS."""
    devices = {}
    try:
        result = subprocess.run(
            ["system_profiler", "SPAudioDataType"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            current_device = None
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.endswith(":") and not line.startswith("_"):
                    # This looks like a device name
                    current_device = line.rstrip(":")
                    devices[f"coreaudio:{current_device}"] = current_device
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return devices


def get_current_config():
    """Load current configuration from .env.local if it exists."""
    config = {}
    env_file = Path(".env.local")
    if env_file.exists():
        load_dotenv(".env.local")
        config = {
            "device1": os.getenv("AUDIO_DEVICE_1"),
            "device2": os.getenv("AUDIO_DEVICE_2"),
            "centre_left_volume": os.getenv("CENTRE_LEFT_VOLUME", "0.5"),
            "centre_right_volume": os.getenv("CENTRE_RIGHT_VOLUME", "0.5"),
            "stereo_left_volume": os.getenv("STEREO_LEFT_VOLUME", "0.5"),
            "stereo_right_volume": os.getenv("STEREO_RIGHT_VOLUME", "0.5"),
            "start_time": os.getenv("PLAY_START_TIME"),
            "end_time": os.getenv("PLAY_END_TIME"),
        }
    return config


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def main():
    print_header("SYSTEM INFORMATION")

    # Basic system info
    print(f"\nOS: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    print(f"Architecture: {platform.machine()}")
    now = datetime.now().astimezone()
    print(f"Current device time: {now.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}")

    # Audio devices
    print_audio_devices_section()

    # Current configuration
    print_header("CURRENT CONFIGURATION")

    config = get_current_config()

    if config and any(config.values()):
        print("\nDevice Configuration:")
        print(f"  Device 1 (C+Sub): {config.get('device1', '(not set)')}")
        print(f"  Device 2 (Stereo): {config.get('device2', '(not set)')}")

        print("\nVolume Settings:")
        print(f"  Centre Left (C):      {config.get('centre_left_volume', '(not set)')}")
        print(f"  Centre Right (Sub):   {config.get('centre_right_volume', '(not set)')}")
        print(f"  Stereo Left:          {config.get('stereo_left_volume', '(not set)')}")
        print(f"  Stereo Right:         {config.get('stereo_right_volume', '(not set)')}")

        print("\nSchedule:")
        print(f"  Start time:           {config.get('start_time') or '(not set)'}")
        print(f"  Stop time:            {config.get('end_time') or '(not set)'}")
    else:
        print("\n⊘ No configuration found in .env.local")
        print("   Run 'just configure' to set up audio devices and volumes")

    # Audio files
    print_header("AUDIO FILES")

    audio_files = {
        "Centre": "./files/centre.wav",
        "Stereo": "./files/stereo.wav",
    }

    for name, path in audio_files.items():
        if Path(path).exists():
            size_mb = Path(path).stat().st_size / (1024 * 1024)
            print(f"  ✓ {name:10} - {path} ({size_mb:.2f} MB)")
        else:
            print(f"  ✗ {name:10} - {path} (missing)")

    print("\n")


def print_coreaudio_devices_section():
    """Print CoreAudio devices for macOS."""
    devices = get_coreaudio_devices()
    if devices:
        print("\nCoreAudio Devices (macOS):")
        for device_id, name in sorted(devices.items()):
            print(f"  {device_id:20} - {name}")
    else:
        print("\n⊘ No CoreAudio devices found (expected on non-macOS systems)")
    return devices


def print_alsa_devices_section():
    """Print ALSA devices for Linux."""
    devices = get_alsa_devices()
    if devices:
        print("\nALSA Devices (Linux):")
        for device_id, name in sorted(devices.items()):
            print(f"  {device_id:15} - {name}")
    else:
        print("\n⊘ No ALSA devices found (expected on non-Linux systems)")
    return devices


def print_pulseaudio_devices_section():
    """Print PulseAudio devices for Linux."""
    devices = get_pulse_audio_devices()
    if devices:
        print("\nPulseAudio Devices (Linux):")
        for device_id, name in sorted(devices.items()):
            print(f"  {device_id:15} - {name}")
    else:
        print("⊘ No PulseAudio devices found (expected on non-Linux systems)")
    return devices


def print_audio_devices_section():
    """Print audio devices detected on this system."""
    print_header("AUDIO DEVICES")

    alsa = print_alsa_devices_section()
    pulse = print_pulseaudio_devices_section()
    core = print_coreaudio_devices_section()

    if not alsa and not pulse and not core:
        print("\n⊘ No audio devices found. Check your audio configuration.")
        print("   - On Linux: Ensure ALSA/PulseAudio is installed")
        print("   - On macOS: CoreAudio should be available by default")


if __name__ == "__main__":
    main()
