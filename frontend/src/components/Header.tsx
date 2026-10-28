import React from 'react';
import { Music2, Settings } from 'lucide-react';
import type { AppConfig } from '../types';

interface HeaderProps {
  config: AppConfig;
  onOpenSettings: () => void;
}

export const Header: React.FC<HeaderProps> = ({ config, onOpenSettings }) => {
  const status = config.cloud_gpu_status || (config.cloud_gpu_url ? 'unreachable' : 'not_configured');

  let dotClass = '';
  let statusLabel = 'Cloud GPU: Not Configured';
  let statusTooltip = 'No Cloud GPU URL configured. Click to connect Google Colab.';

  if (status === 'connected') {
    dotClass = 'active pulsing';
    statusLabel = 'Cloud GPU (Connected)';
    statusTooltip = `Connected to ${config.cloud_gpu_url}`;
  } else if (status === 'unreachable') {
    dotClass = 'error';
    statusLabel = 'Cloud GPU (Unreachable)';
    statusTooltip = `Cloud GPU at ${config.cloud_gpu_url || 'URL'} could not be reached.`;
  } else {
    dotClass = '';
    statusLabel = 'Cloud GPU: Not Configured';
    statusTooltip = 'No Cloud GPU URL configured. Click "Cloud GPU" to connect Google Colab.';
  }

  return (
    <header className="app-header glass-panel">
      <div className="logo-group">
        <div className="logo-icon">
          <Music2 size={26} />
        </div>
        <div className="logo-text">
          <h1>
            <span className="gradient-text">Suroor AI</span>
            <span className="urdu-badge">سرور</span>
          </h1>
          <p>AI Urdu &amp; Pashto Song Generator</p>
        </div>
      </div>

      <div className="header-actions">
        <div 
          className="status-chip"
          title={statusTooltip}
          style={{ cursor: 'pointer' }}
          onClick={onOpenSettings}
        >
          <div className={`status-dot ${dotClass}`} />
          <span>{statusLabel}</span>
        </div>

        <button 
          className="btn-secondary" 
          onClick={onOpenSettings}
          title="Configure Cloud GPU (Google Colab / Kaggle)"
          id="btn-open-settings"
        >
          <Settings size={16} />
          <span>Cloud GPU</span>
        </button>
      </div>
    </header>
  );
};
