import io
import pytest
from app.config import runtime_config

def test_start_song_valid_minimal(client):
    data = {
        "language": "urdu",
        "theme": "Love and devotion",
        "genre": "ghazal",
        "variants": 1,
    }
    response = client.post("/api/song/start", data=data)
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "started"
    assert "job_id" in res

def test_start_song_invalid_language(client):
    data = {
        "language": "spanish",
        "theme": "Love and devotion",
        "genre": "ghazal",
        "variants": 1,
    }
    response = client.post("/api/song/start", data=data)
    assert response.status_code == 400
    assert "Unsupported language" in response.json()["detail"]

def test_start_song_variants_below_min(client):
    data = {
        "language": "urdu",
        "theme": "Theme",
        "genre": "ghazal",
        "variants": 0,
    }
    response = client.post("/api/song/start", data=data)
    assert response.status_code == 422  # FastAPI validation failure

def test_start_song_variants_above_max(client):
    data = {
        "language": "urdu",
        "theme": "Theme",
        "genre": "ghazal",
        "variants": 4,
    }
    response = client.post("/api/song/start", data=data)
    assert response.status_code == 422  # FastAPI validation failure

def test_start_song_voice_sample_too_large(client):
    # 21 MB of fake audio
    large_payload = b"\x00" * (21 * 1024 * 1024)
    files = {
        "voice_sample": ("large.wav", io.BytesIO(large_payload), "audio/wav")
    }
    data = {
        "language": "urdu",
        "theme": "Theme",
        "genre": "ghazal",
        "variants": 1,
    }
    response = client.post("/api/song/start", data=data, files=files)
    assert response.status_code == 400
    assert "too large" in response.json()["detail"]

def test_start_song_unsupported_file_extension(client):
    files = {
        "voice_sample": ("malicious.exe", io.BytesIO(b"MZ12345"), "application/octet-stream")
    }
    data = {
        "language": "urdu",
        "theme": "Theme",
        "genre": "ghazal",
        "variants": 1,
    }
    response = client.post("/api/song/start", data=data, files=files)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]

def test_start_song_mp3_without_ffmpeg_rejected(client):
    original_ffmpeg = runtime_config.ffmpeg_available
    try:
        runtime_config.ffmpeg_available = False
        files = {
            "voice_sample": ("sample.mp3", io.BytesIO(b"\xff\xfb\x90\x00" * 100), "audio/mpeg")
        }
        data = {
            "language": "urdu",
            "theme": "Theme",
            "genre": "ghazal",
            "variants": 1,
        }
        response = client.post("/api/song/start", data=data, files=files)
        assert response.status_code == 400
        assert "requires ffmpeg" in response.json()["detail"]
    finally:
        runtime_config.ffmpeg_available = original_ffmpeg

def test_start_song_empty_sample_handled(client):
    files = {
        "voice_sample": ("empty.wav", io.BytesIO(b""), "audio/wav")
    }
    data = {
        "language": "urdu",
        "theme": "Theme",
        "genre": "ghazal",
        "variants": 1,
    }
    response = client.post("/api/song/start", data=data, files=files)
    assert response.status_code == 200
    assert response.json()["status"] == "started"
