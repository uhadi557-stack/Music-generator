import React, { useState, useEffect } from 'react';
import { Headphones, Sparkles } from 'lucide-react';
import type { AppConfig, JobState, LyricsPreviewResponse } from './types';
import { Header } from './components/Header';
import { SongInputForm } from './components/SongInputForm';
import { PipelineProgress } from './components/PipelineProgress';
import { VariantPlayer } from './components/VariantPlayer';
import { LyricsViewer } from './components/LyricsViewer';
import { ColabSettingsModal } from './components/ColabSettingsModal';

export const App: React.FC = () => {
  const [config, setConfig] = useState<AppConfig>({
    cloud_gpu_url: '',
    has_gemini_key: false,
  });
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [activeJob, setActiveJob] = useState<JobState | null>(null);
  const [lyricsPreview, setLyricsPreview] = useState<LyricsPreviewResponse | null>(null);
  const [selectedVariant, setSelectedVariant] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Reset to start a new song
  const handleReset = () => {
    setActiveJob(null);
    setLyricsPreview(null);
    setSelectedVariant(null);
    setIsLoading(false);
  };

  // Fetch initial config and health from backend
  useEffect(() => {
    const fetchConfigAndHealth = async () => {
      try {
        const [configRes, healthRes] = await Promise.all([
          fetch('/api/config'),
          fetch('/api/health'),
        ]);
        const configData = await configRes.json();
        const healthData = await healthRes.json();
        setConfig({
          cloud_gpu_url: configData.cloud_gpu_url || '',
          has_gemini_key: Boolean(configData.has_gemini_key),
          ffmpeg_available: healthData.ffmpeg_available,
          cloud_gpu_status: healthData.cloud_gpu_status,
          allow_demo_fallback: healthData.allow_demo_fallback,
        });
      } catch (err) {
        console.warn('Backend not yet reachable on /api/config', err);
      }
    };
    fetchConfigAndHealth();
  }, []);

  // Handle form submission to /api/song/start
  const handleStartGeneration = async (formData: FormData) => {
    setIsLoading(true);
    setSelectedVariant(null);
    setLyricsPreview(null);

    try {
      const resp = await fetch('/api/song/start', {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        const errData = await resp.json();
        alert(`Generation failed to start: ${errData.detail || 'Server error'}`);
        setIsLoading(false);
        return;
      }

      const data = await resp.json();
      const jobId = data.job_id;

      // Subscribe to live Server-Sent Events (SSE) stream
      const eventSource = new EventSource(`/api/song/${jobId}/stream`);

      eventSource.addEventListener('step_update', (e) => {
        try {
          const state: JobState = JSON.parse(e.data);
          setActiveJob(state);
        } catch (err) {
          console.error('Failed to parse SSE step update:', err);
        }
      });

      eventSource.addEventListener('completed', (e) => {
        try {
          const state: JobState = JSON.parse(e.data);
          setActiveJob(state);
          setIsLoading(false);
          eventSource.close();
        } catch (err) {
          console.error('Failed to parse SSE completion:', err);
        }
      });

      eventSource.addEventListener('error', (e) => {
        console.error('SSE Stream encountered an error or closed:', e);
        setIsLoading(false);
        eventSource.close();
        // Mark the active job as failed if it was still running
        setActiveJob((prev) => {
          if (prev && prev.status === 'processing') {
            return { ...prev, status: 'failed', message: 'Connection to backend lost. Please try again.' };
          }
          return prev;
        });
      });
    } catch (err) {
      console.error('Network error starting generation:', err);
      alert('Network error connecting to backend.');
      setIsLoading(false);
    }
  };

  // Handle choosing the best variant
  const handleSelectVariant = async (variantNumber: number) => {
    if (!activeJob) return;
    try {
      const resp = await fetch(`/api/song/${activeJob.job_id}/select`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ variant_number: variantNumber }),
      });
      if (resp.ok) {
        setSelectedVariant(variantNumber);
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="app-container">
      <Header config={config} onOpenSettings={() => setIsSettingsOpen(true)} />

      <main className="main-grid">
        {/* Left Column: Form & Inputs */}
        <section>
          <SongInputForm
            onSubmit={handleStartGeneration}
            isLoading={isLoading}
            onPreviewLyrics={setLyricsPreview}
          />
          {/* Reset button when a job is active */}
          {activeJob && (
            <div style={{ marginTop: '16px', textAlign: 'center' }}>
              <button
                className="btn-secondary"
                onClick={handleReset}
                id="btn-new-song"
                style={{ width: '100%', padding: '12px' }}
              >
                🎵 Start a New Song
              </button>
            </div>
          )}
        </section>

        {/* Right Column: Live Pipeline, Output Players, or Welcome */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* 1. Live Pipeline Progress Tracker (Active while running or completed) */}
          {activeJob && <PipelineProgress job={activeJob} />
          }
          {/* Pipeline Error State */}
          {activeJob && activeJob.status === 'failed' && (
            <div style={{
              padding: '16px 20px',
              background: 'rgba(244, 63, 94, 0.08)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--accent-rose)',
              fontSize: '0.88rem'
            }}>
              ⚠️ <strong>Pipeline Error:</strong> {activeJob.error || activeJob.message}
            </div>
          )}

          {/* 2. Finished Audio Players (Step 8: User Chooses) */}
          {activeJob && activeJob.status === 'completed' && activeJob.variants.length > 0 && (
            <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }} id="variants-comparison-panel">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Headphones size={22} color="#f59e0b" />
                    <span>Step 8: Compare &amp; Pick Your Song</span>
                  </h2>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Listen to the {activeJob.variants.length} musical versions. Toggle stems, select your favorite, and download.
                  </p>
                </div>
              </div>

              {/* Render all variants */}
              {activeJob.variants.map((v) => (
                <VariantPlayer
                  key={v.variant_number}
                  jobId={activeJob.job_id}
                  variant={v}
                  isSelected={selectedVariant === v.variant_number}
                  onSelect={handleSelectVariant}
                />
              ))}
            </div>
          )}

          {/* 3. Lyrics Viewer (When available from Job or Preview) */}
          {activeJob && activeJob.display_lyrics && activeJob.current_step >= 2 && (
            <LyricsViewer
              language={activeJob.language}
              displayLyrics={activeJob.display_lyrics}
              sungLyrics={activeJob.sung_lyrics}
              lyricsSource={activeJob.lyrics_source}
            />
          )}

          {/* If user clicked 'Preview Lyrics' before generating full song */}
          {!activeJob && lyricsPreview && (
            <LyricsViewer
              language={lyricsPreview.language}
              displayLyrics={lyricsPreview.display_lyrics}
              sungLyrics={lyricsPreview.sung_lyrics}
              lyricsSource={lyricsPreview.source}
            />
          )}

          {/* 4. Idle / Overview Welcome Panel */}
          {!activeJob && !lyricsPreview && (
            <div className="glass-panel" style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '42px',
                  height: '42px',
                  borderRadius: '12px',
                  background: 'rgba(99, 102, 241, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--primary-light)'
                }}>
                  <Sparkles size={22} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>How the System Works</h3>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-dim)' }}>Complete 8-step pipeline overview</p>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-gold)', fontWeight: 600, fontSize: '0.9rem', marginBottom: '4px' }}>
                    <span>📜 Dual-Script Pashto</span>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Offers experimental phonetic respelling for singing models alongside authentic Pashto script in the viewer.
                  </p>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--secondary)', fontWeight: 600, fontSize: '0.9rem', marginBottom: '4px' }}>
                    <span>🎤 Singing Voice Conversion</span>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Zero-shot Seed-VC voice conversion on Cloud GPU preserves pitch and melody contour while rendering vocals in your voice timbre.
                  </p>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary-light)', fontWeight: 600, fontSize: '0.9rem', marginBottom: '4px' }}>
                    <span>☁️ Free Cloud GPU</span>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Connect a free Google Colab T4 GPU to run real ACE-Step 1.5 music generation without local GPU hardware.
                  </p>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-emerald)', fontWeight: 600, fontSize: '0.9rem', marginBottom: '4px' }}>
                    <span>🎚️ 3 Variants Comparison</span>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Generates 1 to 3 distinct seed interpretations. Solo vocals or backing tracks, then pick the best version to export.
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>
      </main>

      {/* Cloud GPU & Settings Modal */}
      <ColabSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        config={config}
        onConfigUpdated={setConfig}
      />
    </div>
  );
};
export default App;
