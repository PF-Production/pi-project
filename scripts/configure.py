#!/usr/bin/env python3
"""
Interactive configuration tool to set up audio devices, volumes, and playback schedule.
Saves configuration to .env.local
"""

import subprocess
from datetime import datetime
from pathlib import Path


def get_usb_port_for_card(card_num):
    """Get the USB port path for a sound card.

    This returns a stable identifier based on the physical USB port,
    which doesn't change even when identical devices swap detection order.

    Returns something like 'usb-0000:01:00.0-1.2' or None if not a USB device.
    """
    try:
        # The device path symlink reveals the USB topology
        device_path = Path(f"/sys/class/sound/card{card_num}/device")
        if device_path.exists():
            # Resolve the symlink to get the full path
            real_path = device_path.resolve()
            # Extract USB port info from path like:
            # /sys/devices/platform/soc/3f980000.usb/usb1/1-1/1-1.2/1-1.2:1.0/sound/card1
            path_str = str(real_path)
            if "/usb" in path_str:
                # Find the USB port portion (e.g., "1-1.2" from the path)
                parts = path_str.split("/")
                for i, part in enumerate(parts):
                    if part.startswith("usb"):
                        # The next parts contain the port topology
                        # e.g., usb1/1-1/1-1.2/1-1.2:1.0
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

    For USB devices, returns the USB port path which is stable across reboots
    even for identical devices. Falls back to card name for non-USB devices.

    Returns dict: {device_id: (description, usb_port_or_none, card_name)}
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
                    # Parse lines like:
                    # "card 0: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones]"
                    # "card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]"
                    parts = line.split(":")
                    if len(parts) >= 2:
                        card_num = parts[0].split()[1]
                        # Extract card name from the bracket after colon
                        # e.g., "Headphones [bcm2835 Headphones]" -> "Headphones"
                        card_info = parts[1].strip()
                        if " [" in card_info:
                            card_name = card_info.split(" [")[0].strip()
                        else:
                            card_name = card_info.split(",")[0].strip()

                        description = ":".join(parts[1:]).strip()

                        # Get USB port path for stable identification
                        usb_port = get_usb_port_for_card(card_num)

                        if usb_port:
                            # For USB devices, use port path as the stable ID
                            # This survives identical devices swapping detection order
                            stable_id = f"usbport:{usb_port}"
                            port_display = usb_port.split("/")[-1] if "/" in usb_port else usb_port
                            devices[stable_id] = (
                                f"{description} [USB port: {port_display}]",
                                usb_port,
                                card_name,
                            )
                        else:
                            # For non-USB devices, use card name (original behavior)
                            stable_id = f"plughw:CARD={card_name},DEV=0"
                            devices[stable_id] = (description, None, card_name)
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


def get_time_input(prompt, default=None):
    """Get HH:MM (24h) time input from user.

    Returns tuple (value, was_provided). Value is a string like "08:30" or None.
    """

    def _validate(value):
        datetime.strptime(value, "%H:%M")

    while True:
        default_display = default if default is not None else "HH:MM"
        user_input = input(f"{prompt} [{default_display}]: ").strip()
        if not user_input:
            return (default, False)
        try:
            _validate(user_input)
            return (user_input, True)
        except ValueError:
            print("  ✗ Time must be in 24-hour HH:MM format (e.g., 08:00 or 18:30)")


def select_device(devices, device_name, current_device=None):
    """Prompt user to select a device from available options.

    For USB devices identified by port path, the device_id will be like 'usbport:usb1/1-1.2'.
    For non-USB devices, device_id is the traditional 'plughw:CARD=...' format.
    """
    if not devices:
        print(f"\n✗ No audio devices found for {device_name} device")
        custom = input("Enter custom device string (or press Enter to skip): ").strip()
        return custom if custom else None

    print(f"\nAvailable devices for {device_name}:")
    sorted_devices = sorted(devices.items())
    for i, (device_id, info) in enumerate(sorted_devices, 1):
        # info can be a tuple (description, usb_port, card_name) for ALSA devices
        # or a string for PulseAudio/CoreAudio devices
        if isinstance(info, tuple):
            description = info[0]
        else:
            description = info
        marker = " ← current" if device_id == current_device else ""
        # Truncate device_id for display if it's long
        display_id = device_id[:40] + "..." if len(device_id) > 43 else device_id
        print(f"  {i}. {display_id:45} - {description}{marker}")

    print(f"  {len(sorted_devices) + 1}. Enter custom device string")
    print(f"  {len(sorted_devices) + 2}. Skip {device_name} device")

    while True:
        try:
            choice = input(f"\nSelect option (1-{len(sorted_devices) + 2}): ").strip()
            choice_num = int(choice)

            if 1 <= choice_num <= len(sorted_devices):
                return sorted_devices[choice_num - 1][0]
            elif choice_num == len(sorted_devices) + 1:
                custom = input(
                    "Enter device string (e.g., plughw:CARD=Headphones,DEV=0 or usbport:usb1/1-1.2): "
                ).strip()
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

    updated_keys = set()

    for line in lines:
        # Check if this line is a variable we're updating
        updated = False
        for key, value in config.items():
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                updated = True
                updated_keys.add(key)
                break

        if not updated:
            # Keep the line as-is (preserves comments and empty lines)
            new_lines.append(line)

    # Append any new keys that were not found in the original file
    for key, value in config.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    # Write back to .env.local
    with open(env_file, "w") as f:
        f.write("\n".join(new_lines))


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


# ruff: noqa: C901
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
    current_mode = get_env_value("PLAYBACK_MODE", "4ch")
    current_device1 = get_env_value("AUDIO_DEVICE_1")
    current_device2 = get_env_value("AUDIO_DEVICE_2")
    current_vox = float(get_env_value("VOX_VOLUME", "0.5"))
    current_sub = float(get_env_value("SUB_VOLUME", "0.5"))
    current_surround_left = float(get_env_value("SURROUND_LEFT_VOLUME", "0.5"))
    current_surround_right = float(get_env_value("SURROUND_RIGHT_VOLUME", "0.5"))
    current_start_time = get_env_value("PLAY_START_TIME")
    current_end_time = get_env_value("PLAY_END_TIME")

    # Playback Mode selection
    print_header("PLAYBACK MODE")
    print("\n  2ch: 1.1 mix to single output (L=Vox/mono, R=Sub)")
    print("  4ch: Vox+Sub to device 1, Surround L+R to device 2")
    mode_input = input(f"\n  Select mode (2ch/4ch) [{current_mode}]: ").strip().lower()
    playback_mode = mode_input if mode_input in ("2ch", "4ch") else current_mode

    # Device selection
    print_header("DEVICE SELECTION")

    if playback_mode == "4ch":
        device1 = select_device(all_devices, "Vox+Sub", current_device1)
        device2 = select_device(all_devices, "Surround", current_device2)
    else:
        device1 = select_device(all_devices, "Vox+Sub (1.1 mix)", current_device1)
        device2 = None

    # Volume configuration
    print_header("VOLUME CONFIGURATION")

    # Vox and Sub are used in both 2ch and 4ch modes
    print("\nVox/Sub Volumes (used in both 2ch and 4ch modes):")
    vox, vox_provided = get_volume_input("  Vox (Left channel) volume (0.0-1.0):", current_vox)
    sub, sub_provided = get_volume_input("  Sub (Right channel) volume (0.0-1.0):", current_sub)

    if playback_mode == "4ch":
        print("\n4ch Mode - Surround Volumes:")
        surround_left, surround_left_provided = get_volume_input(
            "  Surround Left volume (0.0-1.0):", current_surround_left
        )
        surround_right, surround_right_provided = get_volume_input(
            "  Surround Right volume (0.0-1.0):", current_surround_right
        )
    else:
        surround_left_provided = False
        surround_right_provided = False
        surround_left = current_surround_left
        surround_right = current_surround_right

    # Schedule configuration
    print_header("PLAYBACK SCHEDULE")
    print("\nTimes use the Raspberry Pi's local clock in 24-hour format.")
    start_time, start_time_provided = get_time_input("  Start time (HH:MM):", current_start_time)
    end_time, end_time_provided = get_time_input("  Stop time  (HH:MM):", current_end_time)

    # Remote Control configuration
    print_header("REMOTE CONTROL")
    print("\nConfigure a port for remote control (0 to disable).")
    current_remote_port = get_env_value("REMOTE_PORT", "0")
    remote_port_input = input(f"  Remote Control Port [{current_remote_port}]: ").strip()
    remote_port = remote_port_input if remote_port_input else current_remote_port

    # Summary and confirmation
    print_header("CONFIGURATION SUMMARY")

    print(f"\nPlayback Mode: {playback_mode}")

    print("\nDevice Configuration:")
    if playback_mode == "4ch":
        print(f"  Device 1 (Vox+Sub):    {device1 or '(not set)'}")
        print(f"  Device 2 (Surround):   {device2 or '(not set)'}")
    else:
        print(f"  Device 1 (Vox+Sub):    {device1 or '(not set)'}")

    print("\nVolume Settings:")
    print(f"  Vox (Left):            {vox:.1f}")
    print(f"  Sub (Right):           {sub:.1f}")
    if playback_mode == "4ch":
        print(f"  Surround Left:         {surround_left:.1f}")
        print(f"  Surround Right:        {surround_right:.1f}")

    print("\nSchedule:")
    print(f"  Start time:            {start_time or '(not set)'}")
    print(f"  Stop time:             {end_time or '(not set)'}")

    print("\nRemote Control:")
    print(f"  Port:                  {remote_port}")

    confirm = input("\nSave this configuration to .env.local? (y/n): ").strip().lower()

    if confirm == "y":
        config = {"PLAYBACK_MODE": playback_mode}

        # Only include device settings if user provided them
        if device1 is not None:
            config["AUDIO_DEVICE_1"] = device1
        if device2 is not None:
            config["AUDIO_DEVICE_2"] = device2

        # Volume settings - vox/sub used in both modes
        if vox_provided:
            config["VOX_VOLUME"] = str(vox)
        if sub_provided:
            config["SUB_VOLUME"] = str(sub)
        if surround_left_provided:
            config["SURROUND_LEFT_VOLUME"] = str(surround_left)
        if surround_right_provided:
            config["SURROUND_RIGHT_VOLUME"] = str(surround_right)

        if start_time_provided and start_time:
            config["PLAY_START_TIME"] = start_time
        if end_time_provided and end_time:
            config["PLAY_END_TIME"] = end_time

        # Always save remote port if it's set
        if remote_port:
            config["REMOTE_PORT"] = remote_port

        save_env_file(config)
        print("\n✓ Configuration saved to .env.local")
    else:
        print("\n✗ Configuration not saved")


if __name__ == "__main__":
    main()
