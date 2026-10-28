export type Language = 'urdu' | 'pashto';

export type Genre =
  | 'ghazal'
  | 'sufi'
  | 'pop'
  | 'folk_attan'
  | 'rubab_ballad'
  | 'qawwali'
  | 'lofi'
  | 'acoustic';

export interface VariantInfo {
  variant_number: number;
  title: string;
  seed: number;
  duration_seconds: number;
  audio_url: string;
  vocal_url?: string;
  instrumental_url?: string;
  waveform_data?: number[];
  engine?: 'ace-step' | 'demo-tone';
  voice_conversion?: 'seed-vc' | 'rvc' | 'so-vits-svc' | 'none';
  is_demo?: boolean;
}

export interface JobState {
  job_id: string;
  language: Language;
  theme: string;
  genre: Genre;
  display_lyrics: string;
  sung_lyrics?: string;
  lyrics_source?: 'user' | 'gemini' | 'template' | string;
  number_of_variants: number;
  current_step: number;
  step_name: string;
  step_progress: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message: string;
  voice_sample_path?: string;
  cleaned_voice_sample_path?: string;
  variants: VariantInfo[];
  selected_variant?: number;
  error?: string;
  created_at: number;
  updated_at: number;
}

export interface LyricsPreviewResponse {
  language: Language;
  display_lyrics: string;
  sung_lyrics: string;
  structure: {
    has_verse_1: boolean;
    has_chorus: boolean;
    has_verse_2: boolean;
    total_lines: number;
  };
  source: string;
  dialect?: 'peshawar' | 'kandahari';
}

export interface AppConfig {
  cloud_gpu_url: string;
  has_gemini_key: boolean;
  ffmpeg_available?: boolean;
  cloud_gpu_status?: 'not_configured' | 'unreachable' | 'connected';
  allow_demo_fallback?: boolean;
}
