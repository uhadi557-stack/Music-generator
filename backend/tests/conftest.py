import os
import io
import wave
import struct
import math
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.config import runtime_config

@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)

@pytest.fixture
def sample_wav_bytes():
    """Generates a small valid mono WAV file (1 second, 440 Hz sine wave)."""
    sample_rate = 22050
    duration = 1.0
    num_samples = int(sample_rate * duration)
    
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        
        frames = bytearray()
        for i in range(num_samples):
            # 440 Hz tone
            t = float(i) / sample_rate
            value = int(16000.0 * math.sin(2.0 * math.pi * 440.0 * t))
            frames.extend(struct.pack("<h", value))
        wf.writeframes(frames)
    
    buffer.seek(0)
    return buffer.read()

@pytest.fixture
def sample_wav_file(tmp_path, sample_wav_bytes):
    """Writes a sample WAV file to a temporary directory."""
    path = tmp_path / "sample_voice.wav"
    path.write_bytes(sample_wav_bytes)
    return str(path)
