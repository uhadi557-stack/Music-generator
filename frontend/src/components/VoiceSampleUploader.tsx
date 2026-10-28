import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  UploadCloud, Mic, Square, Play, Pause, CheckCircle2,
  X, AlertTriangle, Scissors, Volume2, Activity,
} from 'lucide-react';

interface VoiceSampleUploaderProps {
  onFileSelected: (file: File | null) => void;
  selectedFile: File | null;
  consentGiven: boolean;
  onConsentChange: (given: boolean) => void;
}

type TabMode = 'upload' | 'record';

interface AudioMeta {
  duration: number;
  sizeKB: number;
  format: string;
}

/** Decode ArrayBuffer to waveform peaks (normalized 0..1) */
async function extractWaveformPeaks(buffer: ArrayBuffer, numBars = 60): Promise<number[]> {
  try {
    const ctx = new AudioContext();
    const decoded = await ctx.decodeAudioData(buffer.slice(0));
    await ctx.close();
    const ch = decoded.getChannelData(0);
    const blockSize = Math.floor(ch.length / numBars);
    const peaks: number[] = [];
    for (let i = 0; i < numBars; i++) {
      let max = 0;
      for (let j = 0; j < blockSize; j++) {
        const abs = Math.abs(ch[i * blockSize + j]);
        if (abs > max) max = abs;
      }
      peaks.push(max);
    }
    const globalMax = Math.max(...peaks, 0.001);
    return peaks.map((p) => Math.max(0.05, p / globalMax));
  } catch {
    return Array.from({ length: numBars }, (_, i) => 0.15 + 0.7 * Math.abs(Math.sin(i * 0.25)));
  }
}

/** Quality badge based on duration */
function qualityBadge(duration: number): { label: string; color: string; ok: boolean } {
  if (duration >= 10 && duration <= 60) return { label: '✓ Good Sample', color: 'var(--accent-emerald)', ok: true };
  if (duration > 5) return { label: '⚠ OK (10-60s ideal)', color: 'var(--accent-gold)', ok: true };
  return { label: '✗ Too Short (<5s)', color: 'var(--accent-rose)', ok: false };
}

export const VoiceSampleUploader: React.FC<VoiceSampleUploaderProps> = ({
  onFileSelected,
  selectedFile,
  consentGiven,
  onConsentChange,
}) => {
  const [mode, setMode] = useState<TabMode>('upload');
  const [isDragging, setIsDragging] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [isPlayingPreview, setIsPlayingPreview] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [waveformPeaks, setWaveformPeaks] = useState<number[]>([]);
  const [micLevel, setMicLevel] = useState(0);
  const [audioMeta, setAudioMeta] = useState<AudioMeta | null>(null);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(100);
  const [currentTime, setCurrentTime] = useState(0);
  const [showTrimmer, setShowTrimmer] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Draw waveform on canvas
  useEffect(() => {
    if (!canvasRef.current || waveformPeaks.length === 0) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);

    const totalDuration = audioMeta?.duration || 1;
    const playedFrac = currentTime / totalDuration;

    waveformPeaks.forEach((peak, idx) => {
      const barW = (width / waveformPeaks.length) - 1.5;
      const barH = Math.max(3, peak * (height * 0.9));
      const x = idx * (width / waveformPeaks.length);
      const y = (height - barH) / 2;

      const frac = idx / waveformPeaks.length;
      const inTrimRange = frac >= trimStart / 100 && frac <= trimEnd / 100;
      const isPlayed = frac <= playedFrac;

      if (!inTrimRange) {
        ctx.fillStyle = 'rgba(255,255,255,0.07)';
      } else if (isPlayed) {
        const grad = ctx.createLinearGradient(0, y, 0, y + barH);
        grad.addColorStop(0, '#818cf8');
        grad.addColorStop(1, '#06b6d4');
        ctx.fillStyle = grad;
      } else {
        ctx.fillStyle = 'rgba(255,255,255,0.22)';
      }

      ctx.beginPath();
      ctx.roundRect(x, y, barW, barH, 2);
      ctx.fill();
    });
  }, [waveformPeaks, trimStart, trimEnd, currentTime, audioMeta]);

  // Live mic level animation
  const animateMicLevel = useCallback(() => {
    if (!analyserRef.current) return;
    const data = new Uint8Array(analyserRef.current.fftSize);
    analyserRef.current.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / data.length);
    setMicLevel(Math.min(1, rms * 8));
    animFrameRef.current = requestAnimationFrame(animateMicLevel);
  }, []);

  /** Load file: generate waveform, read metadata, set URL */
  const loadFile = async (file: File) => {
    setError(null);
    const url = URL.createObjectURL(file);
    setAudioUrl(url);
    setCurrentTime(0);
    setTrimStart(0);
    setTrimEnd(100);
    setShowTrimmer(false);

    // Read ArrayBuffer for waveform
    const arrayBuf = await file.arrayBuffer();
    const peaks = await extractWaveformPeaks(arrayBuf);
    setWaveformPeaks(peaks);

    // Get duration via HTMLAudioElement
    const tempAudio = new Audio(url);
    tempAudio.addEventListener('loadedmetadata', () => {
      const dur = isFinite(tempAudio.duration) ? tempAudio.duration : 0;
      setAudioMeta({
        duration: dur,
        sizeKB: Math.round(file.size / 1024),
        format: file.name.split('.').pop()?.toUpperCase() || 'WAV',
      });
    });

    onFileSelected(file);
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('audio/') && !file.name.match(/\.(wav|mp3|flac|m4a|ogg|aac)$/i)) {
      setError('Please select a valid audio file (WAV, MP3, FLAC, M4A).');
      return;
    }
    await loadFile(file);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    await loadFile(file);
  };

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    setAudioUrl(null);
    setWaveformPeaks([]);
    setAudioMeta(null);
    setCurrentTime(0);
    setShowTrimmer(false);
    onFileSelected(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Microphone recording
  const startRecording = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      audioChunksRef.current = [];

      // Live level meter
      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;
      animateMicLevel();

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) audioChunksRef.current.push(ev.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        setMicLevel(0);
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const file = new File([blob], `mic_recording_${Date.now()}.webm`, { type: 'audio/webm' });
        await loadFile(file);
      };

      mediaRecorder.start(100);
      setIsRecording(true);
      setRecordingSeconds(0);
      timerRef.current = window.setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
    } catch (err) {
      setError('Microphone access denied. Please allow microphone permission and try again.');
    }
  };

  const stopRecording = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    }
  };

  const togglePreview = (e: React.MouseEvent) => {
    e.stopPropagation();
    const audio = audioPlayerRef.current;
    if (!audio || !audioUrl) return;
    if (isPlayingPreview) {
      audio.pause();
      setIsPlayingPreview(false);
    } else {
      // Respect trim boundaries
      if (audioMeta) {
        audio.currentTime = (trimStart / 100) * audioMeta.duration;
      }
      audio.play().catch(() => setIsPlayingPreview(false));
      setIsPlayingPreview(true);
    }
  };

  const handleTimeUpdate = () => {
    const audio = audioPlayerRef.current;
    if (!audio) return;
    setCurrentTime(audio.currentTime);
    // Stop at trim end
    if (audioMeta && audio.currentTime >= (trimEnd / 100) * audioMeta.duration) {
      audio.pause();
      setIsPlayingPreview(false);
    }
  };

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

  const meta = audioMeta;
  const badge = meta ? qualityBadge(meta.duration) : null;
  const hasFile = Boolean(audioUrl && selectedFile);

  return (
    <div className="form-group" style={{ gap: '12px' }}>
      {/* Label */}
      <div className="form-label">
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Mic size={15} color="var(--accent-rose)" />
          Voice Sample for Singing Voice Conversion
        </span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>10–60s clear vocal</span>
      </div>

      {/* Mode Tabs */}
      <div className="voice-tab-row">
        <button
          type="button"
          className={`voice-tab ${mode === 'upload' ? 'active' : ''}`}
          onClick={() => setMode('upload')}
          id="tab-upload-file"
        >
          <UploadCloud size={14} /> Upload File
        </button>
        <button
          type="button"
          className={`voice-tab ${mode === 'record' ? 'active' : ''}`}
          onClick={() => setMode('record')}
          id="tab-record-mic"
        >
          <Mic size={14} /> Record Live
        </button>
      </div>

      {/* Upload Panel */}
      {mode === 'upload' && !hasFile && (
        <div
          className={`voice-drop-zone ${isDragging ? 'dragging' : ''}`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          id="voice-sample-dropzone"
        >
          <input ref={fileInputRef} type="file" accept="audio/*" style={{ display: 'none' }} onChange={handleFileChange} />
          <div className="drop-zone-icon">
            <UploadCloud size={32} />
          </div>
          <div>
            <p style={{ fontWeight: 600, marginBottom: '4px' }}>
              {isDragging ? 'Drop audio file here' : 'Click to browse or drag & drop'}
            </p>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
              WAV · MP3 · FLAC · M4A · OGG — Clear speech or singing voice
            </p>
          </div>
          <div className="format-chips">
            {['WAV', 'MP3', 'FLAC', 'M4A'].map((f) => (
              <span key={f} className="format-chip">{f}</span>
            ))}
          </div>
        </div>
      )}

      {/* Record Panel */}
      {mode === 'record' && !hasFile && (
        <div className="record-panel">
          {/* Mic Level Meter */}
          <div className="mic-meter-wrap">
            <div className="mic-meter-label">
              <Activity size={14} color="var(--accent-rose)" />
              <span>Microphone Level</span>
            </div>
            <div className="mic-meter-track">
              <div
                className={`mic-meter-fill ${isRecording ? 'active' : ''}`}
                style={{ width: `${micLevel * 100}%` }}
              />
            </div>
          </div>

          {isRecording ? (
            <div className="record-active-state">
              <div className="rec-pulse-dot" />
              <span style={{ fontWeight: 600, color: 'var(--accent-rose)' }}>
                Recording — {formatTime(recordingSeconds)}
              </span>
              <button
                type="button"
                className="btn-primary"
                onClick={stopRecording}
                style={{ background: 'var(--accent-rose)', padding: '10px 20px' }}
                id="btn-stop-mic"
              >
                <Square size={15} /> Stop & Save
              </button>
            </div>
          ) : (
            <div className="record-idle-state">
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textAlign: 'center' }}>
                Sing or speak clearly for 10–60 seconds in a quiet room. Echo cancellation is enabled automatically.
              </p>
              <button
                type="button"
                className="btn-primary"
                onClick={startRecording}
                style={{ background: 'var(--accent-rose)' }}
                id="btn-start-mic"
              >
                <Mic size={16} /> Start Recording
              </button>
            </div>
          )}
        </div>
      )}

      {/* File Loaded: Waveform + Controls */}
      {hasFile && (
        <div className="voice-loaded-card">
          {/* File Header */}
          <div className="voice-file-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ padding: '8px', borderRadius: '10px', background: 'rgba(16,185,129,0.12)', color: 'var(--accent-emerald)' }}>
                <CheckCircle2 size={20} />
              </div>
              <div>
                <p style={{ fontWeight: 600, fontSize: '0.92rem', color: 'var(--text-main)' }}>
                  {selectedFile?.name}
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
                  {meta && (
                    <>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                        {formatTime(meta.duration)} • {meta.sizeKB}KB • {meta.format}
                      </span>
                      {badge && (
                        <span style={{
                          fontSize: '0.7rem', fontWeight: 700, color: badge.color,
                          background: badge.ok ? `${badge.color}18` : 'rgba(244,63,94,0.1)',
                          padding: '1px 7px', borderRadius: '99px'
                        }}>
                          {badge.label}
                        </span>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
            <button
              type="button"
              className="btn-secondary"
              onClick={handleRemove}
              style={{ padding: '6px 8px', borderRadius: '8px' }}
              id="btn-remove-voice"
            >
              <X size={15} />
            </button>
          </div>

          {/* Waveform Canvas */}
          <div className="waveform-canvas-wrap" onClick={(e) => {
            if (!audioMeta || !audioPlayerRef.current) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const pct = (e.clientX - rect.left) / rect.width;
            const newTime = pct * audioMeta.duration;
            audioPlayerRef.current.currentTime = newTime;
            setCurrentTime(newTime);
          }}>
            <canvas
              ref={canvasRef}
              width={560}
              height={60}
              style={{ width: '100%', height: '60px', cursor: 'pointer', borderRadius: '8px' }}
            />
            {/* Trim range overlay lines */}
            {showTrimmer && (
              <>
                <div className="trim-line start" style={{ left: `${trimStart}%` }} />
                <div className="trim-line end" style={{ left: `${trimEnd}%` }} />
                <div className="trim-region" style={{ left: `${trimStart}%`, width: `${trimEnd - trimStart}%` }} />
              </>
            )}
          </div>

          {/* Playback + Time */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn-primary"
              onClick={togglePreview}
              style={{ width: '38px', height: '38px', padding: 0, borderRadius: '50%', flexShrink: 0 }}
              id="btn-preview-voice"
            >
              {isPlayingPreview ? <Pause size={15} /> : <Play size={15} style={{ marginLeft: '2px' }} />}
            </button>

            <span style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', minWidth: '80px' }}>
              {formatTime(currentTime)} / {meta ? formatTime(meta.duration) : '0:00'}
            </span>

            <div style={{ display: 'flex', gap: '8px', marginLeft: 'auto' }}>
              {/* Trim Toggle */}
              <button
                type="button"
                className={`btn-secondary ${showTrimmer ? 'active' : ''}`}
                onClick={(e) => { e.stopPropagation(); setShowTrimmer((v) => !v); }}
                style={{ fontSize: '0.78rem', padding: '6px 12px', borderColor: showTrimmer ? 'var(--secondary)' : undefined }}
                id="btn-toggle-trimmer"
              >
                <Scissors size={13} />
                <span>Trim</span>
              </button>
              {/* Replace */}
              <button
                type="button"
                className="btn-secondary"
                onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                id="btn-replace-voice"
              >
                <UploadCloud size={13} />
                <span>Replace</span>
              </button>
            </div>
          </div>

          {/* Trim Sliders */}
          {showTrimmer && (
            <div className="trim-controls">
              <div className="trim-slider-row">
                <span className="trim-label">
                  <Scissors size={12} /> Trim Start
                </span>
                <input
                  type="range" min={0} max={trimEnd - 1} value={trimStart}
                  onChange={(e) => setTrimStart(Number(e.target.value))}
                  className="trim-slider"
                  id="trim-start-slider"
                />
                <span className="trim-time-badge">
                  {meta ? formatTime((trimStart / 100) * meta.duration) : '0:00'}
                </span>
              </div>
              <div className="trim-slider-row">
                <span className="trim-label">
                  <Scissors size={12} /> Trim End
                </span>
                <input
                  type="range" min={trimStart + 1} max={100} value={trimEnd}
                  onChange={(e) => setTrimEnd(Number(e.target.value))}
                  className="trim-slider"
                  id="trim-end-slider"
                />
                <span className="trim-time-badge">
                  {meta ? formatTime((trimEnd / 100) * meta.duration) : '0:00'}
                </span>
              </div>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                Selected: {meta ? formatTime(((trimEnd - trimStart) / 100) * meta.duration) : '0:00'} of audio will be used
              </p>
            </div>
          )}

          {/* Tips */}
          {meta && !badge?.ok && (
            <div className="voice-tip warning">
              <AlertTriangle size={14} />
              <span>Sample is too short. Record at least 10 seconds of clean singing for best voice cloning results.</span>
            </div>
          )}
          {meta && badge?.ok && (
            <div className="voice-tip success">
              <Volume2 size={14} />
              <span>Great sample! Denoising & normalization will be applied automatically in Step 3 of the pipeline.</span>
            </div>
          )}

          {/* Hidden audio element */}
          <audio
            ref={audioPlayerRef}
            src={audioUrl || undefined}
            onTimeUpdate={handleTimeUpdate}
            onEnded={() => setIsPlayingPreview(false)}
            style={{ display: 'none' }}
          />
          {/* Hidden file input for replace */}
          <input ref={fileInputRef} type="file" accept="audio/*" style={{ display: 'none' }} onChange={handleFileChange} />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="voice-tip warning">
          <AlertTriangle size={14} />
          <span>{error}</span>
        </div>
      )}

      {/* Consent Checkbox */}
      <div className="consent-box">
        <input
          type="checkbox"
          id="consent-check"
          checked={consentGiven}
          onChange={(e) => onConsentChange(e.target.checked)}
        />
        <label htmlFor="consent-check" style={{ cursor: 'pointer' }}>
          <strong>Voice Cloning Consent:</strong> I confirm I have explicit permission from the voice owner to clone this voice.
          The final music output will be clearly tagged as AI-generated.
        </label>
      </div>
    </div>
  );
};
