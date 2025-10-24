from mp3_player import MP3Player
import time
import argparse
import os


def main():
    parser = argparse.ArgumentParser(
        description="Run MP3Player with optional device args"
    )
    parser.add_argument(
        "--device1", help="ALSA hw device for main track (e.g. hw:1,0)", default=None
    )
    parser.add_argument(
        "--device2", help="ALSA hw device for second track (e.g. hw:2,0)", default=None
    )
    parser.add_argument(
        "--volume", type=float, help="Main track volume 0.0-1.0", default=0.5
    )
    parser.add_argument(
        "--second-volume", type=float, help="Second track volume 0.0-1.0", default=0.5
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
    # If nothing provided, default to cards 2 and 3 (hw:2,0 and hw:3,0)
    if audio_device is None:
        audio_device = (
            os.environ.get("DEFAULT_DEVICE1", "hw:2,0"),
            os.environ.get("DEFAULT_DEVICE2", "hw:3,0"),
        )

    player = MP3Player(
        "./files/Stereo Drums.wav",
        second_path="./files/Vox L - Synth R.wav",
        volume=args.volume,
        audio_device=audio_device,
        second_volume=args.second_volume,
    )

    player.play_loop()

    # Keep the script alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        player.stop()


if __name__ == "__main__":
    main()
