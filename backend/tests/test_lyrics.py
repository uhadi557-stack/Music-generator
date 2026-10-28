import pytest
from unittest.mock import patch, MagicMock
from app.config import runtime_config
from app.models import Language, Genre
from app.lyrics import (
    call_gemini_lyrics,
    generate_lyrics,
    convert_pashto_to_sung_phonetics,
)

def test_gemini_key_in_header_not_in_url():
    runtime_config.gemini_api_key = "AIzaFakeKey999"
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{
                "content": {"parts": [{"text": "[Verse 1]\nشام ڈھلی تو..."}]}
            }]
        }
        mock_post.return_value = mock_resp
        
        call_gemini_lyrics(Language.URDU, "Love", Genre.GHAZAL)
        
        assert mock_post.called
        args, kwargs = mock_post.call_args
        called_url = args[0]
        called_headers = kwargs.get("headers", {})
        
        # KEY MUST NOT BE IN URL QUERY PARAM
        assert "key=" not in called_url
        assert "AIzaFakeKey999" not in called_url
        # Key must be in header
        assert called_headers.get("x-goog-api-key") == "AIzaFakeKey999"

def test_generate_lyrics_user_stanzas():
    custom = "پہلی سطر محبت کی\nدوسری سطر وفا کی"
    res = generate_lyrics(Language.URDU, "Love", Genre.GHAZAL, custom_stanzas=custom)
    assert res.source == "user"
    assert "پہلی سطر" in res.display_lyrics
    assert res.sung_lyrics == res.display_lyrics

def test_generate_lyrics_template_fallback_honest_label():
    runtime_config.gemini_api_key = ""
    res = generate_lyrics(Language.URDU, "Love", Genre.GHAZAL)
    assert res.source == "template"
    assert len(res.display_lyrics) > 20
    assert "[Verse 1]" in res.display_lyrics
    assert "[Chorus]" in res.display_lyrics

def test_pashto_dialect_peshawar():
    # In Peshawar/Northern dialect: ښ -> خ, ږ -> ګ -> گ (standard Gaf for singing models)
    pashto_sample = "ښایسته ږغ"
    sung = convert_pashto_to_sung_phonetics(pashto_sample, dialect="peshawar")
    assert "خ" in sung
    assert "گ" in sung
    assert "ښ" not in sung
    assert "ږ" not in sung

def test_pashto_dialect_kandahari():
    # In Kandahari/Southern dialect: ښ -> ش, ږ -> ژ
    pashto_sample = "ښایسته ږغ"
    sung = convert_pashto_to_sung_phonetics(pashto_sample, dialect="kandahari")
    assert "ش" in sung
    assert "ژ" in sung
    assert "ښ" not in sung
    assert "ږ" not in sung

def test_urdu_lyrics_unmodified_by_sung_phonetics():
    urdu_sample = "دل کی باتیں سنبھالی جائیں"
    res = generate_lyrics(Language.URDU, "Love", Genre.GHAZAL, custom_stanzas=urdu_sample)
    assert res.display_lyrics == res.sung_lyrics
