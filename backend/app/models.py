from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class Language(str, Enum):
    URDU   = "urdu"
    PASHTO = "pashto"

class Genre(str, Enum):
    GHAZAL       = "ghazal"
    SUFI         = "sufi"
    POP          = "pop"
    FOLK_ATTAN   = "folk_attan"
    RUBAB_BALLAD = "rubab_ballad"
    QAWWALI      = "qawwali"
    LOFI         = "lofi"
    ACOUSTIC     = "acoustic"

# Pashto respelling dialect
class PashtoDialect(str, Enum):
    PESHAWAR   = "peshawar"    # Northern / Yusufzai  (default)
    KANDAHARI  = "kandahari"   # Southern / Kandahari

class JobStep(int, Enum):
    STEP_1_INPUT        = 1
    STEP_2_LYRICS       = 2
    STEP_3_PREPARE_VOICE= 3
    STEP_4_GENERATE_SONG= 4
    STEP_5_SPLIT_VOCALS = 5
    STEP_6_CLONE_VOICE  = 6
    STEP_7_ENHANCE_MIX  = 7
    STEP_8_READY        = 8

STEP_NAMES = {
    JobStep.STEP_1_INPUT:         "Input Received & Validated",
    JobStep.STEP_2_LYRICS:        "Generating & Arranging Lyrics",
    JobStep.STEP_3_PREPARE_VOICE: "High-pass Filter & Normalization of Voice Sample",
    JobStep.STEP_4_GENERATE_SONG: "Composing Music with ACE-Step 1.5",
    JobStep.STEP_5_SPLIT_VOCALS:  "Vocal / Instrumental Stems",
    JobStep.STEP_6_CLONE_VOICE:   "Singing Voice Conversion",
    JobStep.STEP_7_ENHANCE_MIX:   "Enhancing & Final Mix",
    JobStep.STEP_8_READY:         "Songs Ready for Comparison & Download",
}

# ---------------------------------------------------------------------------
# Per-variant information returned to the frontend
# ---------------------------------------------------------------------------
class VariantInfo(BaseModel):
    variant_number:    int
    title:             str
    seed:              int
    duration_seconds:  float
    audio_url:         str
    vocal_url:         Optional[str]  = None
    instrumental_url:  Optional[str]  = None
    waveform_data:     Optional[List[float]] = None

    # Honesty fields (Phase 1)
    engine:            str = "unknown"
    # "ace-step" | "demo-tone" | "unknown"

    voice_conversion:  str = "none"
    # "rvc" | "seed-vc" | "none"

    is_demo:           bool = False
    # True whenever engine == "demo-tone"

# ---------------------------------------------------------------------------
# Full job state
# ---------------------------------------------------------------------------
class JobState(BaseModel):
    job_id:               str
    language:             Language
    theme:                str
    genre:                Genre
    display_lyrics:       str
    sung_lyrics:          Optional[str]  = None
    lyrics_source:        str = "unknown"
    # "user" | "gemini" | "template" | "unknown"

    number_of_variants:   int
    current_step:         int = 1
    step_name:            str = STEP_NAMES[JobStep.STEP_1_INPUT]
    step_progress:        float = 0.0
    status:               str = "pending"
    # "pending" | "processing" | "completed" | "failed"
    message:              str = "Job initialized"

    voice_sample_path:         Optional[str] = None
    cleaned_voice_sample_path: Optional[str] = None

    variants:             List[VariantInfo] = []
    selected_variant:     Optional[int]     = None
    error:                Optional[str]     = None

    created_at:  float
    updated_at:  float

# ---------------------------------------------------------------------------
# Request / response helpers
# ---------------------------------------------------------------------------
class LyricsRequest(BaseModel):
    language:        Language
    theme:           str
    genre:           Genre
    custom_stanzas:  Optional[str] = None
    dialect:         PashtoDialect = PashtoDialect.PESHAWAR

class LyricsResponse(BaseModel):
    language:        Language
    display_lyrics:  str
    sung_lyrics:     str
    structure:       Dict[str, Any]
    source:          str           # "user" | "gemini" | "template"
    dialect:         str = "peshawar"

class SelectVariantRequest(BaseModel):
    variant_number: int
