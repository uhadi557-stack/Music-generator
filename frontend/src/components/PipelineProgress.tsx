import React from 'react';
import { 
  CheckCircle2, 
  Loader2 
} from 'lucide-react';
import type { JobState } from '../types';

interface PipelineProgressProps {
  job: JobState;
}

const STEPS_CONFIG = [
  { step: 1, title: 'Input Received', desc: 'Validating language, theme, and voice sample', runsOn: 'Your computer' },
  { step: 2, title: 'Lyrics Composition', desc: 'Arranging verse/chorus and Pashto sung phonetics', runsOn: 'Cloud API (Gemini)' },
  { step: 3, title: 'Prepare Voice Sample', desc: 'Rumble filtering (80Hz HPF), silence trimming, and -1 dBFS peak normalization', runsOn: 'Your computer' },
  { step: 4, title: 'Compose Music & Vocals', desc: 'ACE-Step 1.5 generating 1–3 song variants', runsOn: 'Cloud GPU (Colab/Kaggle)' },
  { step: 5, title: 'Stems & Accompaniment', desc: 'Stems provided by generator (Phase 1)', runsOn: 'Generator' },
  { step: 6, title: 'Voice Conversion', desc: 'Zero-shot timbre transfer with RMVPE pitch tracking (Seed-VC on Cloud GPU)', runsOn: 'Cloud GPU' },
  { step: 7, title: 'Studio Enhance & Mix', desc: 'Peak normalization (-1 dBFS headroom) and final WAV master', runsOn: 'Your computer' },
  { step: 8, title: 'Song Variants Ready', desc: 'Listen, compare, pick favorite, and download master', runsOn: 'Your computer' },
];

export const PipelineProgress: React.FC<PipelineProgressProps> = ({ job }) => {
  const currentStep = job.current_step;
  const progressPercent = Math.min(100, Math.max(0, job.step_progress));

  return (
    <div className="pipeline-card glass-panel" id="pipeline-progress-panel">
      <div className="progress-header">
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>8-Step Audio Pipeline</span>
            {job.status === 'processing' && (
              <span style={{ fontSize: '0.8rem', color: 'var(--primary-light)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <Loader2 size={14} className="spinning" /> Live
              </span>
            )}
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Job ID: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--secondary)' }}>{job.job_id}</code>
          </p>
        </div>

        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-main)' }}>
            {Math.round(progressPercent)}%
          </span>
        </div>
      </div>

      {/* Main Progress Bar */}
      <div className="overall-bar-track">
        <div className="overall-bar-fill" style={{ width: `${progressPercent}%` }} />
      </div>

      {/* Live Status Message Callout */}
      <div style={{
        background: 'rgba(99, 102, 241, 0.08)',
        border: '1px solid rgba(99, 102, 241, 0.25)',
        borderRadius: 'var(--radius-md)',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}>
        {job.status === 'processing' ? (
          <Loader2 size={18} color="#818cf8" style={{ animation: 'spin 1.5s linear infinite' }} />
        ) : job.status === 'completed' ? (
          <CheckCircle2 size={18} color="#10b981" />
        ) : (
          <span className="status-dot pulsing" />
        )}
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)' }}>
            {job.step_name}
          </p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {job.message}
          </p>
        </div>
      </div>

      {/* Step Breakdown List */}
      <div className="step-list">
        {STEPS_CONFIG.map((s) => {
          const isDone = currentStep > s.step || job.status === 'completed';
          const isCurrent = currentStep === s.step && job.status === 'processing';

          return (
            <div
              key={s.step}
              className={`step-item ${isCurrent ? 'active' : ''} ${isDone ? 'completed' : ''}`}
            >
              <div className="step-num">
                {isDone ? (
                  <CheckCircle2 size={18} />
                ) : isCurrent ? (
                  <Loader2 size={16} style={{ animation: 'spin 1.5s linear infinite' }} />
                ) : (
                  <span>{s.step}</span>
                )}
              </div>

              <div className="step-meta">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span className="step-title">{s.title}</span>
                  <span style={{ 
                    fontSize: '0.72rem', 
                    color: s.runsOn.includes('Cloud GPU') ? 'var(--accent-gold)' : 'var(--text-dim)',
                    background: 'rgba(255,255,255,0.04)',
                    padding: '2px 8px',
                    borderRadius: '4px'
                  }}>
                    {s.runsOn}
                  </span>
                </div>
                <span className="step-desc">{s.desc}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
