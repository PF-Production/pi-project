import os
import platform
import shutil
import signal
import subprocess
import threading
import time
from datetime import datetime, timedelta

import pygame


class MP3Player:
    def __init__(
        self,
        mp3_path,
        second_path=None,
        volume=0.5,
        audio_device=None,
        second_volume=0.5,
        main_left_volume=None,
        main_right_volume=None,
        second_left_volume=None,
        second_right_volume=None,
    ):
        # audio_device may be:
        #  - None -> use default OS audio (pygame)
        #  - a single string (e.g. "hw:1,0") -> use that device for the centre track
        #  - a tuple/list of two strings (centre_device, stereo_device) -> play each track to its device
        self._subprocs = []

        self.mp3_path = mp3_path
        self.second_path = second_path
        self.volume = volume
        self.second_volume = second_volume

        # Per-channel volume settings (defaults to overall volume if not specified)
        self.main_left_volume = main_left_volume if main_left_volume is not None else volume
        self.main_right_volume = main_right_volume if main_right_volume is not None else volume
        self.second_left_volume = second_left_volume if second_left_volume is not None else second_volume
        self.second_right_volume = second_right_volume if second_right_volume is not None else second_volume

        # keep reference to pygame channel for second track (dev/testing)
        self._pygame_channel2 = None
        self._playing = False
        self._thread = None

        # Playback source:
        # - None: not playing
        # - "manual": started via remote 'play' or immediate startup (--ignore-schedule)
        # - "scheduled": started by the schedule window
        self._playback_source = None

        # Scheduling state (only set when play_between_times() is used)
        self._schedule_start_time = None
        self._schedule_end_time = None

        # Track window instances so we can enforce "start once per window"
        self._schedule_started_window_id = None
        self._manual_stop_window_id = None
        # If set, manual playback was started during this window and should stop at window end
        self._manual_play_window_id = None

        # Normalize devices
        if audio_device is None:
            self.devices = None
        elif isinstance(audio_device, (list, tuple)):
            # two devices expected
            self.devices = tuple(audio_device)
        else:
            # single device - use for main track only
            self.devices = (audio_device, None)

        # Use subprocess/ALSA loop playback on Linux when devices are provided and 'aplay' exists.
        use_alsa_subprocess = (
            platform.system() == "Linux" and self.devices is not None and shutil.which("aplay") is not None
        )

        if use_alsa_subprocess:
            # don't initialize pygame (avoids taking ALSA device on headless Pi)
            self._use_subprocess = True
        else:
            # fallback to pygame for macOS / Windows / development
            self._use_subprocess = False
            # Set SDL driver for Raspberry Pi only if explicitly requested and pygame is used
            if self.devices and platform.system() == "Linux":
                os.environ["SDL_AUDIODRIVER"] = "alsa"
                # AUDIODEV may be honored by some SDL builds, but pygame lacks a standard API for per-device selection
                if self.devices[0]:
                    os.environ["AUDIODEV"] = self.devices[0]
            pygame.mixer.init()
            pygame.mixer.music.set_volume(self.volume)

    def _within_window_time(self, now, start_time, end_time):
        if start_time == end_time:
            # Treat matching times as "always on"
            return True
        if start_time < end_time:
            return start_time <= now < end_time
        # Window wraps past midnight
        return now >= start_time or now < end_time

    def _current_window_id(self, now_dt):
        """Return a stable identifier for the current active window instance, or None."""
        if self._schedule_start_time is None or self._schedule_end_time is None:
            return None

        start_time = self._schedule_start_time
        end_time = self._schedule_end_time
        now_time = now_dt.time()

        if not self._within_window_time(now_time, start_time, end_time):
            return None

        # Determine which calendar date the window started on (important when wrapping midnight)
        if start_time == end_time:
            start_date = now_dt.date()
        elif start_time < end_time:
            start_date = now_dt.date()
        else:
            start_date = now_dt.date() if now_time >= start_time else (now_dt.date() - timedelta(days=1))

        return (start_date.isoformat(), start_time.strftime("%H:%M"), end_time.strftime("%H:%M"))

    # --- ALSA volume helpers (best-effort using amixer) ---------------------------------
    def _card_from_hw(self, device_str):
        # device_str like 'hw:1,0' -> returns card index 1
        if not device_str or not device_str.startswith("hw:"):
            return None
        try:
            card = int(device_str.split(":")[1].split(",")[0])
            return card
        except Exception:
            return None

    def _try_set_mixer(self, card, control, value_str):
        # Try to set a mixer control on card using amixer; return True on success
        try:
            cmd = ["amixer", "-c", str(card), "set", control, value_str]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.returncode == 0
        except FileNotFoundError:
            return False

    def _set_alsa_volume_for_device(self, device, vol_val):
        # vol_val: float 0.0..1.0 OR tuple (left_float, right_float)
        if not device:
            return False
        card = self._card_from_hw(device)
        if card is None:
            return False

        if isinstance(vol_val, (tuple, list)):
            left = int(max(0.0, min(1.0, vol_val[0])) * 100)
            right = int(max(0.0, min(1.0, vol_val[1])) * 100)
            value_str = f"{left}%,{right}%"
        else:
            percent = int(max(0.0, min(1.0, vol_val)) * 100)
            value_str = f"{percent}%"

        # common control names to try
        for control in ("Master", "PCM", "Digital", "Speaker", "Headphone"):
            ok = self._try_set_mixer(card, control, value_str)
            if ok:
                # success
                return True
        # nothing worked
        return False

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))
        self.main_left_volume = self.volume
        self.main_right_volume = self.volume
        if not self._use_subprocess:
            pygame.mixer.music.set_volume(self.volume)
            # if pygame second channel exists, keep its volume consistent
            if self._pygame_channel2:
                try:
                    self._pygame_channel2.set_volume(self.second_volume)
                except Exception:
                    pass
        else:
            # attempt to set ALSA volume for main device
            main_device = None
            if isinstance(self.devices, tuple):
                main_device = self.devices[0]
            else:
                main_device = self.devices
            if main_device:
                ok = self._set_alsa_volume_for_device(main_device, self.volume)
                if not ok:
                    print(
                        f"Warning: could not set ALSA mixer for device {main_device}. "
                        "Try running with sudo or configure sudoers."
                    )

    def set_main_channel_volumes(self, left_volume, right_volume):
        """Set left and right channel volumes for the main track independently."""
        self.main_left_volume = max(0.0, min(1.0, left_volume))
        self.main_right_volume = max(0.0, min(1.0, right_volume))
        # Update overall volume to average
        self.volume = (self.main_left_volume + self.main_right_volume) / 2
        if not self._use_subprocess:
            pygame.mixer.music.set_volume(self.volume)
        else:
            # attempt to set ALSA volume for main device
            try:
                main_device = None
                if isinstance(self.devices, tuple):
                    main_device = self.devices[0]
                else:
                    main_device = self.devices
                if main_device:
                    ok = self._set_alsa_volume_for_device(main_device, (self.main_left_volume, self.main_right_volume))
                    if not ok:
                        print(
                            f"Warning: could not set ALSA mixer for device {main_device}. "
                            "Try running with sudo or configure sudoers."
                        )
            except Exception as e:
                print(f"Error setting ALSA volume for main channels: {e}")

    def set_second_channel_volumes(self, left_volume, right_volume):
        """Set left and right channel volumes for the second track independently."""
        self.second_left_volume = max(0.0, min(1.0, left_volume))
        self.second_right_volume = max(0.0, min(1.0, right_volume))
        # Update overall volume to average
        self.second_volume = (self.second_left_volume + self.second_right_volume) / 2
        if not self._use_subprocess:
            if self._pygame_channel2:
                try:
                    self._pygame_channel2.set_volume(self.second_volume)
                except Exception:
                    pass
        else:
            # attempt to set ALSA volume for second device
            try:
                second_device = None
                if isinstance(self.devices, tuple):
                    second_device = self.devices[1]
                if second_device:
                    ok = self._set_alsa_volume_for_device(
                        second_device, (self.second_left_volume, self.second_right_volume)
                    )
                    if not ok:
                        print(
                            f"Warning: could not set ALSA mixer for device {second_device}. "
                            "Try running with sudo or configure sudoers."
                        )
            except Exception as e:
                print(f"Error setting ALSA volume for second channels: {e}")

    def set_second_volume(self, volume):
        self.second_volume = max(0.0, min(1.0, volume))
        self.second_left_volume = self.second_volume
        self.second_right_volume = self.second_volume
        if not self._use_subprocess:
            if self._pygame_channel2:
                try:
                    self._pygame_channel2.set_volume(self.second_volume)
                except Exception:
                    pass
        else:
            # attempt to set ALSA volume for second device
            second_device = None
            if isinstance(self.devices, tuple):
                second_device = self.devices[1]
            if second_device:
                ok = self._set_alsa_volume_for_device(second_device, self.second_volume)
                if not ok:
                    print(
                        f"Warning: could not set ALSA mixer for device {second_device}. "
                        "Try running with sudo or configure sudoers."
                    )

    def _start_subprocess_playback(self):
        """Start subprocess-based ALSA playback for each device."""
        self.stop()
        procs = []

        def start_loop_playback(path, device):
            if not path or not device:
                return None
            # Use a shell loop to re-run aplay so the audio repeats.
            cmd = f"while true; do aplay -D {device} '{path}'; done"
            # Start in a new session so we can reliably terminate the whole process group
            # (the shell loop *and* any aplay child process) on stop().
            return subprocess.Popen(["/bin/sh", "-c", cmd], start_new_session=True)

        main_device, second_device = self.devices if isinstance(self.devices, tuple) else (self.devices, None)

        # Start main device playback
        if isinstance(main_device, str):
            try:
                self._set_alsa_volume_for_device(main_device, self.volume)
            except Exception:
                pass
            p1 = start_loop_playback(self.mp3_path, main_device)
            if p1:
                procs.append(p1)

        # Start second device playback
        if self.second_path and isinstance(second_device, str):
            try:
                self._set_alsa_volume_for_device(second_device, self.second_volume)
            except Exception:
                pass
            p2 = start_loop_playback(self.second_path, second_device)
            if p2:
                procs.append(p2)

        self._subprocs = procs
        self._playing = len(procs) > 0

    def _start_pygame_playback(self):
        """Start pygame-based playback for single default output."""
        pygame.mixer.music.load(self.mp3_path)
        pygame.mixer.music.play(loops=-1)
        self._playing = True

        # Play second track if provided (same output)
        if self.second_path:
            sound2 = pygame.mixer.Sound(self.second_path)
            channel2 = pygame.mixer.Channel(1)
            channel2.set_volume(self.second_volume)
            channel2.play(sound2, loops=-1)
            self._pygame_channel2 = channel2

    def play_loop(self, source: str = "manual"):
        """
        Cross-platform play:
        - On Linux with ALSA devices and `aplay` available: spawn subprocess loops for each device.
        - Otherwise: use pygame.mixer (single default output) for dev on macOS/Windows.
        """
        # An explicit play should always be immediate.
        # Also clear any manual-stop suppression for the current window.
        self._manual_stop_window_id = None
        self._playback_source = source

        # If we have a schedule configured, and manual play happens inside an active window,
        # treat it as "play until the end of this window".
        if source == "manual" and self._schedule_start_time is not None and self._schedule_end_time is not None:
            self._manual_play_window_id = self._current_window_id(datetime.now())
        else:
            self._manual_play_window_id = None
        if self._use_subprocess:
            self._start_subprocess_playback()
        else:
            self._start_pygame_playback()

    def stop(self, manual: bool = False):  # noqa: C901
        # Manual stop should prevent schedule auto-restart only for the *current* window.
        if manual:
            window_id = self._current_window_id(datetime.now())
            if window_id is not None:
                self._manual_stop_window_id = window_id

        self._playback_source = None
        self._manual_play_window_id = None
        if self._use_subprocess:
            # terminate subprocesses started for ALSA playback
            for p in getattr(self, "_subprocs", []):
                try:
                    # We spawn playback via /bin/sh -c "while true; do aplay ...; done".
                    # Terminating only the shell can leave the child `aplay` running.
                    # Kill the whole process group instead.
                    try:
                        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                    except Exception:
                        p.terminate()

                    p.wait(timeout=2)
                except Exception:
                    try:
                        try:
                            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                        except Exception:
                            p.kill()
                    except Exception:
                        pass
            self._subprocs = []
            self._playing = False
        else:
            pygame.mixer.music.stop()
            if self.second_path:
                if self._pygame_channel2:
                    try:
                        self._pygame_channel2.stop()
                    except Exception:
                        pass
            self._playing = False

    def play_between_times(self, start_time, end_time):
        """Run playback only between start_time and end_time (local time objects)."""

        self._schedule_start_time = start_time
        self._schedule_end_time = end_time

        def _run():
            while True:
                now_dt = datetime.now()
                window_id = self._current_window_id(now_dt)

                if window_id is None:
                    # Outside window: reset per-window state so the next window can start.
                    self._manual_stop_window_id = None
                    self._schedule_started_window_id = None

                    # Only stop playback if the schedule started it.
                    if self._playing and self._playback_source == "scheduled":
                        self.stop(manual=False)
                    # Stop manual playback that was started inside a window.
                    elif (
                        self._playing and self._playback_source == "manual" and self._manual_play_window_id is not None
                    ):
                        self.stop(manual=False)
                else:
                    # Inside window: start at most once per window instance.
                    # If a manual stop happened this window, don't auto-restart.
                    if (
                        not self._playing
                        and self._playback_source != "manual"
                        and self._schedule_started_window_id != window_id
                        and self._manual_stop_window_id != window_id
                    ):
                        self.play_loop(source="scheduled")
                        self._schedule_started_window_id = window_id
                time.sleep(1)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def is_playing(self):
        return self._playing
