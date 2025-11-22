import argparse
import os
import time
from datetime import datetime

from dotenv import load_dotenv

from mp3_player import MP3Player

# Load environment variables from .env.local if it exists
load_dotenv(".env.local")


def _parse_schedule_time(label, value):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError:
        print(f"Warning: {label} has invalid format '{value}'. Expected HH:MM.")
        return None


def main():
    parser = argparse.ArgumentParser(description="Run MP3Player with optional device args")
    parser.add_argument("--device1", help="ALSA hw device for centre track (e.g. hw:1,0)", default=None)
    parser.add_argument("--device2", help="ALSA hw device for stereo track (e.g. hw:2,0)", default=None)
    parser.add_argument("--volume", type=float, help="Main track volume 0.0-1.0", default=None)
    parser.add_argument("--second-volume", type=float, help="Second track volume 0.0-1.0", default=None)
    parser.add_argument(
        "--ignore-schedule",
        action="store_true",
        help="Start playback immediately, ignoring PLAY_START_TIME/PLAY_END_TIME",
    )
    args = parser.parse_args()

    print("Hello from pi-project!")

    # Determine audio_device value: None (use pygame/default) or tuple/string for ALSA
    audio_device = None
    if args.device1 and args.device2:
        audio_device = (args.device1, args.device2)
    elif args.device1:
        audio_device = args.device1
    else:
        # allow overriding via env vars for systemd or uv run usage
        env1 = os.environ.get("AUDIO_DEVICE_1")
        env2 = os.environ.get("AUDIO_DEVICE_2")
        if env1 and env2:
            audio_device = (env1, env2)
        elif env1:
            audio_device = env1
    # If nothing provided, use None for system defaults (CoreAudio on macOS, pygame otherwise)
    # For Raspberry Pi deployment, set AUDIO_DEVICE_1 and AUDIO_DEVICE_2 in .env.local

    # Load volumes from environment or use defaults
    main_volume = args.volume or float(os.getenv("CENTRE_LEFT_VOLUME", 0.5))
    second_volume = args.second_volume or float(os.getenv("STEREO_LEFT_VOLUME", 0.5))

    # Load per-channel volumes
    centre_left = float(os.getenv("CENTRE_LEFT_VOLUME", main_volume))
    centre_right = float(os.getenv("CENTRE_RIGHT_VOLUME", main_volume))
    stereo_left = float(os.getenv("STEREO_LEFT_VOLUME", second_volume))
    stereo_right = float(os.getenv("STEREO_RIGHT_VOLUME", second_volume))

    player = MP3Player(
        "./files/centre.wav",
        second_path="./files/stereo.wav",
        volume=main_volume,
        audio_device=audio_device,
        second_volume=second_volume,
        main_left_volume=centre_left,
        main_right_volume=centre_right,
        second_left_volume=stereo_left,
        second_right_volume=stereo_right,
    )

    start_time = _parse_schedule_time("PLAY_START_TIME", os.getenv("PLAY_START_TIME"))
    end_time = _parse_schedule_time("PLAY_END_TIME", os.getenv("PLAY_END_TIME"))

    if not args.ignore_schedule and start_time and end_time:
        print(
            "Playback scheduled between "
            f"{start_time.strftime('%H:%M')} and {end_time.strftime('%H:%M')} (device local time)."
        )
        player.play_between_times(start_time, end_time)
    else:
        if not args.ignore_schedule and (start_time or end_time):
            print("Warning: schedule requires both PLAY_START_TIME and PLAY_END_TIME. Starting immediately.")
        elif args.ignore_schedule and (start_time or end_time):
            print("Ignoring configured schedule and starting playback now.")
        player.play_loop()

    # Keep the script alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        player.stop()


if __name__ == "__main__":
    main()
