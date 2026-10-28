"""
acestep_client.py — ACE-Step 1.5 cloud client + demo-tone fallback.

Honesty rules (Phase 1)
-----------------------
* When ``ALLOW_DEMO_FALLBACK`` is False (the default) and the cloud GPU is
  not reachable, the function raises ``CloudUnavailableError`` so the pipeline
  can fail the job with a clear message.  It never silently returns a fake
  result labelled as a real song.

* When ``ALLOW_DEMO_FALLBACK`` is True the demo-tone generator runs, but
  every result dict carries ``provider="demo-tone"`` and ``is_demo=True`` so
  the pipeline and frontend can label it clearly.

* The cloud path still uses the placeholder Colab runner (Phase 3 replaces
  it with a real ACE-Step notebook).  Results from the cloud are labelled
  ``provider="colab_ace_step"`` which maps to ``engine="ace-step"`` in the
  pipeline.
"""

import os
import math
import random
import logging
from typing import List, Dict, Any, Optional

import numpy as np
import requests
from scipy.io import wavfile

from .config import runtime_config, VARIANTS_DIR
from .models import Language, Genre

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception so callers can distinguish "cloud down" from other errors
# ---------------------------------------------------------------------------
class CloudUnavailableError(RuntimeError):
    """Raised when the cloud GPU is required but unreachable."""


# ---------------------------------------------------------------------------
# Genre style prompts
# ---------------------------------------------------------------------------
GENRE_PROMPT_MAP = {
    Genre.GHAZAL:       "Urdu classical ghazal, acoustic harmonium, warm sarangi, gentle tabla theka (keherwa), soulful expressive melodic singing, acoustic studio production, 85 bpm, key of D minor",
    Genre.SUFI:         "Sufi kalam qawwali devotional, rhythmic clapping, dholak and tabla groove, crescendo harmonium melody, soaring passionate vocals, spiritual ambiance, 105 bpm, key of C minor",
    Genre.POP:          "Modern contemporary South Asian pop ballad, acoustic guitar strumming, lush electronic pads, modern trap drum groove, smooth emotive pop vocal melody, crisp radio production, 98 bpm, key of G major",
    Genre.FOLK_ATTAN:   "Traditional Pashto Attan dance folk, driving dhol rhythms, lively zurna, Afghan rubab solo, festive spirited group and solo singing, high energy celebration, 130 bpm, key of A minor",
    Genre.RUBAB_BALLAD: "Melodic Pashto folk ballad, virtuoso Afghan rubab pluckings, gentle framed drum (zerbaghali), sweet nostalgic melancholic vocal melody, mountain acoustic echo, 90 bpm, key of E minor",
    Genre.QAWWALI:      "Energetic Sufi Qawwali, driving handclaps, live harmonium, energetic tabla solo, chorus harmonies, dynamic vocal call and response, 115 bpm, key of D major",
    Genre.LOFI:         "Chill South Asian lo-fi hip hop, dusty vinyl texture, warm Rhodes chords, gentle harmonium tape loops, soft relaxing vocals, 80 bpm, key of F major",
    Genre.ACOUSTIC:     "Acoustic unplugged session, fingerstyle nylon guitar, light shaker, intimate close-mic vocal, gentle melodic storytelling, 88 bpm, key of C major",
}


# ---------------------------------------------------------------------------
# Demo-tone generator
# ---------------------------------------------------------------------------
def _generate_demo_tone(
    genre: Genre,
    duration_seconds: float,
    seed: int,
    output_mix_path: str,
    output_vocal_path: str,
    output_inst_path: str,
    sample_rate: int = 44100,
) -> None:
    """
    Generates a short synthesised audio file clearly intended as a demo.

    This is NOT a real song.  It is a placeholder that proves the pipeline
    runs end-to-end.  All call sites must label the result as ``demo-tone``.
    """
    np.random.seed(seed)
    random.seed(seed)
    total_samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, total_samples, endpoint=False)

    # Root frequency per genre family
    if genre in (Genre.FOLK_ATTAN, Genre.RUBAB_BALLAD):
        root = 220.0
        scale = [root * r for r in (1, 9/8, 6/5, 4/3, 3/2, 8/5, 9/5)]
    elif genre in (Genre.GHAZAL, Genre.SUFI):
        root = 146.83
        scale = [root * r for r in (1, 9/8, 5/4, 4/3, 3/2, 5/3, 15/8)]
    else:
        root = 196.0
        scale = [root * r for r in (1, 9/8, 5/4, 4/3, 3/2, 5/3, 15/8)]

    inst_signal = np.zeros(total_samples, dtype=np.float32)

    # Drone
    inst_signal += 0.25 * np.sin(2 * np.pi * root / 2.0 * t)
    inst_signal += 0.15 * np.sin(2 * np.pi * root / 2.0 * 1.5 * t)

    # Chord progression
    bar_duration = 3.0 + (seed % 3) * 0.5
    chord_indices = [0, (seed + 3) % len(scale), (seed + 4) % len(scale), (seed + 1) % len(scale)]
    num_bars = int(duration_seconds / bar_duration) + 1

    for b in range(num_bars):
        s = int(b * bar_duration * sample_rate)
        e = min(total_samples, int((b + 1) * bar_duration * sample_rate))
        if s >= total_samples:
            break
        cr  = scale[chord_indices[b % len(chord_indices)]]
        tb  = t[s:e]
        wav = (
            0.18 * np.sin(2 * np.pi * cr * tb) +
            0.14 * np.sin(2 * np.pi * cr * 1.25 * tb) +
            0.12 * np.sin(2 * np.pi * cr * 1.5 * tb)
        )
        env = np.ones_like(tb)
        rl  = min(len(env) // 4, int(0.2 * sample_rate))
        if rl > 0:
            env[:rl] = np.linspace(0, 1, rl)
            env[-rl:] = np.linspace(1, 0, rl)
        inst_signal[s:e] += (wav * env).astype(np.float32)

    # Simple beat
    beat_interval = 0.5 if genre == Genre.FOLK_ATTAN else 0.75
    for k in range(int(duration_seconds / beat_interval)):
        bs = int(k * beat_interval * sample_rate)
        bl = int(0.12 * sample_rate)
        if bs + bl < total_samples:
            decay = np.exp(-np.linspace(0, 6, bl))
            drum  = np.sin(2 * np.pi * 65.0 * np.linspace(0, 0.12, bl)) * decay * 0.35
            inst_signal[bs:bs + bl] += drum.astype(np.float32)

    # Vocal melody
    vocal_signal = np.zeros(total_samples, dtype=np.float32)
    vocal_notes  = [scale[i % len(scale)] * 2.0 for i in range(len(scale))]
    note_dur     = 0.6 + (seed % 4) * 0.15
    num_notes    = int(duration_seconds / note_dur)

    for n in range(num_notes):
        ns = int(n * note_dur * sample_rate)
        ne = min(total_samples, int((n + 1) * note_dur * sample_rate))
        if ns >= total_samples:
            break
        nf = vocal_notes[(n * (seed + 1) + 2) % len(vocal_notes)]
        tn = t[ns:ne]
        vib = 1.0 + 0.015 * np.sin(2 * np.pi * 5.5 * tn)
        f0  = nf * vib
        vw  = (
            0.35 * np.sin(2 * np.pi * f0 * tn) +
            0.20 * np.sin(2 * np.pi * 2 * f0 * tn) +
            0.12 * np.sin(2 * np.pi * 3 * f0 * tn) +
            0.08 * np.sin(2 * np.pi * 4 * f0 * tn)
        )
        nenv = np.ones_like(tn)
        fade = min(len(nenv) // 4, int(0.08 * sample_rate))
        if fade > 0:
            nenv[:fade]  = np.linspace(0, 1, fade)
            nenv[-fade:] = np.linspace(1, 0, fade)
        vocal_signal[ns:ne] += (vw * nenv).astype(np.float32)

    # Normalise
    def _norm(sig, target=0.80):
        mx = np.max(np.abs(sig))
        return (sig / mx * target) if mx > 0 else sig

    inst_signal  = _norm(inst_signal,  0.75)
    vocal_signal = _norm(vocal_signal, 0.85)
    mix_signal   = _norm(inst_signal * 0.65 + vocal_signal * 0.8, 0.85)

    os.makedirs(os.path.dirname(output_mix_path), exist_ok=True)
    wavfile.write(output_mix_path,   sample_rate, (mix_signal   * 32767).astype(np.int16))
    wavfile.write(output_vocal_path, sample_rate, (vocal_signal * 32767).astype(np.int16))
    wavfile.write(output_inst_path,  sample_rate, (inst_signal  * 32767).astype(np.int16))


# ---------------------------------------------------------------------------
# Cloud client
# ---------------------------------------------------------------------------
class AceStepClient:
    """
    Client for ACE-Step 1.5 music generation.

    Behaviour
    ---------
    * cloud reachable         → sends request, labels result ``ace-step``
    * cloud unreachable + ALLOW_DEMO_FALLBACK=False → raises CloudUnavailableError
    * cloud unreachable + ALLOW_DEMO_FALLBACK=True  → generates demo-tone,
                                                      labels result ``demo-tone``
    """

    def __init__(self, cloud_gpu_url: Optional[str] = None) -> None:
        self.cloud_gpu_url = cloud_gpu_url or runtime_config.cloud_gpu_url

    def _check_cloud(self) -> tuple[bool, str]:
        """Returns (available: bool, reason: str)."""
        if not self.cloud_gpu_url:
            return False, "no cloud GPU URL configured"
        try:
            resp = requests.get(
                f"{self.cloud_gpu_url.rstrip('/')}/health",
                timeout=5,
            )
            if resp.status_code == 200:
                return True, "ok"
            return False, f"health endpoint returned HTTP {resp.status_code}"
        except Exception as exc:
            return False, str(exc)

    def _call_cloud_generation(
        self,
        base_url: str,
        style_prompt: str,
        sung_lyrics: str,
        language: Language,
        seed: int,
        duration_seconds: float,
        mix_path: str,
        vocal_path: str,
        inst_path: str,
    ) -> bool:
        """
        Attempts cloud generation using:
        1. Official ACE-Step API: POST /release_task -> poll POST /query_result -> GET /v1/audio
        2. Direct runner endpoint: POST /api/generate
        """
        import time

        # Attempt 1: Official ACE-Step REST API (/release_task)
        try:
            rel_payload = {
                "prompt": style_prompt,
                "lyrics": sung_lyrics,
                "audio_duration": duration_seconds,
                "seed": seed,
                "audio_format": "wav",
                "vocal_language": "ur" if language == Language.URDU else "ps",
                "thinking": False,
                "inference_steps": 8,
            }
            rel_resp = requests.post(f"{base_url}/release_task", json=rel_payload, timeout=20)
            if rel_resp.status_code == 200:
                rel_json = rel_resp.json()
                task_id = (rel_json.get("data") or {}).get("task_id") or rel_json.get("task_id")
                if task_id:
                    logger.info("Official ACE-Step task submitted: task_id=%s, polling...", task_id)
                    poll_start = time.time()
                    while time.time() - poll_start < 300:
                        time.sleep(2)
                        q_resp = requests.post(f"{base_url}/query_result", json={"task_id_list": [task_id]}, timeout=15)
                        if q_resp.status_code == 200:
                            q_json = q_resp.json()
                            items = q_json.get("data", [])
                            if items:
                                task_status = items[0].get("status")
                                if task_status == 1:  # Succeeded
                                    res = items[0].get("result") or {}
                                    audio_rel = (res.get("file") or res.get("audio_url")) if isinstance(res, dict) else res
                                    vocal_rel = res.get("vocal_url") if isinstance(res, dict) else None
                                    inst_rel  = res.get("inst_url")  if isinstance(res, dict) else None

                                    if audio_rel:
                                        full_url = audio_rel if audio_rel.startswith("http") else f"{base_url}{'/' if not audio_rel.startswith('/') else ''}{audio_rel}"
                                        audio_data = requests.get(full_url, timeout=60).content
                                        with open(mix_path, "wb") as f:
                                            f.write(audio_data)

                                        # Vocal stem
                                        if vocal_rel:
                                            v_url = vocal_rel if vocal_rel.startswith("http") else f"{base_url}{'/' if not vocal_rel.startswith('/') else ''}{vocal_rel}"
                                            with open(vocal_path, "wb") as f:
                                                f.write(requests.get(v_url, timeout=60).content)
                                        else:
                                            with open(vocal_path, "wb") as f:
                                                f.write(audio_data)

                                        # Instrumental stem
                                        if inst_rel:
                                            i_url = inst_rel if inst_rel.startswith("http") else f"{base_url}{'/' if not inst_rel.startswith('/') else ''}{inst_rel}"
                                            with open(inst_path, "wb") as f:
                                                f.write(requests.get(i_url, timeout=60).content)
                                        else:
                                            with open(inst_path, "wb") as f:
                                                f.write(audio_data)
                                        return True
                                elif task_status == 2:  # Failed
                                    logger.error("Official ACE-Step task %s reported failure", task_id)
                                    return False
        except Exception as exc:
            logger.debug("Official ACE-Step /release_task unavailable: %s", exc)

        # Attempt 2: Direct /api/generate endpoint
        try:
            payload = {
                "lyrics": sung_lyrics,
                "style_prompt": style_prompt,
                "language": language.value,
                "seed": seed,
                "duration": duration_seconds,
                "split_stems": True,
            }
            resp = requests.post(f"{base_url}/api/generate", json=payload, timeout=240)
            if resp.status_code == 200:
                data = resp.json()
                for url_key, local_path in (
                    ("audio_url", mix_path),
                    ("vocal_url", vocal_path),
                    ("inst_url", inst_path),
                ):
                    u = data.get(url_key)
                    if u:
                        full_u = u if u.startswith("http") else f"{base_url}{'/' if not u.startswith('/') else ''}{u}"
                        content = requests.get(full_u, timeout=60).content
                        with open(local_path, "wb") as fh:
                            fh.write(content)
                    else:
                        if os.path.exists(mix_path) and not os.path.exists(local_path):
                            import shutil
                            shutil.copyfile(mix_path, local_path)
                return True
            else:
                logger.error("Direct /api/generate returned HTTP %d", resp.status_code)
                return False
        except Exception as exc:
            logger.error("Direct /api/generate call failed: %s", exc)
            return False

    def generate_song_variants(
        self,
        job_id: str,
        language: Language,
        genre: Genre,
        theme: str,
        sung_lyrics: str,
        variant_count: int = 1,
        duration_seconds: float = 60.0,
    ) -> List[Dict[str, Any]]:
        """
        Step 4: generate 1–3 song variants (defaults to 60.0s).

        Each result dict contains:
            variant_number, seed, mix_path, vocal_path, inst_path,
            duration_seconds, provider, is_demo
        """
        style_prompt = GENRE_PROMPT_MAP.get(genre, f"{genre.value} song in {language.value}")
        results: List[Dict[str, Any]] = []
        base_seed = random.randint(10000, 99999)

        cloud_ok, cloud_reason = self._check_cloud()
        logger.info(
            "ACE-Step generation: cloud_available=%s, reason=%s, variant_count=%d",
            cloud_ok, cloud_reason, variant_count,
        )

        for i in range(1, variant_count + 1):
            seed           = base_seed + (i * 37)
            variant_prefix = f"{job_id}_variant_{i}"
            mix_path       = str(VARIANTS_DIR / f"{variant_prefix}_mix.wav")
            vocal_path     = str(VARIANTS_DIR / f"{variant_prefix}_vocal.wav")
            inst_path      = str(VARIANTS_DIR / f"{variant_prefix}_inst.wav")

            # ----------------------------------------------------------------
            # Cloud path
            # ----------------------------------------------------------------
            if cloud_ok:
                logger.info("Calling Cloud GPU for variant %d (seed %d)", i, seed)
                base_url = self.cloud_gpu_url.rstrip("/")
                success = self._call_cloud_generation(
                    base_url=base_url,
                    style_prompt=style_prompt,
                    sung_lyrics=sung_lyrics,
                    language=language,
                    seed=seed,
                    duration_seconds=duration_seconds,
                    mix_path=mix_path,
                    vocal_path=vocal_path,
                    inst_path=inst_path,
                )
                if success:
                    results.append({
                        "variant_number":   i,
                        "seed":             seed,
                        "mix_path":         mix_path,
                        "vocal_path":       vocal_path,
                        "inst_path":        inst_path,
                        "duration_seconds": duration_seconds,
                        "provider":         "colab_ace_step",
                        "is_demo":          False,
                    })
                    continue
                else:
                    cloud_ok = False
                    cloud_reason = "Generation call failed on Cloud GPU"

            # ----------------------------------------------------------------
            # No cloud — check demo fallback setting
            # ----------------------------------------------------------------
            if not runtime_config.allow_demo_fallback:
                raise CloudUnavailableError(
                    f"Cloud GPU not reachable: {cloud_reason}. "
                    "Set ALLOW_DEMO_FALLBACK=true in your .env to generate a "
                    "labelled demo-tone track instead."
                )

            # ALLOW_DEMO_FALLBACK=True — generate demo tone, label it clearly
            logger.info(
                "ALLOW_DEMO_FALLBACK=True — generating demo-tone for variant %d "
                "(NOT a real song, genre=%s, seed=%d)",
                i, genre.value, seed,
            )
            _generate_demo_tone(
                genre=genre,
                duration_seconds=duration_seconds,
                seed=seed,
                output_mix_path=mix_path,
                output_vocal_path=vocal_path,
                output_inst_path=inst_path,
            )
            results.append({
                "variant_number":   i,
                "seed":             seed,
                "mix_path":         mix_path,
                "vocal_path":       vocal_path,
                "inst_path":        inst_path,
                "duration_seconds": duration_seconds,
                "provider":         "demo-tone",
                "is_demo":          True,
            })

        return results
