import pygame
import threading
import time
from datetime import datetime

import os
import platform
import subprocess
import shutil


class MP3Player:
    def __init__(
        self,
        mp3_path,
        second_path=None,
        volume=0.5,
        audio_device=None,
        second_volume=0.5,
    ):
        # audio_device may be:
        #  - None -> use default OS audio (pygame)
        #  - a single string (e.g. "hw:1,0") -> use that device for the main track
        #  - a tuple/list of two strings (device_main, device_second) -> play each track to its device
        self._subprocs = []

        self.mp3_path = mp3_path.replace(
            "kb.mp3.wav", "karla bidi - instruments stereo.wav"
        )
        self.second_path = second_path
        self.volume = volume
        self.second_volume = second_volume
        # keep reference to pygame channel for second track (dev/testing)
        self._pygame_channel2 = None
        self._playing = False
        self._thread = None

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
            platform.system() == "Linux"
            and self.devices is not None
            and shutil.which("aplay") is not None
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

    def _try_set_mixer(self, card, control, percent):
        # Try to set a mixer control on card using amixer; return True on success
        try:
            cmd = ["amixer", "-c", str(card), "set", control, f"{percent}%"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.returncode == 0
        except FileNotFoundError:
            return False

    def _set_alsa_volume_for_device(self, device, vol_float):
        # vol_float 0.0..1.0
        if not device:
            return False
        card = self._card_from_hw(device)
        if card is None:
            return False
        percent = int(max(0.0, min(1.0, vol_float)) * 100)
        # common control names to try
        for control in ("Master", "PCM", "Digital", "Speaker", "Headphone"):
            ok = self._try_set_mixer(card, control, percent)
            if ok:
                # success
                return True
        # nothing worked
        return False

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))
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
                    print(f"Warning: could not set ALSA mixer for device {main_device}")

    def set_second_volume(self, volume):
        self.second_volume = max(0.0, min(1.0, volume))
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
                        f"Warning: could not set ALSA mixer for device {second_device}"
                    )

    def play_loop(self):
        """
        Cross-platform play:
        - On Linux with ALSA devices and `aplay` available: spawn subprocess loops which play each file to the specified hw device.
        - Otherwise: use pygame.mixer (single default output) for dev on macOS/Windows.
        """
        if self._use_subprocess:
            # stop any previous subprocesses
            self.stop()
            procs = []

            def start_loop_playback(path, device):
                if not path or not device:
                    return None
                # Use a shell loop to re-run aplay so the audio repeats.
                cmd = f"while true; do aplay -D {device} '{path}'; done"
                return subprocess.Popen(["/bin/sh", "-c", cmd])

            main_device, second_device = (
                self.devices
                if isinstance(self.devices, tuple)
                else (self.devices, None)
            )
            # If a single device tuple was passed like (dev, None) main_device will be device string
            # Start main (set initial volume first)
            if isinstance(main_device, str):
                # try to set ALSA volume before playback
                try:
                    self._set_alsa_volume_for_device(main_device, self.volume)
                except Exception:
                    pass
                p1 = start_loop_playback(self.mp3_path, main_device)
                if p1:
                    procs.append(p1)
            # Start second if provided
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
        else:
            # pygame fallback (single output)
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

    def stop(self):
        if self._use_subprocess:
            # terminate subprocesses started for ALSA playback
            for p in getattr(self, "_subprocs", []):
                try:
                    p.terminate()
                    p.wait(timeout=1)
                except Exception:
                    try:
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
        """
        start_time and end_time should be datetime.time objects
        """

        def _run():
            while True:
                now = datetime.now().time()
                if start_time <= now <= end_time:
                    if not self._playing:
                        self.play_loop()
                else:
                    if self._playing:
                        self.stop()
                time.sleep(1)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def is_playing(self):
        return self._playing
