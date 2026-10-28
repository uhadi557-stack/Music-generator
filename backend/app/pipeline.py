"""
pipeline.py — 8-step song generation pipeline.

Phase 1 changes
---------------
* All artificial ``asyncio.sleep`` calls removed.  Every await now does real
  work or is a genuine notify-only await.
* Step 3 description matches what actually happens (high-pass filter +
  normalisation, not "denoising").
* Step 5 description is honest: stems come from the generator, no separate
  stem-separation library is available yet.
* Step 6 reports ``voice_conversion`` as ``"none"`` until Phase 4.
* ``VariantInfo`` is populated with ``engine``, ``voice_conversion``, and
  ``is_demo`` fields.
* ``lyrics_source`` is propagated from the lyrics step.
* When ``CloudUnavailableError`` is raised the job fails with a clear message
  instead of silently falling back.
"""

import os
import time
import asyncio
import logging
from typing import Dict, Any, Optional, AsyncGenerator, List
import json

from .models import (
    Language, Genre, JobStep, STEP_NAMES, JobState, VariantInfo,
    LyricsResponse,
)
from .config import UPLOADS_DIR, PROCESSED_DIR, VARIANTS_DIR
from .lyrics import generate_lyrics
from .audio_prep import clean_and_prepare_voice_sample, generate_waveform_peaks
from .acestep_client import AceStepClient, CloudUnavailableError
from .voice_clone import VoiceCloningEngine
from .audio_mixer import enhance_and_mix_stems

logger = logging.getLogger(__name__)

# In-memory store of active and completed jobs
JOBS_STORE:    Dict[str, JobState]            = {}
JOB_LISTENERS: Dict[str, List[asyncio.Queue]] = {}


def get_job(job_id: str) -> Optional[JobState]:
    return JOBS_STORE.get(job_id)


async def notify_listeners(job_id: str, event_type: str, payload: Dict[str, Any]) -> None:
    listeners = JOB_LISTENERS.get(job_id, [])
    msg = f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
    for queue in listeners:
        await queue.put(msg)


async def subscribe_job_events(job_id: str) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue = asyncio.Queue()
    JOB_LISTENERS.setdefault(job_id, []).append(queue)
    try:
        job = JOBS_STORE.get(job_id)
        if job:
            yield f"event: step_update\ndata: {json.dumps(job.model_dump())}\n\n"
        while True:
            msg = await queue.get()
            yield msg
            current = JOBS_STORE.get(job_id)
            if current and current.status in ("completed", "failed"):
                if queue.empty():
                    break
    finally:
        lst = JOB_LISTENERS.get(job_id, [])
        if queue in lst:
            lst.remove(queue)


def create_song_job(
    job_id: str,
    language: Language,
    theme: str,
    genre: Genre,
    number_of_variants: int,
    voice_sample_path: Optional[str] = None,
    custom_stanzas:    Optional[str] = None,
) -> JobState:
    now = time.time()
    job = JobState(
        job_id=job_id,
        language=language,
        theme=theme,
        genre=genre,
        display_lyrics=custom_stanzas or "Generating...",
        sung_lyrics=None,
        lyrics_source="unknown",
        number_of_variants=number_of_variants,  # already clamped by caller
        current_step=JobStep.STEP_1_INPUT,
        step_name=STEP_NAMES[JobStep.STEP_1_INPUT],
        step_progress=10.0,
        status="processing",
        message="Job created and parameters validated.",
        voice_sample_path=voice_sample_path,
        created_at=now,
        updated_at=now,
    )
    JOBS_STORE[job_id] = job
    return job


async def run_pipeline(
    job_id: str,
    custom_stanzas: Optional[str] = None,
    dialect: str = "peshawar",
) -> None:
    """Executes the full 8-step pipeline asynchronously."""
    job = JOBS_STORE.get(job_id)
    if not job:
        return

    def _update(step: JobStep, progress: float, message: str) -> None:
        job.current_step  = step
        job.step_name     = STEP_NAMES[step]
        job.step_progress = progress
        job.message       = message
        job.updated_at    = time.time()

    try:
        # ------------------------------------------------------------------
        # STEP 1 — Input validated
        # ------------------------------------------------------------------
        _update(
            JobStep.STEP_1_INPUT, 12.0,
            "User inputs validated. Voice sample queued for audio engine."
            if job.voice_sample_path
            else "User inputs validated. No voice sample — AI singer vocals will be used.",
        )
        await notify_listeners(job_id, "step_update", job.model_dump())

        # ------------------------------------------------------------------
        # STEP 2 — Lyrics
        # ------------------------------------------------------------------
        _update(
            JobStep.STEP_2_LYRICS, 25.0,
            f"Composing {job.language.value.title()} lyrics (Verse/Chorus structure).",
        )
        await notify_listeners(job_id, "step_update", job.model_dump())

        lyrics_res: LyricsResponse = await asyncio.to_thread(
            generate_lyrics,
            language=job.language,
            theme=job.theme,
            genre=job.genre,
            custom_stanzas=custom_stanzas,
            dialect=dialect,
        )
        job.display_lyrics  = lyrics_res.display_lyrics
        job.sung_lyrics     = lyrics_res.sung_lyrics
        job.lyrics_source   = lyrics_res.source
        await notify_listeners(job_id, "step_update", job.model_dump())

        # ------------------------------------------------------------------
        # STEP 3 — Prepare voice sample (if provided)
        # ------------------------------------------------------------------
        _update(JobStep.STEP_3_PREPARE_VOICE, 40.0, "")
        if job.voice_sample_path:
            job.message = (
                "Applying 80 Hz high-pass filter and peak normalisation to voice sample."
            )
            job.updated_at = time.time()
            await notify_listeners(job_id, "step_update", job.model_dump())

            cleaned_sample_path = str(PROCESSED_DIR / f"{job_id}_cleaned_voice.wav")
            prep_result = await asyncio.to_thread(
                clean_and_prepare_voice_sample,
                input_path=job.voice_sample_path,
                output_path=cleaned_sample_path,
            )
            job.cleaned_voice_sample_path = cleaned_sample_path
            job.message = (
                f"Voice sample prepared: {prep_result['cleaned_duration_seconds']}s, "
                "80 Hz HP filtered and normalised to −1 dBFS."
            )
        else:
            job.cleaned_voice_sample_path = None
            job.message = "No voice sample — AI singer vocals will be used as-is."
            job.updated_at = time.time()

        await notify_listeners(job_id, "step_update", job.model_dump())

        # ------------------------------------------------------------------
        # STEP 4 — Generate song variants via ACE-Step
        # ------------------------------------------------------------------
        _update(
            JobStep.STEP_4_GENERATE_SONG, 55.0,
            f"Requesting {job.number_of_variants} variant(s) from ACE-Step 1.5 "
            f"(cloud GPU). This may take several minutes.",
        )
        await notify_listeners(job_id, "step_update", job.model_dump())

        acestep_client = AceStepClient()
        # CloudUnavailableError propagates to the except block below if
        # ALLOW_DEMO_FALLBACK=False — the job fails with a clear message.
        generated_variants: List[Dict[str, Any]] = await asyncio.to_thread(
            acestep_client.generate_song_variants,
            job_id=job_id,
            language=job.language,
            genre=job.genre,
            theme=job.theme,
            sung_lyrics=job.sung_lyrics,
            variant_count=job.number_of_variants,
        )

        # ------------------------------------------------------------------
        # STEPS 5, 6, 7 — per variant
        # ------------------------------------------------------------------
        voice_cloner: VoiceCloningEngine = VoiceCloningEngine()
        finished_variants: List[VariantInfo] = []

        for item in generated_variants:
            var_num  = item["variant_number"]
            seed     = item["seed"]
            provider = item["provider"]
            is_demo  = item.get("is_demo", False)

            # STEP 5 — Stem status
            # Real stem separation is not available in Phase 1.
            # When the ACE-Step cloud runner provides separate vocal/instrumental
            # files those are used directly.  Until then the mix is used for both.
            _update(
                JobStep.STEP_5_SPLIT_VOCALS,
                68.0 + (var_num - 1) * 6.0,
                f"Variant {var_num}: stems provided by generator "
                f"(no separate stem-separation library in Phase 1).",
            )
            await notify_listeners(job_id, "step_update", job.model_dump())

            # STEP 6 — Voice conversion
            if job.cleaned_voice_sample_path:
                _update(
                    JobStep.STEP_6_CLONE_VOICE,
                    75.0 + (var_num - 1) * 5.0,
                    f"Variant {var_num}: singing voice conversion (Seed-VC)...",
                )
                await notify_listeners(job_id, "step_update", job.model_dump())

                cloned_vocal_path, voice_conv_method = await asyncio.to_thread(
                    voice_cloner.convert_singing_voice,
                    job_id=job_id,
                    variant_number=var_num,
                    source_vocal_path=item["vocal_path"],
                    cleaned_voice_sample_path=job.cleaned_voice_sample_path,
                )

                if voice_conv_method != "none":
                    _update(
                        JobStep.STEP_6_CLONE_VOICE,
                        78.0 + (var_num - 1) * 5.0,
                        f"Variant {var_num}: singing vocal converted to user voice ({voice_conv_method}).",
                    )
                else:
                    _update(
                        JobStep.STEP_6_CLONE_VOICE,
                        78.0 + (var_num - 1) * 5.0,
                        f"Variant {var_num}: voice conversion skipped (Cloud GPU offline). Original vocal retained.",
                    )
                await notify_listeners(job_id, "step_update", job.model_dump())
            else:
                cloned_vocal_path = item["vocal_path"]
                voice_conv_method = "none"
                _update(
                    JobStep.STEP_6_CLONE_VOICE,
                    75.0 + (var_num - 1) * 5.0,
                    f"Variant {var_num}: no user voice sample provided — using native AI singer vocal.",
                )
                await notify_listeners(job_id, "step_update", job.model_dump())

            # STEP 7 — Enhance & mix
            _update(
                JobStep.STEP_7_ENHANCE_MIX,
                85.0 + (var_num - 1) * 4.0,
                f"Variant {var_num}: EQ, peak normalisation (−1 dBFS), and final mix.",
            )
            await notify_listeners(job_id, "step_update", job.model_dump())

            final_master_path = str(VARIANTS_DIR / f"{job_id}_variant_{var_num}_master.wav")
            mix_result = await asyncio.to_thread(
                enhance_and_mix_stems,
                cloned_vocal_path=cloned_vocal_path,
                instrumental_path=item["inst_path"],
                output_final_path=final_master_path,
            )

            # Waveform peaks
            peaks = await asyncio.to_thread(generate_waveform_peaks, final_master_path, 80)

            demo_suffix = " [DEMO TONE — not a real song]" if is_demo else ""
            variant_info = VariantInfo(
                variant_number   = var_num,
                title            = (
                    f"{job.language.value.title()} "
                    f"{job.genre.value.replace('_', ' ').title()} "
                    f"— Variant {var_num}{demo_suffix}"
                ),
                seed             = seed,
                duration_seconds = mix_result["duration_seconds"],
                audio_url        = f"/api/song/{job_id}/audio/{var_num}",
                vocal_url        = f"/api/song/{job_id}/vocal/{var_num}",
                instrumental_url = f"/api/song/{job_id}/instrumental/{var_num}",
                waveform_data    = peaks,
                engine           = "ace-step" if provider == "colab_ace_step" else provider,
                voice_conversion = voice_conv_method,
                is_demo          = is_demo,
            )
            finished_variants.append(variant_info)

        # ------------------------------------------------------------------
        # STEP 8 — Done
        # ------------------------------------------------------------------
        job.variants      = finished_variants
        job.current_step  = JobStep.STEP_8_READY
        job.step_name     = STEP_NAMES[JobStep.STEP_8_READY]
        job.step_progress = 100.0
        job.status        = "completed"
        job.updated_at    = time.time()

        demo_count = sum(1 for v in finished_variants if v.is_demo)
        if demo_count == len(finished_variants):
            job.message = (
                f"{len(finished_variants)} demo-tone variant(s) ready. "
                "These are synthesised placeholders — NOT real AI songs. "
                "Connect a cloud GPU to generate real songs."
            )
        elif demo_count > 0:
            job.message = (
                f"{len(finished_variants)} variant(s) ready "
                f"({demo_count} demo-tone). "
                "Connect a cloud GPU for all-real variants."
            )
        else:
            job.message = (
                f"{len(finished_variants)} variant(s) ready for playback and selection."
            )

        await notify_listeners(job_id, "completed", job.model_dump())

    except CloudUnavailableError as exc:
        logger.error("Pipeline failed — cloud GPU unavailable: %s", exc)
        job.status     = "failed"
        job.error      = str(exc)
        job.message    = f"Song generation failed: {exc}"
        job.updated_at = time.time()
        await notify_listeners(job_id, "error", job.model_dump())

    except Exception as exc:
        logger.exception("Pipeline error for job %s: %s", job_id, exc)
        job.status     = "failed"
        job.error      = str(exc)
        job.message    = f"Pipeline error: {exc}"
        job.updated_at = time.time()
        await notify_listeners(job_id, "error", job.model_dump())
