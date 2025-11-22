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
            # No timeout - let the connection stay open as long as needed
            buffer = ""
            try:
                while True:
                    data = client.recv(1024)
                    if not data:
                        break

                    buffer += data.decode("utf-8")

                    # Process all complete commands (lines ending with \n)
                    while "\n" in buffer:
                        command, buffer = buffer.split("\n", 1)
                        command = command.strip()
                        if not command:
                            continue

                        try:
                            response = self._process_command(command)
                            client.sendall((response + "\n").encode("utf-8"))
                        except Exception as e:
                            error_msg = f"error: command failed: {e}"
                            print(f"Command '{command}' failed: {e}")
                            client.sendall((error_msg + "\n").encode("utf-8"))

            except socket.timeout:
                # This shouldn't happen now, but handle it gracefully just in case
                print("Client connection timed out")
            except Exception as e:
                # Only log if it's not just a normal disconnect
                if "Connection reset" not in str(e) and "Broken pipe" not in str(e):
                    print(f"Client handler error: {e}")
                    import traceback

                    traceback.print_exc()

    def _handle_status(self, parts):
        try:
            state = "playing" if self.player.is_playing() else "stopped"
            centre = getattr(self.player, "main_left_volume", 0.5)
            sub = getattr(self.player, "main_right_volume", 0.5)
            stereo = getattr(self.player, "second_volume", 0.5)
            return f"status: {state} centre={centre:.2f} sub={sub:.2f} stereo={stereo:.2f}"
        except Exception as e:
            return f"error: status failed {e}"

    def _handle_play(self, parts):
        self.player.play_loop()
        return "ok"

    def _handle_stop(self, parts):
        self.player.stop()
        return "ok"

    def _handle_centre(self, parts):
        try:
            if len(parts) > 1:
                vol = float(parts[1])
                if vol < 0.0 or vol > 1.0:
                    return "error: volume must be between 0.0 and 1.0"
                right_vol = getattr(self.player, "main_right_volume", 0.5)
                self.player.set_main_channel_volumes(vol, right_vol)
                return f"ok: centre={vol:.2f}"
            left_vol = getattr(self.player, "main_left_volume", 0.5)
            return f"centre: {left_vol:.2f}"
        except ValueError as e:
            return f"error: invalid volume value: {e}"
        except Exception as e:
            print(f"Unexpected error in _handle_centre: {e}")
            import traceback

            traceback.print_exc()
            return f"error: {e}"

    def _handle_sub(self, parts):
        try:
            if len(parts) > 1:
                vol = float(parts[1])
                if vol < 0.0 or vol > 1.0:
                    return "error: volume must be between 0.0 and 1.0"
                left_vol = getattr(self.player, "main_left_volume", 0.5)
                self.player.set_main_channel_volumes(left_vol, vol)
                return f"ok: sub={vol:.2f}"
            right_vol = getattr(self.player, "main_right_volume", 0.5)
            return f"sub: {right_vol:.2f}"
        except ValueError as e:
            return f"error: invalid volume value: {e}"
        except Exception as e:
            print(f"Unexpected error in _handle_sub: {e}")
            import traceback

            traceback.print_exc()
            return f"error: {e}"

    def _handle_stereo(self, parts):
        try:
            if len(parts) > 1:
                vol = float(parts[1])
                if vol < 0.0 or vol > 1.0:
                    return "error: volume must be between 0.0 and 1.0"
                self.player.set_second_volume(vol)
                return f"ok: stereo={vol:.2f}"
            stereo_vol = getattr(self.player, "second_volume", 0.5)
            return f"stereo: {stereo_vol:.2f}"
        except ValueError as e:
            return f"error: invalid volume value: {e}"
        except Exception as e:
            print(f"Unexpected error in _handle_stereo: {e}")
            import traceback

            traceback.print_exc()
            return f"error: {e}"

    def _handle_save(self, parts):
        try:
            env_path = ".env.local"
            if not os.path.exists(env_path):
                return "error: .env.local not found"

            centre_left = getattr(self.player, "main_left_volume", 0.5)
            centre_right = getattr(self.player, "main_right_volume", 0.5)
            stereo_left = getattr(self.player, "second_left_volume", 0.5)
            stereo_right = getattr(self.player, "second_right_volume", 0.5)

            with open(env_path, "r") as f:
                lines = f.readlines()

            new_lines = []
            updated_keys = set()

            updates = {
                "CENTRE_LEFT_VOLUME": f"{centre_left:.2f}",
                "CENTRE_RIGHT_VOLUME": f"{centre_right:.2f}",
                "STEREO_LEFT_VOLUME": f"{stereo_left:.2f}",
                "STEREO_RIGHT_VOLUME": f"{stereo_right:.2f}",
            }

            for line in lines:
                key_match = False
                for key, val in updates.items():
                    if line.strip().startswith(f"{key}="):
                        new_lines.append(f"{key}={val}\n")
                        updated_keys.add(key)
                        key_match = True
                        break
                if not key_match:
                    new_lines.append(line)

            for key, val in updates.items():
                if key not in updated_keys:
                    new_lines.append(f"{key}={val}\n")

            with open(env_path, "w") as f:
                f.writelines(new_lines)

            return "ok: saved"
        except Exception as e:
            return f"error: save failed: {e}"

    def _process_command(self, command):
        parts = command.split()
        if not parts:
            return "error: empty command"

        cmd = parts[0].lower()

        handlers = {
            "status": self._handle_status,
            "play": self._handle_play,
            "stop": self._handle_stop,
            "centre": self._handle_centre,
            "sub": self._handle_sub,
            "stereo": self._handle_stereo,
            "save": self._handle_save,
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
