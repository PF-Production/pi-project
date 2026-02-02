import argparse
import os
import socket
import threading
import time
from datetime import datetime
from pathlib import Path

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
            mode = getattr(self.player, "playback_mode", "4ch")

            # Get schedule times
            start_time = os.getenv("PLAY_START_TIME", "")
            end_time = os.getenv("PLAY_END_TIME", "")
            schedule = f"schedule={start_time}-{end_time}" if start_time and end_time else "schedule=none"

            # Loop mask settings (always show, defaults to on)
            loop_vol = getattr(self.player, "loop_volume", 0.5)
            loop_lead = getattr(self.player, "loop_lead_time", 60)
            loop_info = f"loop={loop_vol:.2f} lead={int(loop_lead)}s"

            # vox and sub are used in both 2ch and 4ch modes
            vox = getattr(self.player, "vox_volume", 0.5)
            sub = getattr(self.player, "sub_volume", 0.5)

            if mode == "2ch":
                return f"status: {state} mode={mode} vox={vox:.2f} sub={sub:.2f} {loop_info} {schedule}"
            else:
                surround_l = getattr(self.player, "surround_left_volume", 0.5)
                surround_r = getattr(self.player, "surround_right_volume", 0.5)
                return (
                    f"status: {state} mode={mode} vox={vox:.2f} sub={sub:.2f} "
                    f"surround_l={surround_l:.2f} surround_r={surround_r:.2f} {loop_info} {schedule}"
                )
        except Exception as e:
            return f"error: status failed {e}"

    def _handle_play(self, parts):
        self.player.play_loop()
        return "ok"

    def _handle_stop(self, parts):
        # Manual stop: keep the process alive for remote control,
        # and (if scheduling is enabled) prevent an immediate auto-restart.
        self.player.stop(manual=True)
        return "ok"

    def _handle_vox(self, parts):
        """Handle vox (centre speaker) volume command."""
        try:
            if len(parts) > 1:
                vol = float(parts[1])
                if vol < 0.0 or vol > 1.0:
                    return "error: volume must be between 0.0 and 1.0"
                self.player.set_vox_volume(vol)
                return f"ok: vox={vol:.2f} (use 'eq apply' to apply)"
            vox_vol = getattr(self.player, "vox_volume", 0.5)
            return f"vox: {vox_vol:.2f}"
        except ValueError as e:
            return f"error: invalid volume value: {e}"
        except Exception as e:
            print(f"Unexpected error in _handle_vox: {e}")
            import traceback

            traceback.print_exc()
            return f"error: {e}"

    def _handle_centre(self, parts):
        """Handle centre command (alias for vox)."""
        return self._handle_vox(parts)

    def _handle_sub(self, parts):
        try:
            if len(parts) > 1:
                vol = float(parts[1])
                if vol < 0.0 or vol > 1.0:
                    return "error: volume must be between 0.0 and 1.0"
                self.player.set_sub_volume(vol)
                return f"ok: sub={vol:.2f} (use 'eq apply' to apply)"
            sub_vol = getattr(self.player, "sub_volume", 0.5)
            return f"sub: {sub_vol:.2f}"
        except ValueError as e:
            return f"error: invalid volume value: {e}"
        except Exception as e:
            print(f"Unexpected error in _handle_sub: {e}")
            import traceback

            traceback.print_exc()
            return f"error: {e}"

    def _handle_surround(self, parts):
        """Handle surround (instruments) volume command."""
        try:
            if len(parts) > 1:
                vol = float(parts[1])
                if vol < 0.0 or vol > 1.0:
                    return "error: volume must be between 0.0 and 1.0"
                self.player.set_surround_volumes(vol, vol)
                return f"ok: surround={vol:.2f}"
            surround_l = getattr(self.player, "surround_left_volume", 0.5)
            surround_r = getattr(self.player, "surround_right_volume", 0.5)
            return f"surround: L={surround_l:.2f} R={surround_r:.2f}"
        except ValueError as e:
            return f"error: invalid volume value: {e}"
        except Exception as e:
            print(f"Unexpected error in _handle_surround: {e}")
            import traceback

            traceback.print_exc()
            return f"error: {e}"

    def _handle_stereo(self, parts):
        """Handle stereo command (alias for surround)."""
        return self._handle_surround(parts)

    def _handle_save(self, parts):
        try:
            from eq_processor import save_eq_to_env_dict

            env_path = ".env.local"
            if not os.path.exists(env_path):
                return "error: .env.local not found"

            mode = getattr(self.player, "playback_mode", "4ch")

            with open(env_path, "r") as f:
                lines = f.readlines()

            new_lines = []
            updated_keys = set()

            # Build updates - vox/sub volumes and EQ are used in both modes
            updates = {
                "VOX_VOLUME": f"{self.player.vox_volume:.2f}",
                "SUB_VOLUME": f"{self.player.sub_volume:.2f}",
                "LOOP_VOLUME": f"{getattr(self.player, 'loop_volume', 0.5):.2f}",
                "LOOP_LEAD_TIME": f"{int(getattr(self.player, 'loop_lead_time', 60))}",
            }
            # vox and sub EQ are used in both 2ch and 4ch modes
            updates.update(save_eq_to_env_dict(self.player.vox_eq, "vox"))
            updates.update(save_eq_to_env_dict(self.player.sub_eq, "sub"))

            if mode == "4ch":
                updates["SURROUND_LEFT_VOLUME"] = f"{self.player.surround_left_volume:.2f}"
                updates["SURROUND_RIGHT_VOLUME"] = f"{self.player.surround_right_volume:.2f}"
                updates.update(save_eq_to_env_dict(self.player.surround_eq, "surround"))

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

    def _handle_eq(self, parts):  # noqa: C901
        """
        Handle EQ commands.
        Syntax:
          eq                           - Show all EQ settings
          eq vox|sub|surround          - Show EQ for specific track
          eq <track> <band>            - Show specific band (1-4)
          eq <track> <band> freq|gain|width <value> - Set parameter
          eq apply                     - Apply changes and restart playback
        """
        try:
            valid_tracks = ("vox", "sub", "surround", "centre", "stereo")

            if len(parts) == 1:
                # Show all EQ settings based on mode
                mode = getattr(self.player, "playback_mode", "4ch")
                vox_eq = self.player.get_all_eq("vox")
                sub_eq = self.player.get_all_eq("sub")
                if mode == "2ch":
                    return f"eq (2ch mode): vox={vox_eq} sub={sub_eq}"
                else:
                    surround_eq = self.player.get_all_eq("surround")
                    return f"eq (4ch mode): vox={vox_eq} sub={sub_eq} surround={surround_eq}"

            track = parts[1].lower()

            if track == "apply":
                self.player.apply_eq()
                return "ok: eq applied"

            if track not in valid_tracks:
                return f"error: track must be one of {valid_tracks}"

            if len(parts) == 2:
                # Show all bands for track
                eq = self.player.get_all_eq(track)
                return f"eq {track}: {eq}"

            band = int(parts[2])
            if band < 1 or band > 4:
                return "error: band must be 1-4"

            if len(parts) == 3:
                # Show specific band
                band_info = self.player.get_eq_band(track, band)
                freq = band_info.get("freq", 0)
                gain = band_info.get("gain", 0)
                width = band_info.get("width", 1.0)
                return f"eq {track} band{band}: freq={freq:.0f}Hz gain={gain:.1f}dB width={width:.1f}"

            if len(parts) >= 5:
                # Set parameter: eq vox 1 gain 3.5
                param = parts[3].lower()
                value = float(parts[4])

                if param == "freq":
                    self.player.set_eq_band(track, band, freq=value)
                    return f"ok: eq {track} band{band} freq={value:.0f}Hz"
                elif param == "gain":
                    if value < -12 or value > 12:
                        return "error: gain must be between -12 and 12 dB"
                    self.player.set_eq_band(track, band, gain=value)
                    return f"ok: eq {track} band{band} gain={value:.1f}dB"
                elif param == "width":
                    if value < 0.1 or value > 10:
                        return "error: width (Q) must be between 0.1 and 10"
                    self.player.set_eq_band(track, band, width=value)
                    return f"ok: eq {track} band{band} width={value:.1f}"
                else:
                    return "error: parameter must be 'freq', 'gain', or 'width'"

            return "error: invalid eq command syntax"
        except ValueError as e:
            return f"error: invalid value: {e}"
        except Exception as e:
            return f"error: eq command failed: {e}"

    def _handle_time(self, parts):
        """Handle time command to view/set schedule times."""
        try:
            start = os.getenv("PLAY_START_TIME", "")
            end = os.getenv("PLAY_END_TIME", "")

            if len(parts) == 1:
                # Show current times
                if start and end:
                    return f"time: start={start} stop={end}"
                return "time: schedule not set"

            if len(parts) == 2:
                arg = parts[1].lower()
                if arg == "clear":
                    os.environ["PLAY_START_TIME"] = ""
                    os.environ["PLAY_END_TIME"] = ""
                    return "ok: schedule cleared (use 'save' to persist)"
                return "error: usage: time [start <HH:MM>] [stop <HH:MM>] or time clear"

            if len(parts) >= 3:
                action = parts[1].lower()
                value = parts[2]

                # Validate time format
                try:
                    datetime.strptime(value, "%H:%M")
                except ValueError:
                    return f"error: invalid time format '{value}'. Use HH:MM (24h)"

                if action == "start":
                    os.environ["PLAY_START_TIME"] = value
                    return f"ok: start={value} (use 'save' to persist)"
                elif action == "stop":
                    os.environ["PLAY_END_TIME"] = value
                    return f"ok: stop={value} (use 'save' to persist)"
                else:
                    return f"error: unknown action '{action}'. Use 'start' or 'stop'"

            return "error: usage: time [start <HH:MM>] [stop <HH:MM>] or time clear"
        except Exception as e:
            return f"error: time command failed: {e}"

    def _handle_reboot(self, parts):
        """Reboot the Raspberry Pi."""
        try:
            import subprocess

            # Send response before rebooting
            subprocess.Popen(["sudo", "reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "ok: rebooting..."
        except Exception as e:
            return f"error: reboot failed: {e}"

    def _handle_loop(self, parts):
        """Handle loop mask track commands."""
        try:
            if len(parts) == 1:
                return "error: usage: loop <0-1> or loop lead <seconds>"

            action = parts[1].lower()

            # Check if it's "loop lead <secs>"
            if action == "lead" and len(parts) >= 3:
                lead = float(parts[2])
                if lead < 0:
                    return "error: lead time must be positive"
                self.player.set_loop_lead_time(lead)
                return f"ok: loop lead={lead:.0f}s"

            # Otherwise treat as "loop <val>" for volume
            vol = float(action)
            if vol < 0.0 or vol > 1.0:
                return "error: volume must be between 0.0 and 1.0"
            self.player.set_loop_volume(vol)
            return f"ok: loop={vol:.2f}"

        except ValueError as e:
            return f"error: invalid value: {e}"
        except Exception as e:
            return f"error: loop command failed: {e}"

    def _process_command(self, command):
        parts = command.split()
        if not parts:
            return "error: empty command"

        cmd = parts[0].lower()

        handlers = {
            "status": self._handle_status,
            "play": self._handle_play,
            "stop": self._handle_stop,
            "vox": self._handle_vox,
            "centre": self._handle_centre,
            "sub": self._handle_sub,
            "surround": self._handle_surround,
            "stereo": self._handle_stereo,
            "save": self._handle_save,
            "eq": self._handle_eq,
            "time": self._handle_time,
            "loop": self._handle_loop,
            "reboot": self._handle_reboot,
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


def _resolve_usb_port_to_device(usb_port_id):  # noqa
    """Resolve a USB port identifier to the current ALSA device name.

    USB port paths are stable across reboots even for identical devices,
    as they identify the physical port rather than the device.

    Args:
        usb_port_id: String like 'usbport:usb1/1-1.2' or 'usbport:usb1/1-1.2/1-1.2:1.0'

    Returns:
        ALSA device string like 'plughw:CARD=PRO,DEV=0' or None if not found
    """
    if not usb_port_id.startswith("usbport:"):
        # Not a USB port identifier, return as-is (legacy format)
        return usb_port_id

    target_port = usb_port_id[8:]  # Remove 'usbport:' prefix

    try:
        # List all sound cards and find which one matches this USB port
        cards_path = Path("/proc/asound/cards")
        if not cards_path.exists():
            print(f"Warning: /proc/asound/cards not found, cannot resolve {usb_port_id}")
            return None

        # Parse /proc/asound/cards to get card numbers and names
        # Format: " 0 [Headphones      ]: bcm2835_headpho - bcm2835 Headphones"
        cards = {}
        with open(cards_path) as f:
            for line in f:
                line = line.strip()
                if line and line[0].isdigit():
                    parts = line.split("[")
                    if len(parts) >= 2:
                        card_num = parts[0].strip().split()[0]
                        card_name = parts[1].split("]")[0].strip()
                        cards[card_num] = card_name

        # Check each card to see if it matches the target USB port
        for card_num, card_name in cards.items():
            device_path = Path(f"/sys/class/sound/card{card_num}/device")
            if device_path.exists():
                try:
                    real_path = str(device_path.resolve())
                    # Check if the target USB port appears in the device path
                    # The port path like "1-1.2" should appear in the resolved path
                    if target_port in real_path or any(
                        part in real_path for part in target_port.split("/") if part and not part.startswith("usb")
                    ):
                        device_str = f"plughw:CARD={card_name},DEV=0"
                        print(f"Resolved {usb_port_id} → {device_str}")
                        return device_str
                except Exception:
                    continue

        print(f"Warning: Could not resolve USB port {usb_port_id} to any current device")
        return None

    except Exception as e:
        print(f"Warning: Error resolving USB port {usb_port_id}: {e}")
        return None


def _resolve_device(device_str):
    """Resolve a device string, handling USB port identifiers.

    If the device is a USB port identifier (usbport:...), resolve it to
    the current ALSA device name. Otherwise return as-is.
    """
    if device_str and device_str.startswith("usbport:"):
        return _resolve_usb_port_to_device(device_str)
    return device_str


def _get_audio_device(args):
    if args.device1 and args.device2:
        return (_resolve_device(args.device1), _resolve_device(args.device2))
    elif args.device1:
        return _resolve_device(args.device1)

    # allow overriding via env vars for systemd or uv run usage
    env1 = os.environ.get("AUDIO_DEVICE_1")
    env2 = os.environ.get("AUDIO_DEVICE_2")
    if env1 and env2:
        return (_resolve_device(env1), _resolve_device(env2))
    elif env1:
        return _resolve_device(env1)
    return None


def _get_volumes():
    """Load volumes from environment variables."""
    return {
        "vox": float(os.getenv("VOX_VOLUME", 0.5)),
        "sub": float(os.getenv("SUB_VOLUME", 0.5)),
        "surround_left": float(os.getenv("SURROUND_LEFT_VOLUME", 0.5)),
        "surround_right": float(os.getenv("SURROUND_RIGHT_VOLUME", 0.5)),
        "loop": float(os.getenv("LOOP_VOLUME", 0.5)),
        "loop_lead_time": float(os.getenv("LOOP_LEAD_TIME", 60)),
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
    parser.add_argument("--device1", help="ALSA hw device for vox/sub track (e.g. hw:1,0)", default=None)
    parser.add_argument("--device2", help="ALSA hw device for surround track (e.g. hw:2,0)", default=None)
    parser.add_argument("--mode", choices=["2ch", "4ch"], help="Playback mode (2ch or 4ch)", default=None)
    parser.add_argument(
        "--ignore-schedule",
        action="store_true",
        help="Start playback immediately, ignoring PLAY_START_TIME/PLAY_END_TIME",
    )
    args = parser.parse_args()

    print("Hello from Karla Bidi playback!")

    # Get playback mode from args or env
    playback_mode = args.mode or os.getenv("PLAYBACK_MODE", "4ch")
    print(f"Playback mode: {playback_mode}")

    audio_device = _get_audio_device(args)
    volumes = _get_volumes()

    player = MP3Player(
        playback_mode=playback_mode,
        sum_path="./files/sum.wav",
        instruments_path="./files/instruments.wav",
        vox_sub_path="./files/vox_sub.wav",
        loop_path="./files/loop.wav",
        audio_device=audio_device,
        vox_volume=volumes["vox"],
        sub_volume=volumes["sub"],
        surround_left_volume=volumes["surround_left"],
        surround_right_volume=volumes["surround_right"],
        loop_volume=volumes["loop"],
        loop_lead_time=volumes["loop_lead_time"],
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
