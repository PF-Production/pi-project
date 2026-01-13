"""
Parametric EQ Processor for audio tracks.
Uses scipy for IIR biquad filter implementation.
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy import signal
from scipy.io import wavfile


@dataclass
class EQBand:
    """Represents a single parametric EQ band."""

    frequency: float  # Center frequency in Hz
    gain: float  # Gain in dB (-12 to +12)
    width: float  # Q factor (0.1 to 10, higher = narrower)

    def __post_init__(self):
        # Clamp values to valid ranges
        self.frequency = max(20.0, min(20000.0, float(self.frequency)))
        self.gain = max(-12.0, min(12.0, float(self.gain)))
        self.width = max(0.1, min(10.0, float(self.width)))

    def is_active(self) -> bool:
        """Returns True if this band has any effect (non-zero gain)."""
        return abs(self.gain) > 0.01


class EQProcessor:
    """4-band parametric EQ processor for WAV files."""

    def __init__(self, bands: Optional[list[EQBand]] = None):
        """
        Initialize EQ processor with up to 4 bands.

        Args:
            bands: List of EQBand objects (up to 4). Defaults to flat EQ.
        """
        self.bands = bands or [
            EQBand(100, 0, 1.0),
            EQBand(500, 0, 1.0),
            EQBand(2000, 0, 1.0),
            EQBand(8000, 0, 1.0),
        ]
        # Ensure we have exactly 4 bands
        while len(self.bands) < 4:
            self.bands.append(EQBand(1000, 0, 1.0))
        self.bands = self.bands[:4]

    def set_band(self, band_index: int, frequency: float = None, gain: float = None, width: float = None):
        """
        Update a specific EQ band.

        Args:
            band_index: 0-3 (band 1-4)
            frequency: Center frequency in Hz (optional)
            gain: Gain in dB (optional)
            width: Q factor (optional)
        """
        if 0 <= band_index < 4:
            band = self.bands[band_index]
            if frequency is not None:
                band.frequency = max(20.0, min(20000.0, float(frequency)))
            if gain is not None:
                band.gain = max(-12.0, min(12.0, float(gain)))
            if width is not None:
                band.width = max(0.1, min(10.0, float(width)))

    def get_band(self, band_index: int) -> Optional[EQBand]:
        """Get a specific EQ band."""
        if 0 <= band_index < 4:
            return self.bands[band_index]
        return None

    def _design_peaking_filter(self, freq: float, gain_db: float, q: float, sample_rate: int):
        """
        Design a peaking (parametric) EQ filter using biquad coefficients.

        Returns (b, a) filter coefficients.
        """
        A = 10 ** (gain_db / 40.0)  # Amplitude
        omega = 2 * np.pi * freq / sample_rate
        sin_omega = np.sin(omega)
        cos_omega = np.cos(omega)
        alpha = sin_omega / (2 * q)

        b0 = 1 + alpha * A
        b1 = -2 * cos_omega
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * cos_omega
        a2 = 1 - alpha / A

        # Normalize by a0
        b = np.array([b0 / a0, b1 / a0, b2 / a0])
        a = np.array([1.0, a1 / a0, a2 / a0])

        return b, a

    def process_audio(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Apply the parametric EQ to audio data.

        Args:
            audio_data: NumPy array of audio samples (mono or stereo)
            sample_rate: Sample rate in Hz

        Returns:
            Processed audio data as NumPy array
        """
        # Convert to float64 for processing
        if audio_data.dtype == np.int16:
            audio_float = audio_data.astype(np.float64) / 32768.0
        elif audio_data.dtype == np.int32:
            audio_float = audio_data.astype(np.float64) / 2147483648.0
        else:
            audio_float = audio_data.astype(np.float64)

        processed = audio_float.copy()

        # Apply each active band
        for band in self.bands:
            if band.is_active():
                b, a = self._design_peaking_filter(band.frequency, band.gain, band.width, sample_rate)

                # Handle mono and stereo
                if len(processed.shape) == 1:
                    processed = signal.lfilter(b, a, processed)
                else:
                    # Process each channel
                    for ch in range(processed.shape[1]):
                        processed[:, ch] = signal.lfilter(b, a, processed[:, ch])

        # Soft clip to prevent harsh distortion
        processed = np.tanh(processed)

        # Convert back to original format
        if audio_data.dtype == np.int16:
            processed = (processed * 32767).astype(np.int16)
        elif audio_data.dtype == np.int32:
            processed = (processed * 2147483647).astype(np.int32)

        return processed

    def process_file(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Process a WAV file with the EQ settings.

        Args:
            input_path: Path to input WAV file
            output_path: Path for output file (default: creates temp file)

        Returns:
            Path to the processed file
        """
        # Check if any EQ is actually active
        if not any(band.is_active() for band in self.bands):
            # No processing needed, return original
            return input_path

        # Read input file
        sample_rate, audio_data = wavfile.read(input_path)

        # Process audio
        processed = self.process_audio(audio_data, sample_rate)

        # Determine output path
        if output_path is None:
            # Create temp file with same extension
            suffix = Path(input_path).suffix
            fd, output_path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)

        # Write output
        wavfile.write(output_path, sample_rate, processed)

        return output_path

    def has_active_eq(self) -> bool:
        """Check if any EQ band is active (non-zero gain)."""
        return any(band.is_active() for band in self.bands)

    def to_dict(self) -> dict:
        """Export EQ settings as dictionary."""
        result = {}
        for i, band in enumerate(self.bands, 1):
            result[f"band{i}"] = {"freq": band.frequency, "gain": band.gain, "width": band.width}
        return result

    def __repr__(self):
        bands_str = ", ".join(
            f"B{i + 1}({b.frequency:.0f}Hz, {b.gain:+.1f}dB, Q{b.width:.1f})" for i, b in enumerate(self.bands)
        )
        return f"EQProcessor({bands_str})"


def load_eq_from_env(track: str = "centre") -> EQProcessor:
    """
    Load EQ settings from environment variables.

    Args:
        track: "centre" or "stereo"

    Returns:
        Configured EQProcessor
    """
    track_upper = track.upper()
    bands = []

    for i in range(1, 5):
        freq = float(os.getenv(f"EQ_{track_upper}_BAND{i}_FREQ", 1000))
        gain = float(os.getenv(f"EQ_{track_upper}_BAND{i}_GAIN", 0))
        width = float(os.getenv(f"EQ_{track_upper}_BAND{i}_WIDTH", 1.0))
        bands.append(EQBand(freq, gain, width))

    return EQProcessor(bands)


def save_eq_to_env_dict(eq: EQProcessor, track: str = "centre") -> dict:
    """
    Generate environment variable dict for EQ settings.

    Args:
        eq: EQProcessor instance
        track: "centre" or "stereo"

    Returns:
        Dictionary of env var name -> value
    """
    track_upper = track.upper()
    result = {}

    for i, band in enumerate(eq.bands, 1):
        result[f"EQ_{track_upper}_BAND{i}_FREQ"] = f"{band.frequency:.0f}"
        result[f"EQ_{track_upper}_BAND{i}_GAIN"] = f"{band.gain:.1f}"
        result[f"EQ_{track_upper}_BAND{i}_WIDTH"] = f"{band.width:.1f}"

    return result
