import React, { useState } from 'react';
import { Wand2 } from 'lucide-react';
import type { Language, Genre, LyricsPreviewResponse } from '../types';
import { VoiceSampleUploader } from './VoiceSampleUploader';
import { StanzasEditor } from './StanzasEditor';

interface SongInputFormProps {
  onSubmit: (formData: FormData) => void;
  isLoading: boolean;
  onPreviewLyrics: (preview: LyricsPreviewResponse) => void;
}

const GENRES: { key: Genre; label: string; icon: string }[] = [
  { key: 'ghazal',       label: 'Ghazal (غزل)',       icon: '📜' },
  { key: 'sufi',         label: 'Sufi Kalam (صوفی)',   icon: '🕊️' },
  { key: 'pop',          label: 'Modern Pop (پاپ)',    icon: '✨' },
  { key: 'folk_attan',   label: 'Pashto Attan (اتڼ)', icon: '🥁' },
  { key: 'rubab_ballad', label: 'Rubab Ballad (رباب)', icon: '🪕' },
  { key: 'qawwali',      label: 'Qawwali (قوالی)',     icon: '👏' },
  { key: 'lofi',         label: 'Lo-Fi Chill (لو فائی)', icon: '☕' },
  { key: 'acoustic',     label: 'Acoustic Soul',       icon: '🎸' },
];

export const SongInputForm: React.FC<SongInputFormProps> = ({
  onSubmit,
  isLoading,
  onPreviewLyrics,
}) => {
  const [language, setLanguage] = useState<Language>('urdu');
  const [genre, setGenre] = useState<Genre>('ghazal');
  const [theme, setTheme] = useState<string>('Nostalgic longing and beauty of autumn evenings in Lahore');
  const [stanzas, setStanzas] = useState<string>('');
  const [variants, setVariants] = useState<number>(3);
  const [dialect, setDialect] = useState<'peshawar' | 'kandahari'>('peshawar');
  const [enableVoiceCloning, setEnableVoiceCloning] = useState<boolean>(false);
  const [voiceFile, setVoiceFile] = useState<File | null>(null);
  const [consentGiven, setConsentGiven] = useState<boolean>(true);

  // Switch default genre and theme when language changes
  const handleLanguageChange = (newLang: Language) => {
    setLanguage(newLang);
    if (newLang === 'pashto') {
      if (genre === 'ghazal') setGenre('rubab_ballad');
      setTheme('Love, loyalty, and mountain breeze of the Khyber pass');
    } else {
      if (genre === 'rubab_ballad' || genre === 'folk_attan') setGenre('ghazal');
      setTheme('Nostalgic longing and beauty of autumn evenings in Lahore');
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (enableVoiceCloning) {
      if (!voiceFile) {
        alert('Please upload or record a voice sample, or switch to AI Vocalist mode.');
        return;
      }
      if (!consentGiven) {
        alert('Please confirm voice cloning consent before proceeding.');
        return;
      }
    }

    const formData = new FormData();
    formData.append('language', language);
    formData.append('theme', theme);
    formData.append('genre', genre);
    formData.append('variants', variants.toString());
    formData.append('dialect', dialect);
    if (stanzas.trim()) {
      formData.append('stanzas', stanzas.trim());
    }
    if (enableVoiceCloning && voiceFile) {
      formData.append('voice_sample', voiceFile);
    }

    onSubmit(formData);
  };

  return (
    <form className="form-section glass-panel" onSubmit={handleSubmit} id="song-input-form">
      <div className="section-header">
        <h2 className="section-title">
          <Wand2 size={20} color="#818cf8" />
          <span>Song Setup &amp; Voice Input</span>
        </h2>
        <span className="step-badge">Pipeline 1–3</span>
      </div>

      {/* Language Picker */}
      <div className="form-group">
        <label className="form-label">
          <span>Target Language</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            Urdu (native) · Pashto (dual-script bridge)
          </span>
        </label>
        <div className="lang-selector">
          <div
            className={`lang-card urdu-card ${language === 'urdu' ? 'active' : ''}`}
            onClick={() => handleLanguageChange('urdu')}
            id="lang-pick-urdu"
          >
            <span className="native-title">اردو</span>
            <span className="lang-en">Urdu · Ghazal, Sufi &amp; Pop</span>
          </div>
          <div
            className={`lang-card pashto-card ${language === 'pashto' ? 'active' : ''}`}
            onClick={() => handleLanguageChange('pashto')}
            id="lang-pick-pashto"
          >
            <span className="native-title">پښتو</span>
            <span className="lang-en">Pashto · Rubab &amp; Attan (Dual Script)</span>
          </div>
        </div>
      </div>

      {/* Pashto Dialect (Northern / Peshawar vs Southern / Kandahari) */}
      {language === 'pashto' && (
        <div className="form-group" style={{ marginTop: '-4px' }}>
          <label className="form-label">
            <span>Pashto Dialect (Experimental Phonetic Spelling)</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
              Adapts ښ / ږ pronunciation for singing models
            </span>
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div
              className={`genre-pill ${dialect === 'peshawar' ? 'active' : ''}`}
              onClick={() => setDialect('peshawar')}
              style={{ padding: '10px 14px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', textAlign: 'center' }}
            >
              <div style={{ fontWeight: 600 }}>Peshawar (Northern / Yusufzai)</div>
              <div style={{ fontSize: '0.72rem', opacity: 0.8 }}>Default · ښ→خ, ږ→ګ</div>
            </div>
            <div
              className={`genre-pill ${dialect === 'kandahari' ? 'active' : ''}`}
              onClick={() => setDialect('kandahari')}
              style={{ padding: '10px 14px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', textAlign: 'center' }}
            >
              <div style={{ fontWeight: 600 }}>Kandahari (Southern)</div>
              <div style={{ fontSize: '0.72rem', opacity: 0.8 }}>Alternative · ښ→ش, ږ→ژ</div>
            </div>
          </div>
        </div>
      )}

      {/* Musical Genre */}
      <div className="form-group">
        <label className="form-label">
          <span>Musical Genre &amp; Arrangement Style</span>
        </label>
        <div className="genre-grid">
          {GENRES.map((g) => (
            <div
              key={g.key}
              className={`genre-pill ${genre === g.key ? 'active' : ''}`}
              onClick={() => setGenre(g.key)}
              id={`genre-${g.key}`}
            >
              <span>{g.icon} {g.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Theme / Mood */}
      <div className="form-group">
        <label className="form-label" htmlFor="song-theme-input">
          <span>Song Theme / Mood Prompt</span>
        </label>
        <input
          id="song-theme-input"
          type="text"
          className="form-input"
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          placeholder="e.g. Romantic sufi melody with tabla, night rain, yearning for home"
          required
        />
      </div>

      {/* ─── Enhanced Stanzas Editor ─── */}
      <StanzasEditor
        language={language}
        genre={genre}
        theme={theme}
        value={stanzas}
        dialect={dialect}
        onChange={setStanzas}
        onPreviewLyrics={onPreviewLyrics}
      />

      {/* ─── Voice Cloning Mode (Optional) ─── */}
      <div className="form-group voice-mode-section">
        <label className="form-label">
          <span>Vocals &amp; Singer Timbre</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--accent-indigo)', fontWeight: 600 }}>
            {enableVoiceCloning ? 'Voice Cloning: ON' : 'Voice Cloning: OPTIONAL (Skipped)'}
          </span>
        </label>

        <div className="voice-mode-cards" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '14px' }}>
          <div
            className={`voice-mode-card ${!enableVoiceCloning ? 'active' : ''}`}
            onClick={() => setEnableVoiceCloning(false)}
            id="voice-mode-ai"
            style={{
              padding: '12px 14px',
              borderRadius: '10px',
              border: !enableVoiceCloning ? '1.5px solid var(--accent-indigo)' : '1px solid var(--border)',
              background: !enableVoiceCloning ? 'rgba(99, 102, 241, 0.14)' : 'rgba(255, 255, 255, 0.03)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}
          >
            <span style={{ fontSize: '1.5rem' }}>✨</span>
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.92rem', color: 'var(--text-main)' }}>Default AI Vocalist</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Instant · Natural studio voice</div>
            </div>
          </div>

          <div
            className={`voice-mode-card ${enableVoiceCloning ? 'active' : ''}`}
            onClick={() => setEnableVoiceCloning(true)}
            id="voice-mode-clone"
            style={{
              padding: '12px 14px',
              borderRadius: '10px',
              border: enableVoiceCloning ? '1.5px solid var(--accent-indigo)' : '1px solid var(--border)',
              background: enableVoiceCloning ? 'rgba(99, 102, 241, 0.14)' : 'rgba(255, 255, 255, 0.03)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}
          >
            <span style={{ fontSize: '1.5rem' }}>🎤</span>
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.92rem', color: 'var(--text-main)' }}>Clone My Voice (Seed-VC)</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Zero-shot conversion via Cloud GPU</div>
            </div>
          </div>
        </div>

        {enableVoiceCloning ? (
          <VoiceSampleUploader
            selectedFile={voiceFile}
            onFileSelected={setVoiceFile}
            consentGiven={consentGiven}
            onConsentChange={setConsentGiven}
          />
        ) : (
          <div
            style={{
              padding: '14px 16px',
              borderRadius: '10px',
              background: 'rgba(99, 102, 241, 0.05)',
              border: '1px dashed rgba(99, 102, 241, 0.25)',
              fontSize: '0.85rem',
              color: 'var(--text-dim)',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}
          >
            <span style={{ fontSize: '1.3rem' }}>💡</span>
            <span>
              Voice cloning is <strong>optional and currently skipped</strong>. The song will be performed by native AI vocalists fine-tuned for {language === 'urdu' ? 'Urdu Ghazal / Sufi' : 'Pashto'} melody. Click <em>"Clone My Voice"</em> above if you want to sing it with your own voice!
            </span>
          </div>
        )}
      </div>

      {/* Number of Variants */}
      <div className="form-group">
        <label className="form-label">
          <span>Number of Song Variants to Compose</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            Each uses a different musical seed
          </span>
        </label>
        <div className="variants-picker">
          {[1, 2, 3].map((v) => (
            <div
              key={v}
              className={`variant-btn ${variants === v ? 'active' : ''}`}
              onClick={() => setVariants(v)}
              id={`variants-pick-${v}`}
            >
              <span className="v-count">{v}</span>
              <span className="v-label">{v === 1 ? '1 Version' : `${v} Versions`}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        className="btn-primary"
        disabled={isLoading || (enableVoiceCloning && (!voiceFile || !consentGiven))}
        style={{ padding: '16px', fontSize: '1.05rem', marginTop: '6px' }}
        id="btn-start-generation"
      >
        <Wand2 size={20} />
        <span>
          {isLoading
            ? 'Composing in Progress…'
            : enableVoiceCloning
            ? 'Start Song Generation (Cloned Voice)'
            : 'Start Song Generation (AI Vocalist)'}
        </span>
      </button>
    </form>
  );
};
