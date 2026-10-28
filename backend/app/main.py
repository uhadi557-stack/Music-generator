"""
main.py — FastAPI application for the Urdu & Pashto Song Generator.

Phase 1 changes
---------------
* CORS: explicit origins only (no wildcard), allow_credentials=False.
* /api/health: reports ffmpeg_available and cloud_gpu_status.
* /api/config/cloud-gpu/test: server-side proxy so the browser never
  fetches Colab directly (fixes the CORS error in the settings modal).
* /api/song/start: validates variants 1–3; rejects uploads >20 MB;
  rejects file types that need ffmpeg when ffmpeg is absent; requires
  voice samples to be WAV when ffmpeg is absent; returns 400 for bad input.
* Gemini key is NEVER returned to the client; only has_gemini_key boolean.
"""

import os
import uuid
import logging
from typing import Optional

import requests as http_requests
from fastapi import (
    FastAPI, UploadFile, File, Form, HTTPException,
    BackgroundTasks, status, Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from pydantic import BaseModel

from .config import UPLOADS_DIR, VARIANTS_DIR, runtime_config
from .models import Language, Genre, LyricsRequest, SelectVariantRequest
from .lyrics import generate_lyrics
from .audio_prep import (
    ALLOWED_EXTENSIONS, UPLOAD_MAX_BYTES,
    VOICE_SAMPLE_MIN_SECONDS, VOICE_SAMPLE_MAX_SECONDS,
)
from .pipeline import (
    create_song_job, run_pipeline, get_job, subscribe_job_events,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("song_generator")

app = FastAPI(
    title="AI Urdu & Pashto Song Generator API",
    version="2.0.0",
    description=(
        "Backend API for 8-step AI Urdu & Pashto Song Generation. "
        "Phase 1: honest engine labels, ffmpeg detection, safe audio handling."
    ),
)

# ---------------------------------------------------------------------------
# CORS — explicit origins, no wildcard, no credentials required
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ],
    allow_credentials=False,   # wildcard + credentials is invalid per spec
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Config models
# ---------------------------------------------------------------------------
class CloudGpuConfigUpdate(BaseModel):
    cloud_gpu_url:   str
    gemini_api_key:  Optional[str] = None


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "service": "Suroor AI Backend API",
        "status": "online",
        "frontend_url": "http://localhost:5173",
        "docs": "/docs",
        "health": "/api/health",
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health_check():
    """
    Reports system capabilities.

    cloud_gpu_status values:
        "not_configured" — no URL has been saved
        "unreachable"    — URL saved but /health ping failed
        "connected"      — URL saved and /health returned 200
    """
    cloud_status = "not_configured"
    if runtime_config.cloud_gpu_url:
        try:
            r = http_requests.get(
                f"{runtime_config.cloud_gpu_url.rstrip('/')}/health",
                timeout=5,
            )
            cloud_status = "connected" if r.status_code == 200 else "unreachable"
        except Exception:
            cloud_status = "unreachable"

    return {
        "status":                "healthy",
        "ffmpeg_available":      runtime_config.ffmpeg_available,
        "cloud_gpu_url_set":     bool(runtime_config.cloud_gpu_url),
        "cloud_gpu_status":      cloud_status,
        "gemini_api_key_configured": bool(runtime_config.gemini_api_key),
        "allow_demo_fallback":   runtime_config.allow_demo_fallback,
    }


# ---------------------------------------------------------------------------
# Config read / write
# ---------------------------------------------------------------------------
@app.get("/api/config")
async def get_config():
    return {
        "cloud_gpu_url":  runtime_config.cloud_gpu_url,
        "has_gemini_key": bool(runtime_config.gemini_api_key),
        "ffmpeg_available": runtime_config.ffmpeg_available,
        "allow_demo_fallback": runtime_config.allow_demo_fallback,
    }


@app.post("/api/config/cloud-gpu")
async def update_cloud_config(update: CloudGpuConfigUpdate):
    runtime_config.cloud_gpu_url = update.cloud_gpu_url.strip()
    if update.gemini_api_key:
        runtime_config.gemini_api_key = update.gemini_api_key.strip()
    return {
        "status":         "updated",
        "cloud_gpu_url":  runtime_config.cloud_gpu_url,
        "has_gemini_key": bool(runtime_config.gemini_api_key),
    }


@app.post("/api/config/cloud-gpu/test")
async def test_cloud_connection(request: Request):
    """
    Server-side proxy for the 'Test connection' button in the settings modal.

    The browser must NOT fetch the Colab URL directly — that would fail on
    CORS because the Colab runner has no CORS headers.  This endpoint makes
    the request from the backend and returns a simple status.
    """
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    target = (body.get("url", "").strip() if isinstance(body, dict) else "") or runtime_config.cloud_gpu_url
    if not target:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "detail": "No cloud GPU URL configured."},
        )
    try:
        r = http_requests.get(
            f"{target.rstrip('/')}/health",
            timeout=8,
        )
        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                data = {}
            return {
                "status":   "connected",
                "detail":   "Cloud GPU health endpoint returned 200.",
                "gpu_info": data,
            }
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "status": "unreachable",
                "detail": f"Cloud GPU returned HTTP {r.status_code}.",
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"status": "unreachable", "detail": str(exc)},
        )


# ---------------------------------------------------------------------------
# Lyrics preview
# ---------------------------------------------------------------------------
@app.post("/api/lyrics/generate")
async def preview_lyrics(request: LyricsRequest):
    """Step 2 preview — generate or arrange lyrics before starting a full job."""
    res = generate_lyrics(
        language=request.language,
        theme=request.theme,
        genre=request.genre,
        custom_stanzas=request.custom_stanzas,
        dialect=request.dialect.value,
    )
    return res


# ---------------------------------------------------------------------------
# Song generation
# ---------------------------------------------------------------------------
@app.post("/api/song/start")
async def start_song_generation(
    background_tasks: BackgroundTasks,
    language: str          = Form(...),
    theme:    str          = Form(...),
    genre:    str          = Form(...),
    variants: int          = Form(default=1, ge=1, le=3),   # validated 1–3
    stanzas:  Optional[str] = Form(None),
    dialect:  Optional[str] = Form("peshawar"),
    voice_sample: Optional[UploadFile] = File(None),
):
    """
    Step 1: validate, save optional voice sample, start background pipeline.

    Validation
    ----------
    * variants must be 1–3 (enforced by ge/le; FastAPI returns 422 otherwise)
    * voice_sample must be ≤ 20 MB
    * accepted extensions: wav, mp3, m4a, ogg, webm
    * non-WAV files require ffmpeg; return 400 with clear message if absent
    """
    # Language
    try:
        lang_enum = Language(language.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{language}'. Choose 'urdu' or 'pashto'.",
        )

    # Genre (lenient: bad value falls back to ghazal)
    try:
        genre_enum = Genre(genre.lower())
    except ValueError:
        genre_enum = Genre.GHAZAL

    job_id = f"song_{uuid.uuid4().hex[:10]}"

    # ---- Voice sample handling -------------------------------------------
    sample_path: Optional[str] = None

    if voice_sample is not None and getattr(voice_sample, "filename", None):
        content = await voice_sample.read()

        if len(content) == 0:
            pass   # treat empty file as "no sample"
        else:
            # Size check
            if len(content) > UPLOAD_MAX_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Voice sample too large: {len(content) // (1024*1024)} MB. "
                        f"Maximum is {UPLOAD_MAX_BYTES // (1024*1024)} MB."
                    ),
                )

            # Extension check
            raw_name = voice_sample.filename or "sample.wav"
            ext = os.path.splitext(raw_name)[1].lstrip(".").lower()
            if not ext:
                ext = "wav"
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported file type '.{ext}'. "
                        f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
                    ),
                )

            # ffmpeg check for non-WAV formats
            if ext != "wav" and not runtime_config.ffmpeg_available:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"File type '.{ext}' requires ffmpeg for conversion, "
                        "but ffmpeg was not found on this server. "
                        "Please upload a WAV file, or install ffmpeg and restart the server."
                    ),
                )

            # Save
            sample_filename = f"{job_id}_sample.{ext}"
            sample_path = os.path.join(UPLOADS_DIR, sample_filename)
            with open(sample_path, "wb") as fh:
                fh.write(content)

    # ---- Create job & start pipeline ------------------------------------
    job = create_song_job(
        job_id=job_id,
        language=lang_enum,
        theme=theme,
        genre=genre_enum,
        number_of_variants=variants,   # already validated 1–3 by Form(ge=1, le=3)
        voice_sample_path=sample_path,
        custom_stanzas=stanzas,
    )

    background_tasks.add_task(
        run_pipeline,
        job_id=job_id,
        custom_stanzas=stanzas,
        dialect=dialect or "peshawar",
    )

    return {
        "job_id":        job_id,
        "status":        "started",
        "current_step":  job.current_step,
        "message":       "Song generation started successfully.",
    }


# ---------------------------------------------------------------------------
# Progress streaming (SSE)
# ---------------------------------------------------------------------------
@app.get("/api/song/{job_id}/stream")
async def stream_job_progress(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return StreamingResponse(
        subscribe_job_events(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Variant listing
# ---------------------------------------------------------------------------
@app.get("/api/song/{job_id}/variants")
async def list_variants(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return {
        "job_id":         job.job_id,
        "status":         job.status,
        "current_step":   job.current_step,
        "display_lyrics": job.display_lyrics,
        "sung_lyrics":    job.sung_lyrics,
        "lyrics_source":  job.lyrics_source,
        "variants":       [v.model_dump() for v in job.variants],
        "error":          job.error,
    }


# ---------------------------------------------------------------------------
# Audio file serving
# ---------------------------------------------------------------------------
@app.get("/api/song/{job_id}/audio/{n}")
async def stream_audio_variant(job_id: str, n: int):
    master_mp3 = VARIANTS_DIR / f"{job_id}_variant_{n}_master.mp3"
    master_wav = VARIANTS_DIR / f"{job_id}_variant_{n}_master.wav"
    if master_mp3.exists():
        return FileResponse(master_mp3, media_type="audio/mpeg")
    elif master_wav.exists():
        return FileResponse(master_wav, media_type="audio/wav")
    raise HTTPException(status_code=404, detail=f"Variant {n} audio not found for job {job_id}.")


@app.get("/api/song/{job_id}/vocal/{n}")
async def stream_vocal_stem(job_id: str, n: int):
    raw_vocal = VARIANTS_DIR / f"{job_id}_variant_{n}_vocal.wav"
    if raw_vocal.exists():
        return FileResponse(raw_vocal, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Vocal stem not found.")


@app.get("/api/song/{job_id}/instrumental/{n}")
async def stream_instrumental_stem(job_id: str, n: int):
    inst_wav = VARIANTS_DIR / f"{job_id}_variant_{n}_inst.wav"
    if inst_wav.exists():
        return FileResponse(inst_wav, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Instrumental stem not found.")


# ---------------------------------------------------------------------------
# Variant selection & download
# ---------------------------------------------------------------------------
@app.post("/api/song/{job_id}/select")
async def select_variant(job_id: str, body: SelectVariantRequest):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if body.variant_number < 1 or body.variant_number > len(job.variants):
        raise HTTPException(status_code=400, detail="Invalid variant number.")
    job.selected_variant = body.variant_number
    return {
        "job_id":           job_id,
        "selected_variant": body.variant_number,
        "download_url":     f"/api/song/{job_id}/download/{body.variant_number}",
        "message":          f"Variant {body.variant_number} selected.",
    }


@app.get("/api/song/{job_id}/download/{n}")
async def download_variant(job_id: str, n: int):
    job   = get_job(job_id)
    title = f"{job.language.value.title()}_Song_Variant_{n}" if job else f"Song_Variant_{n}"

    master_mp3 = VARIANTS_DIR / f"{job_id}_variant_{n}_master.mp3"
    master_wav = VARIANTS_DIR / f"{job_id}_variant_{n}_master.wav"

    if master_mp3.exists():
        return FileResponse(master_mp3, filename=f"{title}.mp3", media_type="audio/mpeg")
    elif master_wav.exists():
        return FileResponse(master_wav, filename=f"{title}.wav", media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Audio file not found.")
