import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

UPLOADS_DIR = MEDIA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

PROCESSED_DIR = MEDIA_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

VARIANTS_DIR = MEDIA_DIR / "variants"
VARIANTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Static configuration (from environment / .env)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CLOUD_GPU_URL  = os.getenv("CLOUD_GPU_URL", "")

# When True the pipeline generates a demo-tone track instead of failing when
# no cloud GPU is reachable.  Default is False so that a missing GPU causes a
# clear job failure rather than a silent fake result.
ALLOW_DEMO_FALLBACK: bool = os.getenv("ALLOW_DEMO_FALLBACK", "false").lower() == "true"

# Gemini model name – read from environment so it can be changed without code
# edits.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Server binding
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# ---------------------------------------------------------------------------
# Startup checks
# ---------------------------------------------------------------------------
_ffmpeg_path = shutil.which("ffmpeg")
FFMPEG_AVAILABLE: bool = _ffmpeg_path is not None

# ---------------------------------------------------------------------------
# Mutable runtime config (set via /api/config/cloud-gpu at runtime)
# ---------------------------------------------------------------------------
class RuntimeConfig:
    def __init__(self) -> None:
        self.gemini_api_key: str  = GEMINI_API_KEY
        self.gemini_model:   str  = GEMINI_MODEL
        self.cloud_gpu_url:  str  = CLOUD_GPU_URL
        self.allow_demo_fallback: bool = ALLOW_DEMO_FALLBACK
        # ffmpeg availability never changes at runtime
        self.ffmpeg_available: bool = FFMPEG_AVAILABLE

runtime_config = RuntimeConfig()
