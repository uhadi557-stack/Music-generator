import os
import pytest
from unittest.mock import patch, MagicMock
from app.config import runtime_config, VARIANTS_DIR
from app.models import Language, Genre
from app.acestep_client import AceStepClient, CloudUnavailableError

def test_offline_raises_cloud_unavailable_error_when_fallback_disabled():
    runtime_config.cloud_gpu_url = ""
    runtime_config.allow_demo_fallback = False
    
    client = AceStepClient(cloud_gpu_url="")
    
    with pytest.raises(CloudUnavailableError) as exc_info:
        client.generate_song_variants(
            job_id="test_offline_job",
            language=Language.URDU,
            genre=Genre.GHAZAL,
            theme="Love",
            sung_lyrics="دل کی باتیں...",
            variant_count=1,
            duration_seconds=1.0,
        )
    assert "Cloud GPU not reachable" in str(exc_info.value)

def test_offline_generates_demo_tone_when_fallback_enabled(tmp_path):
    runtime_config.cloud_gpu_url = ""
    runtime_config.allow_demo_fallback = True
    
    client = AceStepClient(cloud_gpu_url="")
    
    results = client.generate_song_variants(
        job_id="test_demo_job",
        language=Language.URDU,
        genre=Genre.GHAZAL,
        theme="Love",
        sung_lyrics="دل کی باتیں...",
        variant_count=1,
        duration_seconds=1.0,
    )
    
    assert len(results) == 1
    var = results[0]
    assert var["provider"] == "demo-tone"
    assert var["is_demo"] is True
    assert os.path.exists(var["mix_path"])
    assert os.path.exists(var["vocal_path"])
    assert os.path.exists(var["inst_path"])
    assert os.path.getsize(var["mix_path"]) > 1000

def test_cloud_generation_success(sample_wav_bytes):
    runtime_config.cloud_gpu_url = "https://mock-ace-step.gradio.live"
    client = AceStepClient(cloud_gpu_url=runtime_config.cloud_gpu_url)
    
    # Mock health check and generation
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # /health response
        health_resp = MagicMock()
        health_resp.status_code = 200
        health_resp.json.return_value = {"status": "ok"}
        
        # Audio download response
        audio_resp = MagicMock()
        audio_resp.status_code = 200
        audio_resp.content = sample_wav_bytes
        
        mock_get.side_effect = [health_resp, audio_resp, audio_resp, audio_resp]
        
        # /api/generate direct response
        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.json.return_value = {
            "status": "success",
            "audio_url": "/v1/audio?path=mix.wav",
            "vocal_url": "/v1/audio?path=vocal.wav",
            "inst_url": "/v1/audio?path=inst.wav",
        }
        mock_post.return_value = post_resp
        
        results = client.generate_song_variants(
            job_id="test_cloud_job",
            language=Language.URDU,
            genre=Genre.GHAZAL,
            theme="Love",
            sung_lyrics="دل کی باتیں...",
            variant_count=1,
            duration_seconds=1.0,
        )
        
        assert len(results) == 1
        var = results[0]
        assert var["provider"] == "colab_ace_step"
        assert var["is_demo"] is False
