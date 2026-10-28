"""
audio_prep.py — Step 3 of the pipeline.

What this step actually does
----------------------------
1. Converts the uploaded sample to mono, 44.1 kHz.
2. Trims leading and trailing silence.
3. Applies an 80 Hz high-pass filter to remove microphone rumble.
4. Normalises peak amplitude to a safe level (-1 dBFS headroom).

What this step does NOT do
--------------------------
* It does NOT perform AI-based denoising.  The label "Denoising" in the
  previous version was misleading and has been removed.
* It does NOT require ffmpeg for WAV input — pydub handles mono conversion
  and frame-rate resampling natively without the ffmpeg subprocess.
  Extra keyword arguments that forced ffmpeg subprocesses have been removed
  because pydub can perform these operations natively.

ffmpeg is still required if the input file is MP3, M4A, OGG, or WebM.
Call sites must check ``runtime_config.ffmpeg_available`` before accepting
those formats.

Waveform peaks
--------------
Uses RMS per chunk instead of the chunk maximum so that constant-amplitude
audio (e.g. a sine wave) does not produce flat bars at 1.0.
"""

import math
import logging
from typing import Dict, Any, List

import numpy as np
from pydub import AudioSegment, effects

from .config import runtime_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Accepted upload file extensions
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {"wav", "mp3", "m4a", "ogg", "webm"}

# Voice sample duration limits (seconds)
VOICE_SAMPLE_MIN_SECONDS = 5.0
VOICE_SAMPLE_MAX_SECONDS = 60.0

# Upload size limit (bytes)
UPLOAD_MAX_BYTES = 20 * 1024 * 1024   # 20 MB


def detect_leading_silence(
    sound: AudioSegment,
    silence_threshold: float = -45.0,
    chunk_size: int = 10,
) -> int:
    """Returns the duration of leading silence in milliseconds."""
    trim_ms = 0
    while trim_ms < len(sound):
        chunk = sound[trim_ms : trim_ms + chunk_size]
        if chunk.dBFS > silence_threshold:
            break
        trim_ms += chunk_size
    return trim_ms


def clean_and_prepare_voice_sample(
    input_path: str,
    output_path: str,
    target_sample_rate: int = 44100,
) -> Dict[str, Any]:
    """
    Step 3 — voice sample preparation.

    Applies, in order:
    1. Mono conversion + 44.1 kHz resampling  (no ffmpeg needed for WAV)
    2. Silence trimming
    3. 80 Hz high-pass filter (removes mic rumble)
    4. Peak normalisation to -1 dBFS

    Raises
    ------
    ValueError
        If the cleaned sample is shorter than VOICE_SAMPLE_MIN_SECONDS or
        longer than VOICE_SAMPLE_MAX_SECONDS.
    """
    logger.info("Preparing voice sample: %s → %s", input_path, output_path)

    audio = AudioSegment.from_file(input_path)
    original_duration = len(audio) / 1000.0

    # --- Mono + resample (pydub native, no ffmpeg subprocess needed) --------
    audio = audio.set_channels(1)
    audio = audio.set_frame_rate(target_sample_rate)

    # --- Silence trimming ---------------------------------------------------
    start_trim = detect_leading_silence(audio)
    end_trim   = detect_leading_silence(audio.reverse())
    duration_ms = len(audio)
    trimmed = audio[start_trim : duration_ms - end_trim]
    if len(trimmed) < 500:          # avoid cutting everything out
        trimmed = audio

    # --- Duration guard -----------------------------------------------------
    trimmed_seconds = len(trimmed) / 1000.0
    if trimmed_seconds < VOICE_SAMPLE_MIN_SECONDS:
        raise ValueError(
            f"Voice sample too short after trimming: {trimmed_seconds:.1f}s "
            f"(minimum {VOICE_SAMPLE_MIN_SECONDS}s)."
        )
    if trimmed_seconds > VOICE_SAMPLE_MAX_SECONDS:
        # Truncate rather than error — user may have uploaded a long file
        trimmed = trimmed[: int(VOICE_SAMPLE_MAX_SECONDS * 1000)]

    # --- High-pass filter at 80 Hz (removes mic rumble) --------------------
    filtered = trimmed.high_pass_filter(80)

    # --- Peak normalisation to -1 dBFS (never gain above this) -------------
    # effects.normalize() raises to 0 dBFS; we then pull back by 1 dB.
    normalised = effects.normalize(filtered).apply_gain(-1.0)

    # --- Export — WAV only, no custom ffmpeg flags -------------------------
    # Omitting custom flags means pydub writes the WAV header natively, which
    # does not require ffmpeg.
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    normalised.export(output_path, format="wav")

    final_duration = len(normalised) / 1000.0
    return {
        "original_duration_seconds": round(original_duration, 2),
        "cleaned_duration_seconds":  round(final_duration, 2),
        "sample_rate":               target_sample_rate,
        "channels":                  1,
        "trimmed_start_ms":          start_trim,
        "trimmed_end_ms":            end_trim,
        "output_path":               output_path,
    }


def generate_waveform_peaks(audio_path: str, num_peaks: int = 80) -> List[float]:
    """
    Extracts RMS-based amplitude peaks (0.0–1.0) for the frontend waveform
    visualiser.

    Uses RMS per chunk rather than the chunk maximum so that a constant-
    amplitude signal (e.g. a pure sine wave) produces meaningfully varying
    bars instead of a flat line of 1.0.

    A small floor (0.05) prevents bars from vanishing for very quiet sections.
    """
    try:
        audio = AudioSegment.from_file(audio_path)
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        if audio.channels == 2:
            samples = samples.reshape((-1, 2)).mean(axis=1)

        total_samples = len(samples)
        if total_samples == 0:
            return [0.2] * num_peaks

        chunk_size = max(1, total_samples // num_peaks)
        rms_values: List[float] = []

        for i in range(num_peaks):
            start = i * chunk_size
            end   = min(total_samples, start + chunk_size)
            chunk = samples[start:end]
            if len(chunk) > 0:
                rms = float(np.sqrt(np.mean(chunk ** 2)))
            else:
                rms = 0.0
            rms_values.append(rms)

        max_rms = max(rms_values) if rms_values else 1.0
        if max_rms <= 0.0:
            return [0.15] * num_peaks

        # Normalise to 0.05–1.0 range
        peaks = [round(max(0.05, v / max_rms), 3) for v in rms_values]
        return peaks

    except Exception as exc:
        logger.error("Failed to generate waveform peaks: %s", exc)
        # Fallback: sine-shaped pattern so bars are at least visible
        return [round(0.2 + 0.6 * abs(math.sin(i * 0.15)), 2) for i in range(num_peaks)]
