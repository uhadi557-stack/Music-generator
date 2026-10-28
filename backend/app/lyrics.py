"""
Lyrics generation — Step 2 of the pipeline.

Key behaviours
--------------
* Gemini API key is sent in the ``x-goog-api-key`` header, never in the URL.
* Model name is read from ``runtime_config.gemini_model`` (default in config.py).
* The URL and key are never logged.
* Pashto phonetic conversion offers two dialect modes:
    - "peshawar"  (Northern / Yusufzai, default): ښ→خ, ږ→ګ
    - "kandahari" (Southern): ښ→ش, ږ→ژ
  The feature is experimental; the mapping has not been validated by ACE-Step
  and is explicitly labelled as such.
"""

import re
import logging
from typing import Optional, Dict, Any

import requests

from .config import runtime_config
from .models import Language, Genre, PashtoDialect, LyricsResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pashto phonetic respelling maps
# ---------------------------------------------------------------------------
# NOTE: Both maps are *experimental*.  The Northern (Peshawar) map is now the
# default because the previous default used Southern (Kandahari) values for ښ
# and ږ, which are the two most dialectally variable letters.
#
# A native Pashto speaker should verify and correct these before any production
# release.  Neither map is tailored to any specific synthesizer model — that is
# untested.

# Northern / Yusufzai (Peshawar) — DEFAULT
# ښ is typically realised as خ; ږ as ګ
_MAP_PESHAWAR: Dict[str, str] = {
    "ښ": "خ",   # Pashto xin   → kh  (Northern)
    "ږ": "ګ",   # Pashto zhin  → g   (Northern)
    "ځ": "ز",   # dz affricate → z
    "څ": "س",   # ts affricate → s
    "ڼ": "ں",   # Retroflex nasal → noon ghunna
    "ړ": "ڑ",   # Retroflex r  → Urdu Rre
    "ډ": "ڈ",   # Retroflex d  → Urdu Ddaal
    "ټ": "ٹ",   # Retroflex t  → Urdu Tte
    "ې": "ے",   # Majhool Ye   → Urdu Bari Ye
    "ۍ": "ی",   # Feminine Ye  → Urdu Chhoti Ye
    "ئ": "ئی",  # Verb Ye
    "ي": "ی",   # Arabic Ye    → Urdu Ye
    "ګ": "گ",   # Pashto Gaf   → standard Gaf
}

# Southern / Kandahari — kept as reference, user may switch via dialect param
# ښ is typically realised as ش; ږ as ژ
_MAP_KANDAHARI: Dict[str, str] = {
    "ښ": "ش",   # Pashto xin   → sh (Southern)
    "ږ": "ژ",   # Pashto zhin  → zh (Southern)
    "ځ": "ز",
    "څ": "س",
    "ڼ": "ں",
    "ړ": "ڑ",
    "ډ": "ڈ",
    "ټ": "ٹ",
    "ې": "ے",
    "ۍ": "ی",
    "ئ": "ئی",
    "ي": "ی",
    "ګ": "گ",
}


def convert_pashto_to_sung_phonetics(pashto_text: str, dialect: str = "peshawar") -> str:
    """
    Transforms Pashto script into a phonetic 'sung' spelling that may help
    singing voice models trained primarily on Urdu/Arabic corpora.

    This is *experimental* — the mapping has not been validated against any
    specific model and may not improve pronunciation accuracy.

    Parameters
    ----------
    pashto_text : str
        Original Pashto-script text.
    dialect : str
        "peshawar" (Northern / Yusufzai, default) or "kandahari" (Southern).
    """
    char_map = _MAP_KANDAHARI if dialect == "kandahari" else _MAP_PESHAWAR
    sung = pashto_text
    for src, dst in char_map.items():
        sung = sung.replace(src, dst)
    sung = re.sub(r"[ \t]+", " ", sung)
    return sung


# ---------------------------------------------------------------------------
# Lyric templates (reliable fallback when Gemini is not configured)
# ---------------------------------------------------------------------------
TEMPLATES: Dict[Language, Dict[Genre, str]] = {
    Language.URDU: {
        Genre.GHAZAL: (
            "[Verse 1]\n"
            "دل کی باتوں کو سنبھالا جائے\n"
            "رات کا درد اجالا جائے\n"
            "ہم نے چاہا تھا کہ خاموش رہیں\n"
            "اب محبت کو پکارا جائے\n\n"
            "[Chorus]\n"
            "یہ سفر خواب کا عنواں تو نہیں\n"
            "زندگی اتنا بھی آساں تو نہیں\n"
            "ہم تیری راہ میں پلکیں بچھائیں\n"
            "دل تیرا شمع کا پروانہ سہی\n\n"
            "[Verse 2]\n"
            "شام ڈھلتے ہی تیری یاد آئی\n"
            "اک نئی دھن سرِ محفل چھائی\n"
            "ہر صدا میں تیرا پیغام رہے\n"
            "میری جاں، تیرا ہی اک نام رہے\n\n"
            "[Chorus]\n"
            "یہ سفر خواب کا عنواں تو نہیں\n"
            "زندگی اتنا بھی آساں تو نہیں\n"
            "ہم تیری راہ میں پلکیں بچھائیں\n"
            "دل تیرا شمع کا پروانہ سہی\n\n"
            "[Outro]\n"
            "دل کی باتوں کو سنبھالا جائے..."
        ),
        Genre.SUFI: (
            "[Verse 1]\n"
            "روح کی پیاس بجھا دے مولا\n"
            "عشق کا راستہ دکھا دے مولا\n"
            "میں گدا تیرے در کا سائیں\n"
            "مجھ کو اپنا بنا لے مولا\n\n"
            "[Chorus]\n"
            "ہو حق، اللہ ہو حق\n"
            "من کنت مولاہ فعلی مولاہ\n"
            "نور تیرا ہی ہر سو چھایا\n"
            "تونے ہی یہ جہاں سجایا\n\n"
            "[Verse 2]\n"
            "بندھے جو ڈور تیرے کرم سے\n"
            "چھوٹے یہ دل ہر ایک بھرم سے\n"
            "تیری رضا میں جینا مرنا\n"
            "اب نہ کسی سے ڈرنا ورنا\n\n"
            "[Chorus]\n"
            "ہو حق، اللہ ہو حق\n"
            "من کنت مولاہ فعلی مولاہ\n"
            "نور تیرا ہی ہر سو چھایا\n"
            "تونے ہی یہ جہاں سجایا\n\n"
            "[Outro]\n"
            "یا علی مدد، یا رحمان مولا..."
        ),
        Genre.POP: (
            "[Verse 1]\n"
            "تیرے سنگ جینے کی چاہت ہوئی\n"
            "ہمیں بھی تو اب یہ محبت ہوئی\n"
            "دھڑکنیں تیز ہیں، دل بے قرار\n"
            "تیری نظر کا ہے سارا خمار\n\n"
            "[Chorus]\n"
            "او جاناں، تیرے بن اب جیا نہ جائے\n"
            "او جاناں، یہ گھونٹ پیا نہ جائے\n"
            "چلتے چلیں ہم ستاروں کے سنگ\n"
            "چھلکیں خوشی کے یہ سارے ہی رنگ\n\n"
            "[Verse 2]\n"
            "ہواؤں میں کیسی بہار آ گئی\n"
            "تیرے لمس سے اک پکار آ گئی\n"
            "نہ چھوڑیں گے ہم تیرا دامن کبھی\n"
            "تو ہے حقیقت تو خواب ابھی\n\n"
            "[Chorus]\n"
            "او جاناں، تیرے بن اب جیا نہ جائے\n"
            "او جاناں، یہ گھونٹ پیا نہ جائے\n\n"
            "[Outro]\n"
            "او جاناں... تیرے سنگ..."
        )
    },
    Language.PASHTO: {
        Genre.FOLK_ATTAN: (
            "[Verse 1]\n"
            "راشه په اتڼ کې لاس راکړه جانانه\n"
            "جوړه کړه د مېنې خوندوره زمانه\n"
            "غرونه او رغونه ټول په نڅا شول\n"
            "راغلل د ګلونو خوشبویانه مېلمانه\n\n"
            "[Chorus]\n"
            "ای زما وطنه، ای زما جانانه\n"
            "ګډ شه په اتڼ کې له خوښۍ نه ورانه\n"
            "ډول په نری غږ کړه، سرنا کړه روانه\n"
            "ستا په مینه پایم تر ابده پورې رانه\n\n"
            "[Verse 2]\n"
            "د پښتون په زړه کې د غیرت نغمه ده\n"
            "د ملنګ رباب کې د حسرت قصه ده\n"
            "ټول یو ځای راغونډ یو د خندا محفل دی\n"
            "ستا د سترګو جنګ کې زما مات شوی زړه دی\n\n"
            "[Chorus]\n"
            "ای زما وطنه، ای زما جانانه\n"
            "ګډ شه په اتڼ کې له خوښۍ نه ورانه\n"
            "ډول په نری غږ کړه، سرنا کړه روانه\n"
            "ستا په مینه پایم تر ابده پورې رانه\n\n"
            "[Outro]\n"
            "شاباس اتڼ والو، لاس په لاس روان شئ..."
        ),
        Genre.RUBAB_BALLAD: (
            "[Verse 1]\n"
            "د رباب په تار کې ستا یادونه ژاړي\n"
            "زما د مات زړګي فریادونه ژاړي\n"
            "بیلتانه لوګی کړم د هجران په اور کې\n"
            "ستا د سپین مخ شمعې سحرونه ژاړي\n\n"
            "[Chorus]\n"
            "کله به راځې، ای د ژوندون امیده\n"
            "وران مې شو جهان ستا له تلو ناامیده\n"
            "راشه د رباب په زنګیدلي نغمو کې\n"
            "زه تا لټوم په تورو شپو تیارو کې\n\n"
            "[Verse 2]\n"
            "د غره لمن کې چنارونه ژاړي\n"
            "د مینې تږي ناصبره زړونه ژاړي\n"
            "یو نظر راوګوره زما پر خوار حال باندې\n"
            "اوښکې مې تویېږي د جانان پر لاره باندې\n\n"
            "[Chorus]\n"
            "کله به راځې، ای د ژوندون امیده\n"
            "وران مې شو جهان ستا له تلو ناامیده\n\n"
            "[Outro]\n"
            "د رباب نغمه او ستا یاد..."
        )
    }
}


def structure_custom_stanzas(stanzas: str) -> str:
    """
    Wraps raw user stanzas in section tags if none are present.
    Limits total text to 4000 characters to avoid oversized payloads.
    """
    stanzas = stanzas.strip()[:4000]
    lines = [l.strip() for l in stanzas.split("\n") if l.strip()]
    if any(tag in stanzas for tag in ("[Verse", "[Chorus", "[Outro", "Verse:", "Chorus:")):
        return stanzas

    total = len(lines)
    if total <= 4:
        return "[Verse 1]\n" + "\n".join(lines)
    elif total <= 8:
        half = total // 2
        return (
            "[Verse 1]\n" + "\n".join(lines[:half]) +
            "\n\n[Chorus]\n" + "\n".join(lines[half:])
        )
    else:
        v1 = lines[:4]
        ch = lines[4:8]
        v2 = lines[8:12] if len(lines) >= 12 else lines[8:]
        return (
            "[Verse 1]\n" + "\n".join(v1) +
            "\n\n[Chorus]\n" + "\n".join(ch) +
            "\n\n[Verse 2]\n" + "\n".join(v2) +
            "\n\n[Chorus]\n" + "\n".join(ch)
        )


def call_gemini_lyrics(language: Language, theme: str, genre: Genre) -> Optional[str]:
    """
    Calls Google Gemini to generate structured lyrics.

    The API key is sent in the ``x-goog-api-key`` request *header* so it
    never appears in the URL or server logs.
    """
    api_key = runtime_config.gemini_api_key
    if not api_key:
        return None

    model = runtime_config.gemini_model
    lang_name = "Urdu" if language == Language.URDU else "Pashto"

    prompt = (
        f"You are an expert lyricist for {lang_name} music.\n"
        f"Write complete, poetic song lyrics in proper {lang_name} script.\n"
        f"Theme/Mood: {theme}\n"
        f"Musical Genre: {genre.value}\n\n"
        "Requirements:\n"
        "1. Use section tags: [Verse 1], [Chorus], [Verse 2], [Chorus], [Outro]\n"
        "2. Strict rhythmic meter; qafia & radif for Ghazal or traditional meter for Pashto.\n"
        "3. Singable with a catchy, repetitive [Chorus].\n"
        "4. Return ONLY the lyrics with section brackets. No English remarks.\n"
    )

    # Key goes in a header — never in the URL.
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:generateContent"
    )
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,    # ← header, not query string
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95,
            "maxOutputTokens": 1000,
        },
    }

    try:
        # Do NOT log url or headers — they contain the key.
        resp = requests.post(url, json=payload, headers=headers, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        else:
            # Log status code only, not the URL.
            logger.warning("Gemini API returned status %s", resp.status_code)
    except Exception as exc:
        logger.error("Error calling Gemini API: %s", exc)

    return None


def generate_lyrics(
    language: Language,
    theme: str,
    genre: Genre,
    custom_stanzas: Optional[str] = None,
    dialect: str = "peshawar",
) -> LyricsResponse:
    """
    Step 2: Generate or arrange lyrics, returning both display and sung versions.

    Returns
    -------
    LyricsResponse
        Includes a ``source`` field: "user", "gemini", or "template".
        Includes a ``dialect`` field for Pashto respelling mode used.
    """
    source = "template"

    if custom_stanzas and custom_stanzas.strip():
        display_lyrics = structure_custom_stanzas(custom_stanzas)
        source = "user"
    else:
        gemini_result = call_gemini_lyrics(language, theme, genre)
        if gemini_result:
            display_lyrics = gemini_result
            source = "gemini"
        else:
            genre_map = TEMPLATES.get(language, {})
            display_lyrics = genre_map.get(genre) or next(iter(genre_map.values()), "")
            if not display_lyrics:
                display_lyrics = "دل کی صدا، تیری نگاہ..."

    # Pashto phonetic respelling (experimental)
    if language == Language.PASHTO:
        sung_lyrics = convert_pashto_to_sung_phonetics(display_lyrics, dialect=dialect)
    else:
        sung_lyrics = display_lyrics

    structure = {
        "has_verse_1": "[Verse 1]" in display_lyrics or "[Verse]" in display_lyrics,
        "has_chorus":  "[Chorus]"  in display_lyrics,
        "has_verse_2": "[Verse 2]" in display_lyrics,
        "total_lines": len([l for l in display_lyrics.splitlines() if l.strip()]),
    }

    return LyricsResponse(
        language=language,
        display_lyrics=display_lyrics,
        sung_lyrics=sung_lyrics,
        structure=structure,
        source=source,
        dialect=dialect,
    )
