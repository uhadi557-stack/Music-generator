import os
import pytest
from pydub import AudioSegment
from app.config import runtime_config
from app.audio_prep import clean_and_prepare_voice_sample
from app.audio_mixer import enhance_and_mix_stems

def test_clean_and_prepare_voice_sample_valid(sample_wav_file, tmp_path):
    # Create 6-second audio (passes >= 5.0s minimum requirement)
    seg = AudioSegment.from_file(sample_wav_file)
    valid_seg = seg * 6
    valid_path = str(tmp_path / "valid_sample.wav")
    valid_seg.export(valid_path, format="wav")
    
    output_clean = str(tmp_path / "cleaned_voice.wav")
    meta = clean_and_prepare_voice_sample(valid_path, output_clean)
    
    assert os.path.exists(output_clean)
    assert meta["sample_rate"] == 44100
    assert meta["channels"] == 1
    assert meta["cleaned_duration_seconds"] >= 5.0
    
    from app.audio_prep import generate_waveform_peaks
    peaks = generate_waveform_peaks(output_clean)
    assert len(peaks) > 0
    # All waveform peaks must be between 0.0 and 1.0
    for peak in peaks:
        assert 0.0 <= peak <= 1.0

def test_clean_and_prepare_voice_sample_too_short(sample_wav_file, tmp_path):
    # 1-second sample should be rejected by the duration guard
    output_clean = str(tmp_path / "cleaned_voice.wav")
    with pytest.raises(ValueError) as exc:
        clean_and_prepare_voice_sample(sample_wav_file, output_clean)
    assert "too short" in str(exc.value)

def test_enhance_and_mix_stems_peak_headroom(sample_wav_file, tmp_path):
    output_mix = str(tmp_path / "final_song.wav")
    
    # Mix identical stems
    res = enhance_and_mix_stems(
        cloned_vocal_path=sample_wav_file,
        instrumental_path=sample_wav_file,
        output_final_path=output_mix,
        vocal_gain_db=2.0,
        inst_gain_db=1.0,
    )
    
    assert os.path.exists(output_mix)
    assert res["final_wav"] == output_mix
    # Peak must have headroom and sit at or below -1.0 dBFS
    assert res["final_dbfs"] <= -0.95
    
    # Load with AudioSegment to verify duration and peak
    seg = AudioSegment.from_file(output_mix)
    assert seg.max_dBFS <= -0.95

def test_mix_stems_handles_unequal_durations(sample_wav_file, tmp_path):
    # Create a 2-second stem by appending
    seg = AudioSegment.from_file(sample_wav_file)
    long_seg = seg + seg
    long_path = str(tmp_path / "long_stem.wav")
    long_seg.export(long_path, format="wav")
    
    output_mix = str(tmp_path / "final_unequal.wav")
    res = enhance_and_mix_stems(
        cloned_vocal_path=sample_wav_file,  # 1 second
        instrumental_path=long_path,        # 2 seconds
        output_final_path=output_mix,
    )
    
    assert os.path.exists(output_mix)
    assert round(res["duration_seconds"], 1) == 2.0

def test_mp3_export_respects_ffmpeg_flag(sample_wav_file, tmp_path):
    original_ffmpeg = runtime_config.ffmpeg_available
    try:
        runtime_config.ffmpeg_available = False
        output_mix = str(tmp_path / "final_no_ffmpeg.wav")
        res = enhance_and_mix_stems(
            cloned_vocal_path=sample_wav_file,
            instrumental_path=sample_wav_file,
            output_final_path=output_mix,
        )
        assert res["final_mp3"] is None
        assert os.path.exists(res["final_wav"])
    finally:
        runtime_config.ffmpeg_available = original_ffmpeg
