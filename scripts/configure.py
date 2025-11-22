#!/usr/bin/env python3
"""
Interactive configuration tool to set up audio devices and volume levels.
Saves configuration to .env.local
"""

import subprocess
from pathlib import Path


def get_alsa_devices():
    """Get available ALSA audio devices."""
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
                    if len(parts) >= 3:
                        card_num = parts[0].split()[1]
                        name = ":".join(parts[1:]).strip()
                        devices[f"hw:{card_num},0"] = name
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
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.endswith(":") and not line.startswith("_"):
                    # This looks like a device name
                    current_device = line.rstrip(":")
                    devices[f"coreaudio:{current_device}"] = current_device
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return devices


def get_env_value(key, default=None):
    """Read a specific value from .env.local file.
    Direct file parsing to ensure we get the current value,
    not a cached environment variable.
    """
    env_file = Path(".env.local")
    if not env_file.exists():
        return default

    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1]
    except Exception:
        pass

    return default


def get_volume_input(prompt, default=0.5):
    """Get volume input from user (0.0 to 1.0).

    Returns a tuple: (value, was_provided)
    was_provided is False if user just pressed Enter to skip.
    """
    while True:
        try:
            user_input = input(f"{prompt} [{default}]: ").strip()
            if not user_input:
                # User pressed Enter without input - skip/don't update
                return (default, False)
            vol = float(user_input)
            if 0.0 <= vol <= 1.0:
                return (vol, True)
            else:
                print("  ✗ Volume must be between 0.0 and 1.0")
        except ValueError:
            print("  ✗ Invalid input. Please enter a number between 0.0 and 1.0")


def select_device(devices, device_num, current_device=None):
    """Prompt user to select a device from available options."""
    if not devices:
        print(f"\n✗ No audio devices found for device {device_num}")
        custom = input("Enter custom device string (or press Enter to skip): ").strip()
        return custom if custom else None

    print(f"\nAvailable devices for device {device_num}:")
    sorted_devices = sorted(devices.items())
    for i, (device_id, name) in enumerate(sorted_devices, 1):
        marker = " ← current" if device_id == current_device else ""
        print(f"  {i}. {device_id:15} - {name}{marker}")

    print(f"  {len(sorted_devices) + 1}. Enter custom device string")
    print(f"  {len(sorted_devices) + 2}. Skip / Remove device {device_num}")

    while True:
        try:
            choice = input(f"\nSelect option (1-{len(sorted_devices) + 2}): ").strip()
            choice_num = int(choice)

            if 1 <= choice_num <= len(sorted_devices):
                return sorted_devices[choice_num - 1][0]
            elif choice_num == len(sorted_devices) + 1:
                custom = input("Enter device string (e.g., hw:1,0 or pulse:0): ").strip()
                return custom if custom else None
            elif choice_num == len(sorted_devices) + 2:
                return None
            else:
                print("  ✗ Invalid choice")
        except ValueError:
            print("  ✗ Invalid input. Please enter a number")


def save_env_file(config):
    """Save configuration to .env.local by updating only the specified variables.

    Preserves comments and formatting from the template.
    Only updates variables that are in config dict (skipped values are not included).
    """
    env_file = Path(".env.local")
    template_file = Path(".env.template")

    # Read the existing file or template
    if env_file.exists():
        content = env_file.read_text()
    elif template_file.exists():
        content = template_file.read_text()
    else:
        # Fallback: create minimal file
        content = ""

    # Update only the variables we're configuring
    lines = content.split("\n")
    new_lines = []

    for line in lines:
        # Check if this line is a variable we're updating
        updated = False
        for key, value in config.items():
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                updated = True
                break

        if not updated:
            # Keep the line as-is (preserves comments and empty lines)
            new_lines.append(line)

    # Write back to .env.local
    with open(env_file, "w") as f:
        f.write("\n".join(new_lines))


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def main():
    print_header("AUDIO DEVICE & VOLUME CONFIGURATION")

    # Get available devices
    alsa_devices = get_alsa_devices()
    pulse_devices = get_pulse_audio_devices()
    coreaudio_devices = get_coreaudio_devices()
    all_devices = {**alsa_devices, **pulse_devices, **coreaudio_devices}

    if not all_devices:
        print("\n⊘ Warning: No audio devices detected")
        print("  You can still enter custom device strings manually")

    # Get current configuration - read directly from file to ensure fresh values
    current_device1 = get_env_value("AUDIO_DEVICE_1")
    current_device2 = get_env_value("AUDIO_DEVICE_2")
    current_centre_left = float(get_env_value("CENTRE_LEFT_VOLUME", "0.5"))
    current_centre_right = float(get_env_value("CENTRE_RIGHT_VOLUME", "0.5"))
    current_stereo_left = float(get_env_value("STEREO_LEFT_VOLUME", "0.5"))
    current_stereo_right = float(get_env_value("STEREO_RIGHT_VOLUME", "0.5"))

    # Device selection
    print_header("DEVICE SELECTION")

    device1 = select_device(all_devices, 1, current_device1)
    device2 = select_device(all_devices, 2, current_device2)

    # Volume configuration
    print_header("VOLUME CONFIGURATION")

    print("\nCentre Channel (mono)")
    centre_left, centre_left_provided = get_volume_input("  Left volume (0.0-1.0):", current_centre_left)
    centre_right, centre_right_provided = get_volume_input("  Right volume (0.0-1.0):", current_centre_right)

    print("\nStereo Channel")
    stereo_left, stereo_left_provided = get_volume_input("  Left volume (0.0-1.0):", current_stereo_left)
    stereo_right, stereo_right_provided = get_volume_input("  Right volume (0.0-1.0):", current_stereo_right)

    # Summary and confirmation
    print_header("CONFIGURATION SUMMARY")

    print("\nDevice Configuration:")
    print(f"  Device 1 (Main):        {device1 or '(not set)'}")
    print(f"  Device 2 (Secondary):   {device2 or '(not set)'}")

    print("\nVolume Settings:")
    print(f"  Centre Left:    {centre_left:.1f}")
    print(f"  Centre Right:   {centre_right:.1f}")
    print(f"  Stereo Left:    {stereo_left:.1f}")
    print(f"  Stereo Right:   {stereo_right:.1f}")

    confirm = input("\nSave this configuration to .env.local? (y/n): ").strip().lower()

    if confirm == "y":
        config = {}
        # Only include device settings if user provided them
        if device1 is not None:
            config["AUDIO_DEVICE_1"] = device1
        if device2 is not None:
            config["AUDIO_DEVICE_2"] = device2
        # Only include volume settings if user provided them (not skipped)
        if centre_left_provided:
            config["CENTRE_LEFT_VOLUME"] = str(centre_left)
        if centre_right_provided:
            config["CENTRE_RIGHT_VOLUME"] = str(centre_right)
        if stereo_left_provided:
            config["STEREO_LEFT_VOLUME"] = str(stereo_left)
        if stereo_right_provided:
            config["STEREO_RIGHT_VOLUME"] = str(stereo_right)

        save_env_file(config)
        print("\n✓ Configuration saved to .env.local")
    else:
        print("\n✗ Configuration not saved")


if __name__ == "__main__":
    main()
