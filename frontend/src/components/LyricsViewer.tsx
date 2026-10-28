import React, { useState } from 'react';
import { Copy, Check, BookOpen } from 'lucide-react';
import type { Language } from '../types';

interface LyricsViewerProps {
  language: Language;
  displayLyrics: string;
  sungLyrics?: string;
  lyricsSource?: string;
}

export const LyricsViewer: React.FC<LyricsViewerProps> = ({
  language,
  displayLyrics,
  sungLyrics,
  lyricsSource,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(displayLyrics);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isPashto = language === 'pashto';

  const renderSourceBadge = () => {
    if (!lyricsSource) return null;
    if (lyricsSource === 'user') {
      return (
        <span style={{
          background: 'rgba(99, 102, 241, 0.15)',
          color: 'var(--primary-light)',
          fontSize: '0.74rem',
          padding: '2px 8px',
          borderRadius: '4px',
          border: '1px solid var(--border-glow)'
        }}>
          ✍️ User Provided
        </span>
      );
    }
    if (lyricsSource === 'gemini') {
      return (
        <span style={{
          background: 'rgba(16, 185, 129, 0.15)',
          color: 'var(--accent-emerald)',
          fontSize: '0.74rem',
          padding: '2px 8px',
          borderRadius: '4px',
          border: '1px solid rgba(16, 185, 129, 0.3)'
        }}>
          ✨ AI Composed (Gemini)
        </span>
      );
    }
    if (lyricsSource === 'template') {
      return (
        <span style={{
          background: 'rgba(245, 158, 11, 0.15)',
          color: 'var(--accent-gold)',
          fontSize: '0.74rem',
          padding: '2px 8px',
          borderRadius: '4px',
          border: '1px solid rgba(245, 158, 11, 0.3)'
        }}>
          📜 Curated Template (Fallback)
        </span>
      );
    }
    return (
      <span style={{
        background: 'rgba(255, 255, 255, 0.05)',
        color: 'var(--text-muted)',
        fontSize: '0.74rem',
        padding: '2px 8px',
        borderRadius: '4px'
      }}>
        Source: {lyricsSource}
      </span>
    );
  };

  return (
    <div className="glass-panel" style={{ padding: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BookOpen size={20} color="#818cf8" />
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>
            Song Lyrics ({language.toUpperCase()})
          </h3>
          {renderSourceBadge()}
        </div>

        <button
          className="btn-secondary"
          onClick={handleCopy}
          style={{ fontSize: '0.78rem', padding: '4px 10px' }}
        >
          {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
          <span>{copied ? 'Copied!' : 'Copy Lyrics'}</span>
        </button>
      </div>

      {isPashto && sungLyrics && (
        <div style={{ 
          background: 'rgba(6, 182, 212, 0.08)',
          border: '1px solid rgba(6, 182, 212, 0.25)',
          borderRadius: 'var(--radius-sm)',
          padding: '8px 12px',
          marginBottom: '14px',
          fontSize: '0.8rem',
          color: 'var(--secondary)'
        }}>
          💡 <strong>Pashto Dual-Lyrics Active:</strong> Displaying authentic Pashto script on the left, and experimental phonetic singing respelling on the right.
        </div>
      )}

      <div className={isPashto && sungLyrics ? 'dual-lyrics-container' : ''}>
        {/* Native Script Pane */}
        <div className="lyrics-pane">
          <h4>{isPashto ? 'Proper Pashto Script (د پښتو اصلي متن)' : 'Urdu Script (اردو کلام)'}</h4>
          <div className={`lyrics-content ${isPashto ? 'pashto' : 'urdu'}`}>
            {displayLyrics}
          </div>
        </div>

        {/* Pashto Phonetic Sung Spelling Pane */}
        {isPashto && sungLyrics && (
          <div className="lyrics-pane">
            <h4 style={{ color: 'var(--secondary)' }}>
              Phonetic Singing Script (ACE-Step Model Input)
            </h4>
            <div className="lyrics-content pashto" style={{ opacity: 0.85 }}>
              {sungLyrics}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
