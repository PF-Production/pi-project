import argparse
import os
import socket
import threading
import time
from datetime import datetime

from dotenv import load_dotenv

from mp3_player import MP3Player

# Load environment variables from .env.local if it exists
load_dotenv(".env.local")


class RemoteControl:
    def __init__(self, player, port):
        self.player = player
        self.port = int(port)
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()

    def _run_server(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", self.port))
            server.listen(1)
            print(f"Remote control listening on port {self.port}")

            while self.running:
                try:
                    client, addr = server.accept()
                    self._handle_client(client)
                except Exception as e:
                    print(f"Remote server error: {e}")
                    time.sleep(1)
        except Exception as e:
            print(f"Failed to start remote server: {e}")

    def _handle_client(self, client):
        with client:
            client.settimeout(5.0)
            try:
                while True:
                    data = client.recv(1024)
                    if not data:
                        break
                    command = data.decode("utf-8").strip()
                    if not command:
                        continue
                    response = self._process_command(command)
                    client.sendall((response + "\n").encode("utf-8"))
            except Exception:
                pass

    def _handle_status(self, parts):
        state = "playing" if self.player.is_playing() else "stopped"
        return f"status: {state} vol1={self.player.volume:.2f} vol2={self.player.second_volume:.2f}"

    def _handle_play(self, parts):
        self.player.play_loop()
        return "ok"

    def _handle_stop(self, parts):
        self.player.stop()
        return "ok"

    def _handle_volume(self, parts):
        if len(parts) > 1:
            try:
                vol = float(parts[1])
                self.player.set_volume(vol)
                return f"ok: volume={vol}"
            except ValueError:
                return "error: invalid volume"
        return f"volume: {self.player.volume}"

    def _handle_volume2(self, parts):
        if len(parts) > 1:
            try:
                vol = float(parts[1])
                self.player.set_second_volume(vol)
                return f"ok: volume2={vol}"
            except ValueError:
                return "error: invalid volume"
        return f"volume2: {self.player.second_volume}"

    def _process_command(self, command):
        parts = command.split()
        if not parts:
            return "error: empty command"

        cmd = parts[0].lower()

        handlers = {
            "status": self._handle_status,
            "play": self._handle_play,
            "stop": self._handle_stop,
            "volume": self._handle_volume,
            "volume2": self._handle_volume2,
        }

        handler = handlers.get(cmd)
        if handler:
            return handler(parts)

        return "error: unknown command"


def _parse_schedule_time(label, value):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError:
        print(f"Warning: {label} has invalid format '{value}'. Expected HH:MM.")
        return None


def _get_audio_device(args):
    if args.device1 and args.device2:
        return (args.device1, args.device2)
    elif args.device1:
        return args.device1

    # allow overriding via env vars for systemd or uv run usage
    env1 = os.environ.get("AUDIO_DEVICE_1")
    env2 = os.environ.get("AUDIO_DEVICE_2")
    if env1 and env2:
        return (env1, env2)
    elif env1:
        return env1
    return None


def _get_volumes(args):
    # Load volumes from environment or use defaults
    main_volume = args.volume or float(os.getenv("CENTRE_LEFT_VOLUME", 0.5))
    second_volume = args.second_volume or float(os.getenv("STEREO_LEFT_VOLUME", 0.5))

    return {
        "main": main_volume,
        "second": second_volume,
        "centre_left": float(os.getenv("CENTRE_LEFT_VOLUME", main_volume)),
        "centre_right": float(os.getenv("CENTRE_RIGHT_VOLUME", main_volume)),
        "stereo_left": float(os.getenv("STEREO_LEFT_VOLUME", second_volume)),
        "stereo_right": float(os.getenv("STEREO_RIGHT_VOLUME", second_volume)),
    }


def _setup_remote(player):
    remote_port = os.getenv("REMOTE_PORT")
    if remote_port and int(remote_port) > 0:
        RemoteControl(player, remote_port)


def _handle_scheduling(player, args):
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

    audio_device = _get_audio_device(args)
    volumes = _get_volumes(args)

    player = MP3Player(
        "./files/centre.wav",
        second_path="./files/stereo.wav",
        volume=volumes["main"],
        audio_device=audio_device,
        second_volume=volumes["second"],
        main_left_volume=volumes["centre_left"],
        main_right_volume=volumes["centre_right"],
        second_left_volume=volumes["stereo_left"],
        second_right_volume=volumes["stereo_right"],
    )

    _setup_remote(player)
    _handle_scheduling(player, args)

    # Keep the script alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        player.stop()


if __name__ == "__main__":
    main()
