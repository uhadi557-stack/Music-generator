"""
voice_clone.py — Step 6 of the pipeline.

Real Singing Voice Conversion (Seed-VC on Cloud GPU)
----------------------------------------------------
When a Cloud GPU (Google Colab / Kaggle) is configured:
  Dispatches the generated vocal stem and the user's cleaned voice sample
  to the Cloud GPU /api/convert_voice endpoint running Seed-VC (Zero-Shot
  Singing Voice Conversion with RMVPE pitch tracking).
  Saves the converted singing vocal and returns (cloned_path, "seed-vc").

When Cloud GPU is not configured or offline:
  Passes through the original generated vocal unchanged and returns
  (source_vocal_path, "none").
  Never uses artificial EQ filters or deceptive pseudo-cloning.
"""

import os
import logging
import requests
from typing import Optional

from .config import runtime_config, VARIANTS_DIR

logger = logging.getLogger(__name__)


class VoiceCloningEngine:
    """
    Step 6 — Singing Voice Conversion Engine.

    Delegates zero-shot neural voice conversion (Seed-VC) to the Cloud GPU.
    """

    def __init__(self, cloud_gpu_url: Optional[str] = None) -> None:
        self.cloud_gpu_url = cloud_gpu_url or runtime_config.cloud_gpu_url

    def convert_singing_voice(
        self,
        job_id: str,
        variant_number: int,
        source_vocal_path: str,
        cleaned_voice_sample_path: str,
    ) -> tuple[str, str]:
        """
        Converts the timbre of the source singing vocal to match the user's
        voice sample while preserving pitch, melody, and rhythm.

        Returns
        -------
        (output_path, conversion_method)
            output_path       — path to the converted or passthrough vocal file
            conversion_method — "seed-vc" when converted via GPU, or "none" if skipped
        """
        cloud_url = self.cloud_gpu_url or runtime_config.cloud_gpu_url

        if not cloud_url:
            logger.info(
                "Voice conversion skipped for job %s variant %d: No Cloud GPU URL configured. "
                "Retaining original AI singer vocal.",
                job_id, variant_number,
            )
            return source_vocal_path, "none"

        output_cloned_path = str(VARIANTS_DIR / f"{job_id}_variant_{variant_number}_cloned.wav")

        try:
            logger.info(
                "Calling Cloud GPU for singing voice conversion (job %s, variant %d)...",
                job_id, variant_number,
            )
            endpoint = f"{cloud_url.rstrip('/')}/api/convert_voice"

            with open(source_vocal_path, "rb") as sv_fh, open(cleaned_voice_sample_path, "rb") as vs_fh:
                files = {
                    "source_vocal": ("source_vocal.wav", sv_fh, "audio/wav"),
                    "voice_sample": ("voice_sample.wav", vs_fh, "audio/wav"),
                }
                data = {
                    "job_id": job_id,
                    "variant_number": str(variant_number),
                }
                resp = requests.post(endpoint, files=files, data=data, timeout=120)

            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(output_cloned_path, "wb") as out_fh:
                    out_fh.write(resp.content)
                method = resp.headers.get("x-conversion-method", "seed-vc")
                logger.info(
                    "Singing voice conversion completed successfully via Cloud GPU (%s).",
                    method,
                )
                return output_cloned_path, method
            else:
                logger.warning(
                    "Cloud GPU voice conversion returned HTTP %d. Falling back to original vocal (passthrough).",
                    resp.status_code,
                )
                return source_vocal_path, "none"

        except Exception as exc:
            logger.warning(
                "Cloud GPU voice conversion call failed (%s). Falling back to original vocal (passthrough).",
                exc,
            )
            return source_vocal_path, "none"
