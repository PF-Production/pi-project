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


def get_usb_port_for_card(card_num):
    """Get the USB port path for a sound card.

    This returns a stable identifier based on the physical USB port,
    which doesn't change even when identical devices swap detection order.

    Returns something like 'usb1/1-1.2' or None if not a USB device.
    """
    try:
        device_path = Path(f"/sys/class/sound/card{card_num}/device")
        if device_path.exists():
            real_path = device_path.resolve()
            path_str = str(real_path)
            if "/usb" in path_str:
                parts = path_str.split("/")
                for i, part in enumerate(parts):
                    if part.startswith("usb"):
                        usb_parts = []
                        for j in range(i, len(parts)):
                            if parts[j] == "sound":
                                break
                            usb_parts.append(parts[j])
                        if usb_parts:
                            return "/".join(usb_parts)
    except Exception:
        pass
    return None


def get_alsa_devices():
    """Get available ALSA audio devices with USB port paths for stable identification.

    For USB devices, includes the USB port path which is stable across reboots.
    """
    devices = {}
    try:
        result = subprocess.run(
            ["aplay", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("card"):
                    parts = line.split(":")
                    if len(parts) >= 2:
                        card_num = parts[0].split()[1]
                        card_info = parts[1].strip()
                        if " [" in card_info:
                            card_name = card_info.split(" [")[0].strip()
                        else:
                            card_name = card_info.split(",")[0].strip()

                        description = ":".join(parts[1:]).strip()

                        # Get USB port path for stable identification
                        usb_port = get_usb_port_for_card(card_num)

                        if usb_port:
                            stable_id = f"usbport:{usb_port}"
                            port_display = usb_port.split("/")[-1] if "/" in usb_port else usb_port
                            devices[stable_id] = {
                                "description": description,
                                "card_name": card_name,
                                "card_num": card_num,
                                "usb_port": usb_port,
                                "port_display": port_display,
                            }
                        else:
                            stable_id = f"plughw:CARD={card_name},DEV=0"
                            devices[stable_id] = {
                                "description": description,
                                "card_name": card_name,
                                "card_num": card_num,
                                "usb_port": None,
                                "port_display": None,
                            }
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
            "playback_mode": os.getenv("PLAYBACK_MODE", "4ch"),
            "device1": os.getenv("AUDIO_DEVICE_1"),
            "device2": os.getenv("AUDIO_DEVICE_2"),
            "vox_volume": os.getenv("VOX_VOLUME", "0.5"),
            "sub_volume": os.getenv("SUB_VOLUME", "0.5"),
            "surround_left_volume": os.getenv("SURROUND_LEFT_VOLUME", "0.5"),
            "surround_right_volume": os.getenv("SURROUND_RIGHT_VOLUME", "0.5"),
            "sum_left_volume": os.getenv("SUM_LEFT_VOLUME", "0.5"),
            "sum_right_volume": os.getenv("SUM_RIGHT_VOLUME", "0.5"),
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
        mode = config.get("playback_mode", "4ch")
        print(f"\nPlayback Mode: {mode}")

        print("\nDevice Configuration:")
        if mode == "4ch":
            print(f"  Device 1 (Vox+Sub):    {config.get('device1') or '(not set)'}")
            print(f"  Device 2 (Surround):   {config.get('device2') or '(not set)'}")
        else:
            print(f"  Device 1 (Sum):        {config.get('device1') or '(not set)'}")

        print("\nVolume Settings:")
        if mode == "4ch":
            print(f"  Vox (Centre):          {config.get('vox_volume', '(not set)')}")
            print(f"  Sub:                   {config.get('sub_volume', '(not set)')}")
            print(f"  Surround Left:         {config.get('surround_left_volume', '(not set)')}")
            print(f"  Surround Right:        {config.get('surround_right_volume', '(not set)')}")
        else:
            print(f"  Sum Left:              {config.get('sum_left_volume', '(not set)')}")
            print(f"  Sum Right:             {config.get('sum_right_volume', '(not set)')}")

        print("\nSchedule:")
        print(f"  Start time:            {config.get('start_time') or '(not set)'}")
        print(f"  Stop time:             {config.get('end_time') or '(not set)'}")
    else:
        print("\n⊘ No configuration found in .env.local")
        print("   Run 'just configure' to set up audio devices and volumes")

    # Audio files
    print_header("AUDIO FILES")

    audio_files = {
        "Sum (Full Mix)": "./files/sum.wav",
        "Instruments (Surround)": "./files/instruments.wav",
        "Vox+Sub": "./files/vox_sub.wav",
        "Loop Mask": "./files/loop.wav",
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
    """Print ALSA devices for Linux with USB port information."""
    devices = get_alsa_devices()
    if devices:
        print("\nALSA Devices (Linux):")
        print("  Note: USB port identifiers are stable across reboots, even for identical devices.\n")
        for device_id, info in sorted(devices.items()):
            if isinstance(info, dict):
                desc = info.get("description", "Unknown")
                card_name = info.get("card_name", "?")
                card_num = info.get("card_num", "?")
                usb_port = info.get("usb_port")
                if usb_port:
                    port_short = usb_port.split("/")[-1] if "/" in usb_port else usb_port
                    print(f"  hw:{card_num} (CARD={card_name})")
                    print(f"      └─ USB port: {port_short}")
                    print(f"      └─ Stable ID: {device_id}")
                    print(f"      └─ {desc}")
                else:
                    print(f"  hw:{card_num} (CARD={card_name})")
                    print(f"      └─ {desc}")
                print()
            else:
                # Legacy format (string)
                print(f"  {device_id:45} - {info}")
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
