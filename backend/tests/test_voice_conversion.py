import os
import pytest
from unittest.mock import patch, MagicMock
from app.config import runtime_config
from app.voice_clone import VoiceCloningEngine

def test_voice_conversion_offline_passthrough(sample_wav_file):
    runtime_config.cloud_gpu_url = ""
    engine = VoiceCloningEngine(cloud_gpu_url="")
    
    out_path, method = engine.convert_singing_voice(
        job_id="job_vc_test",
        variant_number=1,
        source_vocal_path=sample_wav_file,
        cleaned_voice_sample_path=sample_wav_file,
    )
    
    # Must be exact source audio and honest 'none' method
    assert out_path == sample_wav_file
    assert method == "none"

def test_voice_conversion_network_failure_fallback(sample_wav_file):
    runtime_config.cloud_gpu_url = "https://broken-cloud.gradio.live"
    engine = VoiceCloningEngine(cloud_gpu_url=runtime_config.cloud_gpu_url)
    
    with patch("requests.post", side_effect=Exception("Connection refused")):
        out_path, method = engine.convert_singing_voice(
            job_id="job_vc_test",
            variant_number=1,
            source_vocal_path=sample_wav_file,
            cleaned_voice_sample_path=sample_wav_file,
        )
        
        # Must fail gracefully to passthrough with 'none'
        assert out_path == sample_wav_file
        assert method == "none"

def test_voice_conversion_cloud_success(sample_wav_file, sample_wav_bytes):
    runtime_config.cloud_gpu_url = "https://active-colab.gradio.live"
    engine = VoiceCloningEngine(cloud_gpu_url=runtime_config.cloud_gpu_url)
    
    with patch("requests.post") as mock_post:
        resp = MagicMock()
        resp.status_code = 200
        # Valid converted audio bytes > 1000 bytes
        resp.content = sample_wav_bytes * 5
        resp.headers = {"x-conversion-method": "seed-vc"}
        mock_post.return_value = resp
        
        out_path, method = engine.convert_singing_voice(
            job_id="job_vc_test",
            variant_number=1,
            source_vocal_path=sample_wav_file,
            cleaned_voice_sample_path=sample_wav_file,
        )
        
        assert method == "seed-vc"
        assert os.path.exists(out_path)
        assert out_path != sample_wav_file
        assert "variant_1_cloned.wav" in out_path
