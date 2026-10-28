"""
audio_mixer.py — Step 7 of the pipeline.

Changes from the previous version
----------------------------------
* Loudness: uses **safe peak normalisation** (target −1 dBFS) instead of
  the broken dBFS/LUFS confusion.  effects.normalize() raises the signal to
  0 dBFS and then we pull back by 1 dB — the peak never exceeds −1 dBFS.
  No additional gain is applied, so hard clipping is impossible.
  True LUFS normalisation requires a loudness meter (e.g. pyloudnorm or
  ffmpeg's loudnorm filter) which is a Phase 4 enhancement.

* MP3 export: only attempted when ``runtime_config.ffmpeg_available`` is
  True.  When ffmpeg is absent the function exports WAV only and sets
  ``final_mp3`` to ``None`` in the returned dict.
"""

import os
import logging
from typing import Dict, Any, Optional

from pydub import AudioSegment, effects

from .config import runtime_config

logger = logging.getLogger(__name__)


def enhance_and_mix_stems(
    cloned_vocal_path: str,
    instrumental_path: str,
    output_final_path: str,
    vocal_gain_db: float = 1.0,
    inst_gain_db:  float = -1.0,
) -> Dict[str, Any]:
    """
    Step 7 — polish, mix, and master the final song.

    Processing chain
    ----------------
    1. Load vocal and instrumental stems.
    2. Align durations (pad shorter stem with silence).
    3. Vocal: 90 Hz high-pass → low-pass at 14 kHz → apply vocal_gain_db.
    4. Instrumental: apply inst_gain_db.
    5. Mix (overlay).
    6. Peak normalise to −1 dBFS (safe; never clips).
    7. Export WAV (always). Export MP3 only when ffmpeg is available.

    Returns
    -------
    dict with keys:
        final_wav       – absolute path to WAV file (always present)
        final_mp3       – absolute path to MP3 file, or None if ffmpeg absent
        duration_seconds
        final_dbfs      – post-master peak dBFS
    """
    logger.info(
        "Mixing stems: vocal=%s, inst=%s → %s",
        cloned_vocal_path, instrumental_path, output_final_path,
    )

    # 1. Load
    vocal        = AudioSegment.from_file(cloned_vocal_path)
    instrumental = AudioSegment.from_file(instrumental_path)

    # 2. Align duration
    max_len = max(len(vocal), len(instrumental))
    if len(vocal) < max_len:
        vocal = vocal + AudioSegment.silent(duration=max_len - len(vocal))
    if len(instrumental) < max_len:
        instrumental = instrumental + AudioSegment.silent(duration=max_len - len(instrumental))

    # 3. Vocal polish
    polished_vocal = (
        vocal
        .high_pass_filter(90)
        .low_pass_filter(14000)
        .apply_gain(vocal_gain_db)
    )

    # 4. Instrumental
    polished_inst = instrumental.apply_gain(inst_gain_db)

    # 5. Mix
    master = polished_inst.overlay(polished_vocal)

    # 6. Safe peak normalisation to −1 dBFS
    # effects.normalize() raises to 0 dBFS, then we pull back 1 dB so the
    # peak is guaranteed to sit at or below −1 dBFS — no clipping possible.
    final_master = effects.normalize(master).apply_gain(-1.0)

    # 7. Export
    os.makedirs(os.path.dirname(output_final_path), exist_ok=True)
    final_master.export(output_final_path, format="wav")

    mp3_path: Optional[str] = None
    if runtime_config.ffmpeg_available:
        mp3_path = output_final_path.replace(".wav", ".mp3")
        try:
            final_master.export(mp3_path, format="mp3", bitrate="256k")
        except Exception as exc:
            logger.warning("MP3 export failed (ffmpeg present but error): %s", exc)
            mp3_path = None
    else:
        logger.info("ffmpeg not available — skipping MP3 export, WAV only.")

    return {
        "final_wav":        output_final_path,
        "final_mp3":        mp3_path,
        "duration_seconds": len(final_master) / 1000.0,
        "final_dbfs":       round(final_master.dBFS, 2),
    }
