import React, { useState, useRef, useEffect } from 'react';
import { 
  Play, 
  Pause, 
  Download, 
  Check, 
  Star 
} from 'lucide-react';
import type { VariantInfo } from '../types';

interface VariantPlayerProps {
  jobId: string;
  variant: VariantInfo;
  isSelected: boolean;
  onSelect: (variantNumber: number) => void;
}

export const VariantPlayer: React.FC<VariantPlayerProps> = ({
  jobId,
  variant,
  isSelected,
  onSelect,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(variant.duration_seconds || 30);
  const [activeStem, setActiveStem] = useState<'master' | 'vocal' | 'inst'>('master');
  
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Determine which audio stream URL to load based on selected stem
  const getAudioUrl = () => {
    if (activeStem === 'vocal' && variant.vocal_url) return variant.vocal_url;
    if (activeStem === 'inst' && variant.instrumental_url) return variant.instrumental_url;
    return variant.audio_url;
  };

  useEffect(() => {
    if (audioRef.current) {
      const wasPlaying = isPlaying;
      audioRef.current.src = getAudioUrl();
      audioRef.current.currentTime = currentTime;
      if (wasPlaying) {
        audioRef.current.play().catch(() => setIsPlaying(false));
      }
    }
  }, [activeStem]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().catch(() => setIsPlaying(false));
      setIsPlaying(true);
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
      if (audioRef.current.duration && !isNaN(audioRef.current.duration)) {
        setDuration(audioRef.current.duration);
      }
    }
  };

  const handleSeek = (percentage: number) => {
    if (audioRef.current) {
      const newTime = percentage * duration;
      audioRef.current.currentTime = newTime;
      setCurrentTime(newTime);
    }
  };

  const handleDownload = () => {
    window.location.href = `/api/song/${jobId}/download/${variant.variant_number}`;
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const waveformPeaks = variant.waveform_data || Array(60).fill(0.35);

  return (
    <div 
      className={`variant-player-card ${isSelected ? 'selected' : ''}`}
      id={`variant-player-${variant.variant_number}`}
    >
      <audio
        ref={audioRef}
        src={getAudioUrl()}
        onTimeUpdate={handleTimeUpdate}
        onEnded={() => setIsPlaying(false)}
        preload="metadata"
      />

      {/* Header Info */}
      <div className="player-header">
        <div className="player-title-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{
              background: 'rgba(99, 102, 241, 0.2)',
              color: 'var(--primary-light)',
              fontWeight: 700,
              fontSize: '0.78rem',
              padding: '2px 8px',
              borderRadius: '4px'
            }}>
              Version {variant.variant_number}
            </span>
            <h3>{variant.title}</h3>

            {/* Engine Badge */}
            {variant.is_demo || variant.engine === 'demo-tone' ? (
              <span style={{
                background: 'rgba(245, 158, 11, 0.2)',
                color: 'var(--accent-gold)',
                fontWeight: 600,
                fontSize: '0.72rem',
                padding: '2px 8px',
                borderRadius: '4px',
                border: '1px solid rgba(245, 158, 11, 0.35)'
              }}>
                ⚠️ Demo Tone (Fallback)
              </span>
            ) : (
              <span style={{
                background: 'rgba(16, 185, 129, 0.15)',
                color: 'var(--accent-emerald)',
                fontWeight: 600,
                fontSize: '0.72rem',
                padding: '2px 8px',
                borderRadius: '4px',
                border: '1px solid rgba(16, 185, 129, 0.3)'
              }}>
                ACE-Step 1.5
              </span>
            )}

            {/* Voice Conversion Badge */}
            <span style={{
              background: variant.voice_conversion && variant.voice_conversion !== 'none' ? 'rgba(99, 102, 241, 0.18)' : 'rgba(255, 255, 255, 0.05)',
              color: variant.voice_conversion && variant.voice_conversion !== 'none' ? 'var(--primary-light)' : 'var(--text-muted)',
              fontWeight: variant.voice_conversion && variant.voice_conversion !== 'none' ? 600 : 400,
              fontSize: '0.72rem',
              padding: '2px 8px',
              borderRadius: '4px',
              border: variant.voice_conversion && variant.voice_conversion !== 'none' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid var(--border-subtle)'
            }}>
              🎤 Voice: {variant.voice_conversion && variant.voice_conversion !== 'none' ? `${variant.voice_conversion.toUpperCase()} Cloned` : 'None (Passthrough)'}
            </span>
          </div>
          <p>
            Seed: <code>{variant.seed}</code> • Length: {formatTime(duration)} • -1 dBFS Peak Master
          </p>
        </div>

        {isSelected && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(245, 158, 11, 0.15)',
            border: '1px solid rgba(245, 158, 11, 0.4)',
            color: 'var(--accent-gold)',
            fontSize: '0.78rem',
            fontWeight: 700,
            padding: '4px 10px',
            borderRadius: '999px'
          }}>
            <Star size={12} fill="#f59e0b" />
            <span>Chosen Best</span>
          </div>
        )}
      </div>

      {/* Demo Tone Notice Banner */}
      {(variant.is_demo || variant.engine === 'demo-tone') && (
        <div style={{
          background: 'rgba(245, 158, 11, 0.08)',
          border: '1px solid rgba(245, 158, 11, 0.25)',
          borderRadius: 'var(--radius-sm)',
          padding: '8px 12px',
          fontSize: '0.78rem',
          color: 'var(--accent-gold)',
          marginBottom: '8px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <span>⚠️</span>
          <span><strong>Demo Preview Tone:</strong> Cloud GPU is offline. This audio is a synthesized melodic preview tone, not a real ACE-Step generated song.</span>
        </div>
      )}

      {/* Waveform Scrubber */}
      <div 
        className="waveform-container"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const clickX = e.clientX - rect.left;
          handleSeek(clickX / rect.width);
        }}
      >
        {waveformPeaks.map((peak, idx) => {
          const barProgress = idx / waveformPeaks.length;
          const currentProgress = duration > 0 ? currentTime / duration : 0;
          const isPlayed = barProgress <= currentProgress;
          const isCurrent = Math.abs(barProgress - currentProgress) < 0.02;

          return (
            <div
              key={idx}
              className={`waveform-bar ${isPlayed ? 'played' : ''} ${isCurrent ? 'current' : ''}`}
              style={{ height: `${Math.max(15, peak * 100)}%` }}
            />
          );
        })}
      </div>

      {/* Controls & Stems Row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Play/Pause Button */}
          <button
            className="btn-primary"
            onClick={togglePlay}
            style={{ width: '42px', height: '42px', padding: 0, borderRadius: '50%' }}
            id={`btn-play-variant-${variant.variant_number}`}
          >
            {isPlaying ? <Pause size={18} /> : <Play size={18} style={{ marginLeft: '2px' }} />}
          </button>

          {/* Time Display */}
          <span style={{ fontSize: '0.82rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>

          {/* Stem Solo Selector */}
          <div className="stem-selector">
            <button
              className={`stem-btn ${activeStem === 'master' ? 'active' : ''}`}
              onClick={() => setActiveStem('master')}
            >
              Master Mix
            </button>
            <button
              className={`stem-btn ${activeStem === 'vocal' ? 'active' : ''}`}
              onClick={() => setActiveStem('vocal')}
            >
              {variant.voice_conversion && variant.voice_conversion !== 'none' ? 'Cloned Vocal Solo' : 'Vocal Solo (Passthrough)'}
            </button>
            <button
              className={`stem-btn ${activeStem === 'inst' ? 'active' : ''}`}
              onClick={() => setActiveStem('inst')}
            >
              Instrumental
            </button>
          </div>
        </div>

        {/* Action Buttons: Pick Favorite & Download */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            className="btn-secondary"
            onClick={() => onSelect(variant.variant_number)}
            style={{
              borderColor: isSelected ? 'var(--accent-gold)' : undefined,
              color: isSelected ? 'var(--accent-gold)' : undefined
            }}
            id={`btn-select-variant-${variant.variant_number}`}
          >
            <Check size={15} />
            <span>{isSelected ? 'Selected' : 'Pick as Favorite'}</span>
          </button>

          <button
            className="btn-primary"
            onClick={handleDownload}
            style={{ fontSize: '0.85rem', padding: '8px 16px' }}
            id={`btn-download-variant-${variant.variant_number}`}
          >
            <Download size={15} />
            <span>Download</span>
          </button>
        </div>
      </div>
    </div>
  );
};
