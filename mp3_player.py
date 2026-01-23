import os
import platform
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timedelta

import numpy as np
import pygame
from scipy.io import wavfile

from eq_processor import load_eq_from_env


class MP3Player:
    def __init__(
        self,
        playback_mode="4ch",
        sum_path="./files/sum.wav",
        instruments_path="./files/instruments.wav",
        vox_sub_path="./files/vox_sub.wav",
        loop_path="./files/loop.wav",
        audio_device=None,
        # Volume settings
        vox_volume=0.5,
        sub_volume=0.5,
        surround_left_volume=0.5,
        surround_right_volume=0.5,
        # Loop mask track settings
        loop_volume=0.5,
        loop_lead_time=60,
        # EQ processors (optional, loaded from env if None)
        vox_eq=None,
        sub_eq=None,
        surround_eq=None,
    ):
        """
        Initialize MP3Player with support for 2ch and 4ch playback modes.

        2ch mode: Plays sum.wav to a single stereo output (L=Vox/mono, R=Sub)
        4ch mode: Plays vox_sub.wav (L=Vox, R=Sub) to device 1 +
                  instruments.wav (L=Surround L, R=Surround R) to device 2

        In both modes, vox_volume controls the left channel (vox/mono) and
        sub_volume controls the right channel (sub).

        Loop mask track: An optional short audio file that plays near the end of each
        main track loop to mask the loop point transition.

        Args:
            playback_mode: "2ch" or "4ch"
            sum_path: Path to 1.1 mix stereo file - L=vox/mono, R=sub (2ch mode)
            instruments_path: Path to L-R instruments/surround file (4ch mode)
            vox_sub_path: Path to vox(L)/sub(R) file (4ch mode)
            loop_path: Path to loop mask audio file
            audio_device: None, single device string, or tuple (device1, device2)
            vox_volume: Vox/mono channel volume - left channel (0.0-1.0)
            sub_volume: Sub channel volume - right channel (0.0-1.0)
            surround_left_volume: Surround left volume (0.0-1.0, 4ch mode only)
            surround_right_volume: Surround right volume (0.0-1.0, 4ch mode only)
            loop_volume: Loop mask track volume (0.0-1.0)
            loop_lead_time: Seconds before main track ends to start loop mask
        """
        self._subprocs = []

        # Playback mode
        self.playback_mode = playback_mode.lower() if playback_mode else "4ch"

        # File paths
        self.sum_path = sum_path
        self.instruments_path = instruments_path
        self.vox_sub_path = vox_sub_path
        self.loop_path = loop_path

        # Volume settings
        # vox_volume: left channel (vox/mono) in both 2ch and 4ch modes
        # sub_volume: right channel (sub) in both 2ch and 4ch modes
        self.vox_volume = vox_volume
        self.sub_volume = sub_volume
        self.surround_left_volume = surround_left_volume
        self.surround_right_volume = surround_right_volume

        # Loop mask track settings
        self.loop_volume = loop_volume
        self.loop_lead_time = loop_lead_time
        self._loop_timer_thread = None
        self._loop_proc = None  # Subprocess for loop mask playback
        self._main_track_duration = None  # Duration of main track in seconds

        # EQ processors for each channel
        # vox_eq: left channel EQ (vox/mono) - used in both 2ch and 4ch modes
        # sub_eq: right channel EQ (sub) - used in both 2ch and 4ch modes
        # surround_eq: surround channels - used in 4ch mode only
        self.vox_eq = vox_eq if vox_eq is not None else load_eq_from_env("vox")
        self.sub_eq = sub_eq if sub_eq is not None else load_eq_from_env("sub")
        self.surround_eq = surround_eq if surround_eq is not None else load_eq_from_env("surround")

        # Paths to processed files (None = use original)
        self._processed_vox_sub_path = None
        self._processed_instruments_path = None
        self._processed_sum_path = None
        self._eq_dirty = True  # Flag to reprocess audio when EQ changes

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
            pygame.mixer.music.set_volume(0.5)

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
    def _card_from_device(self, device_str):
        """Extract card identifier from device string for use with amixer.

        Supports both formats:
        - 'hw:1,0' -> returns card index '1'
        - 'plughw:CARD=Headphones,DEV=0' -> returns card name 'Headphones'

        Returns string suitable for amixer -c argument, or None if invalid.
        """
        if not device_str:
            return None

        # Handle plughw:CARD=<name> format (stable device names)
        if "CARD=" in device_str:
            try:
                # Extract card name from 'plughw:CARD=Headphones,DEV=0'
                card_part = device_str.split("CARD=")[1]
                card_name = card_part.split(",")[0].strip()
                return card_name
            except Exception:
                return None

        # Handle hw:X,Y format (legacy numeric indices)
        if device_str.startswith("hw:"):
            try:
                card = device_str.split(":")[1].split(",")[0]
                return card
            except Exception:
                return None

        return None

    def _get_mixer_controls(self, card):
        """Get available mixer controls for a card using amixer."""
        try:
            cmd = ["amixer", "-c", str(card), "scontrols"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                controls = []
                for line in res.stdout.strip().split("\n"):
                    # Parse lines like: Simple mixer control 'Radial USB Pro Output',0
                    if "'" in line:
                        start = line.index("'") + 1
                        end = line.index("'", start)
                        controls.append(line[start:end])
                return controls
        except (FileNotFoundError, ValueError):
            pass
        return []

    def _try_set_mixer(self, card, control, value_str):
        # Try to set a mixer control on card using amixer; return True on success
        # card can be a number or a card name
        try:
            cmd = ["amixer", "-c", str(card), "set", control, value_str]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.returncode == 0
        except FileNotFoundError:
            return False

    def _set_alsa_volume_for_device(self, device, vol_val):  # noqa: C901
        # vol_val: float 0.0..1.0 OR tuple (left_float, right_float)
        if not device:
            return False
        card = self._card_from_device(device)
        if card is None:
            return False

        if isinstance(vol_val, (tuple, list)):
            left = int(max(0.0, min(1.0, vol_val[0])) * 100)
            right = int(max(0.0, min(1.0, vol_val[1])) * 100)
            value_str = f"{left}%,{right}%"
        else:
            percent = int(max(0.0, min(1.0, vol_val)) * 100)
            value_str = f"{percent}%"

        # Try common control names first
        for control in ("Master", "PCM", "Digital", "Speaker", "Headphone"):
            ok = self._try_set_mixer(card, control, value_str)
            if ok:
                return True

        # If standard controls failed, try to detect available controls
        # This handles USB audio devices with custom control names
        available_controls = self._get_mixer_controls(card)
        for control in available_controls:
            # Skip controls we already tried
            if control in ("Master", "PCM", "Digital", "Speaker", "Headphone"):
                continue
            # Prefer controls with "Output" or "Playback" in the name
            if "Output" in control or "Playback" in control or "Volume" in control:
                ok = self._try_set_mixer(card, control, value_str)
                if ok:
                    return True

        # Last resort: try any remaining control
        for control in available_controls:
            if control not in ("Master", "PCM", "Digital", "Speaker", "Headphone"):
                ok = self._try_set_mixer(card, control, value_str)
                if ok:
                    return True

        return False

    def set_vox_volume(self, volume):
        """Set vox (left channel) volume. Works in both 2ch and 4ch modes.

        Volume is baked into the processed audio file for true per-channel control,
        since ALSA mixer controls often don't provide independent L/R adjustment.
        Use 'eq apply' or restart to apply changes.
        ALSA mixer is also adjusted for best-effort runtime control.
        """
        self.vox_volume = max(0.0, min(1.0, volume))

        # Mark as needing reprocessing (for file-level volume in both modes)
        self._eq_dirty = True

        if self._use_subprocess:
            # Vox is the left channel of device 1 (in both 2ch and 4ch modes)
            main_device = self.devices[0] if isinstance(self.devices, tuple) else self.devices
            if main_device:
                self._set_alsa_volume_for_device(main_device, (self.vox_volume, self.sub_volume))
        elif self.playback_mode == "2ch":
            # For pygame in 2ch mode, use average of vox/sub for overall volume
            avg = (self.vox_volume + self.sub_volume) / 2
            pygame.mixer.music.set_volume(avg)

    def set_sub_volume(self, volume):
        """Set sub (right channel) volume. Works in both 2ch and 4ch modes.

        Volume is baked into the processed audio file for true per-channel control,
        since ALSA mixer controls often don't provide independent L/R adjustment.
        Use 'eq apply' or restart to apply changes.
        ALSA mixer is also adjusted for best-effort runtime control.
        """
        self.sub_volume = max(0.0, min(1.0, volume))

        # Mark as needing reprocessing (for file-level volume in both modes)
        self._eq_dirty = True

        if self._use_subprocess:
            # Sub is the right channel of device 1 (in both 2ch and 4ch modes)
            main_device = self.devices[0] if isinstance(self.devices, tuple) else self.devices
            if main_device:
                self._set_alsa_volume_for_device(main_device, (self.vox_volume, self.sub_volume))
        elif self.playback_mode == "2ch":
            # For pygame in 2ch mode, use average of vox/sub for overall volume
            avg = (self.vox_volume + self.sub_volume) / 2
            pygame.mixer.music.set_volume(avg)

    def set_surround_volumes(self, left_volume, right_volume):
        """Set surround (instruments) left and right volumes."""
        self.surround_left_volume = max(0.0, min(1.0, left_volume))
        self.surround_right_volume = max(0.0, min(1.0, right_volume))
        if self._use_subprocess:
            # In 4ch mode, surround is device 2
            second_device = self.devices[1] if isinstance(self.devices, tuple) else None
            if second_device:
                self._set_alsa_volume_for_device(second_device, (self.surround_left_volume, self.surround_right_volume))
        else:
            if self._pygame_channel2:
                try:
                    avg = (self.surround_left_volume + self.surround_right_volume) / 2
                    self._pygame_channel2.set_volume(avg)
                except Exception:
                    pass

    # Legacy methods for compatibility
    def set_volume(self, volume):
        """Set main volume (affects vox/left channel)."""
        self.set_vox_volume(volume)

    def set_main_channel_volumes(self, left_volume, right_volume):
        """Set main track channel volumes (vox/sub - works in both 2ch and 4ch)."""
        self.set_vox_volume(left_volume)
        self.set_sub_volume(right_volume)

    def set_second_channel_volumes(self, left_volume, right_volume):
        """Set second track channel volumes (surround L/R in 4ch)."""
        self.set_surround_volumes(left_volume, right_volume)

    def set_second_volume(self, volume):
        """Set second track volume (surround in 4ch)."""
        self.set_surround_volumes(volume, volume)

    # --- Loop Mask Track Methods ---

    def set_loop_volume(self, volume):
        """Set loop mask track volume."""
        self.loop_volume = max(0.0, min(1.0, volume))

    def set_loop_lead_time(self, seconds):
        """Set how many seconds before loop end to start the mask track."""
        self.loop_lead_time = max(0.0, seconds)

    def _get_wav_duration(self, path):
        """Get duration of a WAV file in seconds."""
        if not path or not os.path.exists(path):
            return None
        try:
            sample_rate, data = wavfile.read(path)
            return len(data) / sample_rate
        except Exception as e:
            print(f"Warning: Could not get duration of {path}: {e}")
            return None

    def _start_loop_mask_timer(self, main_track_path, device):
        """Start a timer thread that triggers the loop mask at the right time."""
        if not self.loop_path or not os.path.exists(self.loop_path):
            return  # No loop mask file

        duration = self._get_wav_duration(main_track_path)
        if duration is None:
            return

        self._main_track_duration = duration

        # Calculate when to trigger (relative to loop start)
        trigger_time = max(0, duration - self.loop_lead_time)

        def _loop_timer():
            """Timer thread that triggers loop mask playback."""
            import time as time_module

            loop_start = time_module.time()

            while self._playing:
                elapsed = time_module.time() - loop_start
                time_in_loop = elapsed % duration

                # Check if we should trigger the loop mask
                if time_in_loop >= trigger_time and time_in_loop < trigger_time + 1:
                    self._play_loop_mask(device)
                    # Wait until next loop cycle
                    time_module.sleep(self.loop_lead_time + 2)
                    continue

                time_module.sleep(0.5)

        self._loop_timer_thread = threading.Thread(target=_loop_timer, daemon=True)
        self._loop_timer_thread.start()

    def _play_loop_mask(self, device):
        """Play the loop mask track once."""
        if not self.loop_path or not os.path.exists(self.loop_path):
            return

        if self._use_subprocess and device:
            try:
                # Apply volume by processing the file (simple amplitude scaling)
                loop_file = self._process_loop_file()

                # Play the loop mask file once (not looping)
                cmd = ["aplay", "-D", device, loop_file]
                self._loop_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Warning: Could not play loop mask: {e}")
        else:
            # pygame fallback - just play the sound
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                sound = pygame.mixer.Sound(self.loop_path)
                sound.set_volume(self.loop_volume)
                sound.play()
            except Exception as e:
                print(f"Warning: Could not play loop mask with pygame: {e}")

    def _process_loop_file(self):
        """Process loop file with volume adjustment. Returns path to processed file."""
        if self.loop_volume == 1.0:
            return self.loop_path  # No processing needed

        try:
            sample_rate, data = wavfile.read(self.loop_path)

            # Convert to float for processing
            if data.dtype == np.int16:
                audio_float = data.astype(np.float64) / 32768.0
            elif data.dtype == np.int32:
                audio_float = data.astype(np.float64) / 2147483648.0
            else:
                audio_float = data.astype(np.float64)

            # Apply volume
            audio_float = audio_float * self.loop_volume

            # Clip to prevent distortion
            audio_float = np.clip(audio_float, -1.0, 1.0)

            # Convert back
            if data.dtype == np.int16:
                processed = (audio_float * 32767).astype(np.int16)
            elif data.dtype == np.int32:
                processed = (audio_float * 2147483647).astype(np.int32)
            else:
                processed = audio_float

            # Write to temp file
            fd, temp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            wavfile.write(temp_path, sample_rate, processed)
            return temp_path

        except Exception as e:
            print(f"Warning: Could not process loop file: {e}")
            return self.loop_path

    def _process_vox_sub_file(self):
        """
        Process vox_sub.wav applying separate volume and EQ to left (vox) and right (sub) channels.

        Volume is applied at the file level to ensure true per-channel control,
        since ALSA mixer controls often don't provide independent L/R adjustment.

        Returns path to processed file or None if no processing needed.
        """
        if not self.vox_sub_path or not os.path.exists(self.vox_sub_path):
            return None

        # Check if any processing is needed (volume != 1.0 or EQ active)
        needs_volume = self.vox_volume != 1.0 or self.sub_volume != 1.0
        needs_eq = self.vox_eq.has_active_eq() or self.sub_eq.has_active_eq()

        if not needs_volume and not needs_eq:
            return None

        try:
            sample_rate, audio_data = wavfile.read(self.vox_sub_path)

            # Ensure stereo
            if len(audio_data.shape) == 1:
                audio_data = np.column_stack([audio_data, audio_data])

            # Convert to float for processing
            original_dtype = audio_data.dtype
            if np.issubdtype(original_dtype, np.integer):
                max_val = np.iinfo(original_dtype).max
                audio_float = audio_data.astype(np.float64) / max_val
            else:
                audio_float = audio_data.astype(np.float64)

            # Process left channel (vox) with volume and EQ
            left_channel = audio_float[:, 0:1]  # Keep as 2D
            left_channel = left_channel * self.vox_volume  # Apply volume
            if self.vox_eq.has_active_eq():
                left_processed = self.vox_eq.process_audio(left_channel, sample_rate)
            else:
                left_processed = left_channel

            # Process right channel (sub) with volume and EQ
            right_channel = audio_float[:, 1:2]  # Keep as 2D
            right_channel = right_channel * self.sub_volume  # Apply volume
            if self.sub_eq.has_active_eq():
                right_processed = self.sub_eq.process_audio(right_channel, sample_rate)
            else:
                right_processed = right_channel

            # Combine channels
            processed = np.column_stack([left_processed.flatten(), right_processed.flatten()])

            # Convert back to original dtype
            if np.issubdtype(original_dtype, np.integer):
                processed = np.clip(processed * max_val, -max_val, max_val).astype(original_dtype)
            else:
                processed = processed.astype(original_dtype)

            # Write to temp file
            fd, output_path = tempfile.mkstemp(suffix=".wav", prefix="vox_sub_processed_")
            os.close(fd)
            wavfile.write(output_path, sample_rate, processed)

            print(f"Processed vox_sub track: vox_vol={self.vox_volume:.2f}, sub_vol={self.sub_volume:.2f}")
            return output_path

        except Exception as e:
            print(f"Warning: Could not process vox_sub track: {e}")
            return None

    def _process_sum_file(self):
        """
        Process sum.wav applying separate volume and EQ to left (vox) and right (sub) channels.
        Same as _process_vox_sub_file but for the sum.wav file used in 2ch mode.

        Volume is applied at the file level to ensure true per-channel control,
        since ALSA mixer controls often don't provide independent L/R adjustment.

        Returns path to processed file or None if no processing needed.
        """
        if not self.sum_path or not os.path.exists(self.sum_path):
            return None

        # Check if any processing is needed (volume != 1.0 or EQ active)
        needs_volume = self.vox_volume != 1.0 or self.sub_volume != 1.0
        needs_eq = self.vox_eq.has_active_eq() or self.sub_eq.has_active_eq()

        if not needs_volume and not needs_eq:
            return None

        try:
            sample_rate, audio_data = wavfile.read(self.sum_path)

            # Ensure stereo
            if len(audio_data.shape) == 1:
                audio_data = np.column_stack([audio_data, audio_data])

            # Convert to float for processing
            original_dtype = audio_data.dtype
            if np.issubdtype(original_dtype, np.integer):
                max_val = np.iinfo(original_dtype).max
                audio_float = audio_data.astype(np.float64) / max_val
            else:
                audio_float = audio_data.astype(np.float64)

            # Process left channel (vox/mono) with volume and EQ
            left_channel = audio_float[:, 0:1]  # Keep as 2D
            left_channel = left_channel * self.vox_volume  # Apply volume
            if self.vox_eq.has_active_eq():
                left_processed = self.vox_eq.process_audio(left_channel, sample_rate)
            else:
                left_processed = left_channel

            # Process right channel (sub) with volume and EQ
            right_channel = audio_float[:, 1:2]  # Keep as 2D
            right_channel = right_channel * self.sub_volume  # Apply volume
            if self.sub_eq.has_active_eq():
                right_processed = self.sub_eq.process_audio(right_channel, sample_rate)
            else:
                right_processed = right_channel

            # Combine channels
            processed = np.column_stack([left_processed.flatten(), right_processed.flatten()])

            # Convert back to original dtype
            if np.issubdtype(original_dtype, np.integer):
                processed = np.clip(processed * max_val, -max_val, max_val).astype(original_dtype)
            else:
                processed = processed.astype(original_dtype)

            # Write to temp file
            fd, output_path = tempfile.mkstemp(suffix=".wav", prefix="sum_processed_")
            os.close(fd)
            wavfile.write(output_path, sample_rate, processed)

            print(f"Processed sum track: vox_vol={self.vox_volume:.2f}, sub_vol={self.sub_volume:.2f}")
            return output_path

        except Exception as e:
            print(f"Warning: Could not process sum track: {e}")
            return None

    def _start_subprocess_playback(self):  # noqa: C901
        """Start subprocess-based ALSA playback for each device."""
        self.stop()
        procs = []

        # Get EQ-processed paths (or originals if no EQ)
        primary_path, secondary_path = self._get_playback_paths()

        def start_loop_playback(path, device):
            if not path or not device:
                return None
            # Use a shell loop to re-run aplay so the audio repeats.
            cmd = f"while true; do aplay -D {device} '{path}'; done"
            # Start in a new session so we can reliably terminate the whole process group
            # (the shell loop *and* any aplay child process) on stop().
            return subprocess.Popen(["/bin/sh", "-c", cmd], start_new_session=True)

        main_device, second_device = self.devices if isinstance(self.devices, tuple) else (self.devices, None)

        if self.playback_mode == "2ch":
            # 2ch mode: play sum.wav to main device only (vox=left, sub=right)
            if isinstance(main_device, str):
                try:
                    self._set_alsa_volume_for_device(main_device, (self.vox_volume, self.sub_volume))
                except Exception:
                    pass
                p1 = start_loop_playback(primary_path, main_device)
                if p1:
                    procs.append(p1)
        else:
            # 4ch mode: play vox_sub to device 1, instruments to device 2
            if isinstance(main_device, str):
                try:
                    self._set_alsa_volume_for_device(main_device, (self.vox_volume, self.sub_volume))
                except Exception:
                    pass
                p1 = start_loop_playback(primary_path, main_device)
                if p1:
                    procs.append(p1)

            # Start second device playback (instruments/surround)
            if secondary_path and isinstance(second_device, str):
                try:
                    self._set_alsa_volume_for_device(
                        second_device, (self.surround_left_volume, self.surround_right_volume)
                    )
                except Exception:
                    pass
                p2 = start_loop_playback(secondary_path, second_device)
                if p2:
                    procs.append(p2)

        self._subprocs = procs
        self._playing = len(procs) > 0

        # Start loop mask timer if enabled
        if self._playing and main_device:
            self._start_loop_mask_timer(primary_path, main_device)

    def _start_pygame_playback(self):
        """Start pygame-based playback for single default output."""
        # Get EQ-processed paths (or originals if no EQ)
        primary_path, secondary_path = self._get_playback_paths()

        if self.playback_mode == "2ch":
            # 2ch mode: play sum only (vox=left, sub=right)
            pygame.mixer.music.load(primary_path)
            pygame.mixer.music.set_volume((self.vox_volume + self.sub_volume) / 2)
            pygame.mixer.music.play(loops=-1)
            self._playing = True
        else:
            # 4ch mode: play vox_sub as main, instruments as second
            pygame.mixer.music.load(primary_path)
            pygame.mixer.music.set_volume((self.vox_volume + self.sub_volume) / 2)
            pygame.mixer.music.play(loops=-1)
            self._playing = True

            # Play second track if provided (same output in pygame - no multi-device support)
            if secondary_path:
                sound2 = pygame.mixer.Sound(secondary_path)
                channel2 = pygame.mixer.Channel(1)
                avg_vol = (self.surround_left_volume + self.surround_right_volume) / 2
                channel2.set_volume(avg_vol)
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

            # Stop loop mask timer and any playing loop mask
            self._loop_timer_thread = None
            if self._loop_proc:
                try:
                    self._loop_proc.terminate()
                    self._loop_proc.wait(timeout=1)
                except Exception:
                    try:
                        self._loop_proc.kill()
                    except Exception:
                        pass
                self._loop_proc = None
        else:
            pygame.mixer.music.stop()
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

    # --- EQ Methods ---

    def _ensure_eq_processed(self):
        """Process audio files with current EQ/volume settings if needed."""
        if not self._eq_dirty:
            return

        # Clean up old processed files
        self._cleanup_processed_files()

        if self.playback_mode == "2ch":
            # Process sum track with volume and EQ (vox=left, sub=right)
            # Always attempt processing - method returns None if not needed
            if self.sum_path:
                try:
                    self._processed_sum_path = self._process_sum_file()
                    if self._processed_sum_path:
                        print("Processed sum track for playback")
                except Exception as e:
                    print(f"Warning: Could not process sum track: {e}")
                    self._processed_sum_path = None
        else:
            # 4ch mode: process vox_sub (with separate L/R volume and EQ) and instruments
            # Always attempt processing - method returns None if not needed
            if self.vox_sub_path:
                try:
                    self._processed_vox_sub_path = self._process_vox_sub_file()
                    if self._processed_vox_sub_path:
                        print("Processed vox_sub track for playback")
                except Exception as e:
                    print(f"Warning: Could not process vox_sub track: {e}")
                    self._processed_vox_sub_path = None

            # Process instruments (surround) track
            if self.instruments_path and self.surround_eq.has_active_eq():
                try:
                    self._processed_instruments_path = self.surround_eq.process_file(self.instruments_path)
                    print(f"Applied EQ to surround track: {self.surround_eq}")
                except Exception as e:
                    print(f"Warning: Could not apply EQ to surround track: {e}")
                    self._processed_instruments_path = None

        self._eq_dirty = False

    def _cleanup_processed_files(self):
        """Clean up temporary processed files."""
        for path in [self._processed_vox_sub_path, self._processed_instruments_path, self._processed_sum_path]:
            if path and path not in [self.vox_sub_path, self.instruments_path, self.sum_path]:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
        self._processed_vox_sub_path = None
        self._processed_instruments_path = None
        self._processed_sum_path = None

    def _get_playback_paths(self):
        """Get the paths to use for playback (processed or original)."""
        self._ensure_eq_processed()

        if self.playback_mode == "2ch":
            # 2ch mode: return sum path only
            primary_path = self._processed_sum_path or self.sum_path
            return primary_path, None
        else:
            # 4ch mode: return vox_sub and instruments paths
            primary_path = self._processed_vox_sub_path or self.vox_sub_path
            secondary_path = self._processed_instruments_path or self.instruments_path
            return primary_path, secondary_path

    def _get_eq_for_track(self, track: str):
        """Get the EQ processor for a given track name."""
        track_lower = track.lower()
        if track_lower == "vox":
            return self.vox_eq
        elif track_lower == "sub":
            return self.sub_eq
        elif track_lower == "surround":
            return self.surround_eq
        # Legacy support
        elif track_lower == "centre":
            return self.vox_eq
        elif track_lower == "stereo":
            return self.surround_eq
        return None

    def set_eq_band(self, track: str, band: int, freq: float = None, gain: float = None, width: float = None):
        """
        Set EQ parameters for a specific band.

        Args:
            track: "vox", "sub", "surround", or "sum"
            band: Band number 1-4
            freq: Center frequency in Hz (optional)
            gain: Gain in dB, -12 to +12 (optional)
            width: Q factor, 0.1 to 10 (optional)
        """
        eq = self._get_eq_for_track(track)
        if eq is None:
            return

        band_index = band - 1  # Convert to 0-indexed

        if 0 <= band_index < 4:
            eq.set_band(band_index, freq, gain, width)
            self._eq_dirty = True

    def get_eq_band(self, track: str, band: int) -> dict:
        """
        Get EQ parameters for a specific band.

        Args:
            track: "vox", "sub", "surround", or "sum"
            band: Band number 1-4

        Returns:
            Dict with freq, gain, width or empty dict if invalid
        """
        eq = self._get_eq_for_track(track)
        if eq is None:
            return {}

        band_index = band - 1

        if 0 <= band_index < 4:
            b = eq.get_band(band_index)
            if b:
                return {"freq": b.frequency, "gain": b.gain, "width": b.width}
        return {}

    def get_all_eq(self, track: str) -> dict:
        """Get all EQ bands for a track."""
        eq = self._get_eq_for_track(track)
        if eq is None:
            return {}
        return eq.to_dict()

    def apply_eq(self):
        """
        Apply current EQ settings immediately.
        This will stop playback, reprocess files, and restart if was playing.
        """
        was_playing = self._playing
        playback_source = self._playback_source

        if was_playing:
            self.stop(manual=False)

        self._eq_dirty = True
        self._ensure_eq_processed()

        if was_playing:
            self.play_loop(source=playback_source or "manual")
