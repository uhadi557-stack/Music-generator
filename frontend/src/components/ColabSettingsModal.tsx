import React, { useState } from 'react';
import { X, Cloud, CheckCircle, AlertTriangle, Copy, Check } from 'lucide-react';
import type { AppConfig } from '../types';

interface ColabSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: AppConfig;
  onConfigUpdated: (newConfig: AppConfig) => void;
}

export const ColabSettingsModal: React.FC<ColabSettingsModalProps> = ({
  isOpen,
  onClose,
  config,
  onConfigUpdated,
}) => {
  const [cloudGpuUrl, setCloudGpuUrl] = useState(config.cloud_gpu_url || '');
  const [geminiApiKey, setGeminiApiKey] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle');
  const [testDetail, setTestDetail] = useState('');
  const [copiedCell, setCopiedCell] = useState(false);

  if (!isOpen) return null;

  const colabCommand = `!git clone https://github.com/ACE-Step/ACE-Step-1.5.git /content/ACE-Step-1.5
%cd /content/ACE-Step-1.5
!pip install -q fastapi uvicorn gradio soundfile torch torchaudio pydub requests diffusers
# Upload cloud_colab/colab_ace_step_runner.py to /content/ACE-Step-1.5/ and run:
!python colab_ace_step_runner.py
# (Or open cloud_colab/suroor_ai_colab_runner.ipynb in Google Colab)`;

  const copyColabCode = () => {
    navigator.clipboard.writeText(colabCommand);
    setCopiedCell(true);
    setTimeout(() => setCopiedCell(false), 2000);
  };

  const handleTestConnection = async () => {
    if (!cloudGpuUrl.trim()) {
      alert('Please enter a Cloud GPU URL to test.');
      return;
    }
    setTestStatus('testing');
    setTestDetail('');
    try {
      const resp = await fetch('/api/config/cloud-gpu/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: cloudGpuUrl.trim() }),
      });
      const data = await resp.json();
      if (resp.ok && data.status === 'connected') {
        setTestStatus('success');
        setTestDetail(data.detail || 'Connected to Cloud GPU server successfully!');
      } else {
        setTestStatus('failed');
        setTestDetail(data.detail || 'Cloud GPU server could not be reached.');
      }
    } catch (err) {
      setTestStatus('failed');
      setTestDetail('Backend error testing cloud connection.');
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const resp = await fetch('/api/config/cloud-gpu', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cloud_gpu_url: cloudGpuUrl.trim(),
          gemini_api_key: geminiApiKey.trim() || undefined,
        }),
      });
      if (resp.ok) {
        let freshStatus: 'not_configured' | 'unreachable' | 'connected' = 'not_configured';
        try {
          const h = await (await fetch('/api/health')).json();
          freshStatus = h.cloud_gpu_status;
        } catch {}

        onConfigUpdated({
          cloud_gpu_url: cloudGpuUrl.trim(),
          has_gemini_key: Boolean(geminiApiKey.trim() || config.has_gemini_key),
          cloud_gpu_status: freshStatus,
        });
        onClose();
      }
    } catch (err) {
      console.error(err);
      alert('Failed to save settings.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose} id="colab-settings-modal">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Cloud size={24} color="#06b6d4" />
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Free Cloud GPU (Colab / Kaggle)</h2>
          </div>
          <button className="btn-secondary" onClick={onClose} style={{ padding: '6px' }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ fontSize: '0.88rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
          Since your computer has no dedicated local GPU, neural song generation (ACE-Step 1.5) runs on a free cloud GPU like Google Colab or Kaggle.
          If no cloud GPU is configured or reachable, song generation requires connecting one, or enabling demo fallback in your .env for synthetic preview tones.
        </div>

        {/* 1-Click Colab Code */}
        <div className="form-group">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <label className="form-label">
              <span>Google Colab Runner Cell (T4 GPU Free Tier)</span>
            </label>
            <button
              type="button"
              className="btn-secondary"
              onClick={copyColabCode}
              style={{ fontSize: '0.75rem', padding: '3px 8px' }}
            >
              {copiedCell ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
              <span>{copiedCell ? 'Copied' : 'Copy Cell'}</span>
            </button>
          </div>
          <pre className="code-box">{colabCommand}</pre>
        </div>

        {/* URL Input */}
        <div className="form-group">
          <label className="form-label" htmlFor="cloud-gpu-url-input">
            <span>Cloud GPU Public URL (*.gradio.live or ngrok)</span>
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              id="cloud-gpu-url-input"
              type="url"
              className="form-input"
              value={cloudGpuUrl}
              onChange={(e) => {
                setCloudGpuUrl(e.target.value);
                setTestStatus('idle');
                setTestDetail('');
              }}
              placeholder="e.g. https://12a34b56.gradio.live"
            />
            <button
              type="button"
              className="btn-secondary"
              onClick={handleTestConnection}
              style={{ whiteSpace: 'nowrap' }}
            >
              {testStatus === 'testing' ? 'Testing...' : 'Test Connection'}
            </button>
          </div>
          {testStatus === 'success' && (
            <p style={{ color: 'var(--accent-emerald)', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle size={14} /> {testDetail || 'Connected to Cloud GPU server successfully!'}
            </p>
          )}
          {testStatus === 'failed' && (
            <p style={{ color: 'var(--accent-rose)', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <AlertTriangle size={14} /> {testDetail || 'Could not reach runner. Check if Colab session is active.'}
            </p>
          )}
        </div>

        {/* Gemini API Key */}
        <div className="form-group">
          <label className="form-label" htmlFor="gemini-key-input">
            <span>Google Gemini API Key (Optional for Custom AI Lyrics)</span>
          </label>
          <input
            id="gemini-key-input"
            type="password"
            className="form-input"
            value={geminiApiKey}
            onChange={(e) => setGeminiApiKey(e.target.value)}
            placeholder={config.has_gemini_key ? '•••••••••••••••• (API Key Active)' : 'AIzaSy...'}
          />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            Free tier Google Gemini API key used for Step 2 verse/chorus lyrics generation.
          </span>
        </div>

        {/* Footer Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '10px' }}>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
};
