import React, { useState, useRef, useCallback } from 'react';
import { Sparkles, Plus, Trash2, ChevronDown, ChevronUp, FileText, RotateCcw } from 'lucide-react';
import type { Language, Genre, LyricsPreviewResponse } from '../types';

interface StanzasEditorProps {
  language: Language;
  genre: Genre;
  theme: string;
  value: string;
  dialect?: 'peshawar' | 'kandahari';
  onChange: (v: string) => void;
  onPreviewLyrics: (preview: LyricsPreviewResponse) => void;
}

type SectionTag = '[Verse 1]' | '[Chorus]' | '[Verse 2]' | '[Bridge]' | '[Outro]' | '[Pre-Chorus]';

const SECTION_TAGS: { tag: SectionTag; emoji: string; color: string }[] = [
  { tag: '[Verse 1]',     emoji: '1️⃣', color: '#818cf8' },
  { tag: '[Pre-Chorus]',  emoji: '🔺', color: '#a78bfa' },
  { tag: '[Chorus]',      emoji: '🔁', color: '#f59e0b' },
  { tag: '[Verse 2]',     emoji: '2️⃣', color: '#6ee7b7' },
  { tag: '[Bridge]',      emoji: '🌉', color: '#38bdf8' },
  { tag: '[Outro]',       emoji: '🏁', color: '#f87171' },
];

/** Parse text into color-coded section blocks for preview */
function parseSections(text: string): { tag: string | null; lines: string[]; color: string }[] {
  if (!text.trim()) return [];
  const blocks: { tag: string | null; lines: string[]; color: string }[] = [];
  let currentTag: string | null = null;
  let currentColor = 'var(--text-muted)';
  let currentLines: string[] = [];

  for (const rawLine of text.split('\n')) {
    const line = rawLine;
    const sectionMatch = SECTION_TAGS.find((s) => line.trim().startsWith(s.tag));
    if (sectionMatch) {
      if (currentLines.filter(Boolean).length > 0) {
        blocks.push({ tag: currentTag, lines: currentLines, color: currentColor });
      }
      currentTag = sectionMatch.tag;
      currentColor = sectionMatch.color;
      currentLines = [];
    } else {
      currentLines.push(line);
    }
  }
  if (currentLines.filter(Boolean).length > 0) {
    blocks.push({ tag: currentTag, lines: currentLines, color: currentColor });
  }
  return blocks;
}

export const StanzasEditor: React.FC<StanzasEditorProps> = ({
  language,
  genre,
  theme,
  value,
  dialect,
  onChange,
  onPreviewLyrics,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const lineCount = value.trim() ? value.split('\n').length : 0;
  const charCount = value.length;
  const wordCount = value.trim() ? value.trim().split(/\s+/).length : 0;
  const sections = parseSections(value);
  const hasContent = Boolean(value.trim());

  /** Insert a section tag at the cursor position */
  const insertTag = useCallback((tag: SectionTag) => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const before = value.slice(0, start);
    const after = value.slice(end);
    const needsNewline = before.length > 0 && !before.endsWith('\n');
    const insertion = (needsNewline ? '\n' : '') + tag + '\n';
    const newVal = before + insertion + after;
    onChange(newVal);
    // Restore cursor
    requestAnimationFrame(() => {
      ta.focus();
      const pos = start + insertion.length;
      ta.setSelectionRange(pos, pos);
    });
  }, [value, onChange]);

  /** Auto-structure raw text into verse/chorus */
  const autoStructure = () => {
    if (!value.trim()) return;
    const lines = value.split('\n').filter((l) => l.trim());
    // Skip if already has tags
    if (lines.some((l) => SECTION_TAGS.some((s) => l.trim().startsWith(s.tag)))) return;

    const n = lines.length;
    let structured = '';
    if (n <= 4) {
      structured = '[Verse 1]\n' + lines.join('\n');
    } else if (n <= 8) {
      const half = Math.ceil(n / 2);
      structured = '[Verse 1]\n' + lines.slice(0, half).join('\n') + '\n\n[Chorus]\n' + lines.slice(half).join('\n');
    } else {
      const v1 = lines.slice(0, 4).join('\n');
      const ch = lines.slice(4, 8).join('\n');
      const v2 = lines.slice(8, 12).join('\n');
      structured = '[Verse 1]\n' + v1 + '\n\n[Chorus]\n' + ch;
      if (v2) structured += '\n\n[Verse 2]\n' + v2;
      structured += '\n\n[Chorus]\n' + ch;
    }
    onChange(structured);
  };

  /** Clear all */
  const handleClear = () => {
    onChange('');
    setShowPreview(false);
  };

  /** Generate & preview via API */
  const handleGeneratePreview = async () => {
    setIsGenerating(true);
    try {
      const resp = await fetch('/api/lyrics/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          language,
          genre,
          theme,
          custom_stanzas: value.trim() || undefined,
          dialect: dialect || 'peshawar',
        }),
      });
      if (resp.ok) {
        const data: LyricsPreviewResponse = await resp.json();
        onPreviewLyrics(data);
        // Populate the editor if empty
        if (!value.trim()) {
          onChange(data.display_lyrics);
          setShowPreview(true);
        }
      } else {
        alert('Could not generate lyrics at this moment.');
      }
    } catch {
      alert('Error connecting to lyrics engine.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="stanzas-editor-wrap">
      {/* Collapsible Header */}
      <button
        type="button"
        className="stanzas-header-btn"
        onClick={() => setIsExpanded((v) => !v)}
        id="btn-toggle-stanzas"
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FileText size={15} color="var(--primary-light)" />
          <span style={{ fontWeight: 600, fontSize: '0.88rem' }}>Custom Lyrics / Stanzas</span>
          <span className="stanzas-optional-tag">Optional</span>
          {hasContent && (
            <span className="stanzas-count-tag">{sections.length} section{sections.length !== 1 ? 's' : ''}</span>
          )}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Generate AI Lyrics */}
          <span
            role="button"
            className="btn-secondary"
            onClick={(e) => { e.stopPropagation(); handleGeneratePreview(); }}
            style={{ fontSize: '0.75rem', padding: '4px 10px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
            id="btn-preview-lyrics"
          >
            <Sparkles size={12} color="#f59e0b" />
            {isGenerating ? 'Writing…' : 'AI Generate'}
          </span>
          {isExpanded ? <ChevronUp size={16} color="var(--text-dim)" /> : <ChevronDown size={16} color="var(--text-dim)" />}
        </span>
      </button>

      {isExpanded && (
        <div className="stanzas-body">
          {/* Section Tag Insertion Bar */}
          <div className="section-tag-bar">
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>Insert:</span>
            {SECTION_TAGS.map((s) => (
              <button
                key={s.tag}
                type="button"
                className="section-tag-btn"
                style={{ '--tag-color': s.color } as React.CSSProperties}
                onClick={() => insertTag(s.tag)}
                title={`Insert ${s.tag} section header`}
              >
                {s.emoji} {s.tag.replace(/[\[\]]/g, '')}
              </button>
            ))}
          </div>

          {/* Textarea */}
          <div style={{ position: 'relative' }}>
            <textarea
              ref={textareaRef}
              className={`form-textarea stanzas-textarea ${language === 'urdu' ? 'urdu-text' : language === 'pashto' ? 'pashto-text' : ''}`}
              placeholder={
                language === 'urdu'
                  ? 'اپنے اشعار یہاں لکھیں یا "AI Generate" پر کلک کریں...\n\n[Verse 1]\nپہلا شعر یہاں\n\n[Chorus]\nٹیک یہاں'
                  : language === 'pashto'
                  ? 'خپل شعر دلته ولیکئ یا "AI Generate" کلیک کړئ...\n\n[Verse 1]\nلومړی شعر دلته\n\n[Chorus]\nنغمه دلته'
                  : 'Write your stanzas here or click AI Generate...\n\n[Verse 1]\nFirst verse line\n\n[Chorus]\nYour chorus here'
              }
              value={value}
              onChange={(e) => { onChange(e.target.value); setShowPreview(false); }}
              id="custom-stanzas-input"
              style={{ minHeight: '180px', fontFamily: language === 'urdu' ? 'var(--font-urdu)' : language === 'pashto' ? 'var(--font-pashto)' : 'var(--font-sans)' }}
            />
          </div>

          {/* Toolbar Row: stats + actions */}
          <div className="stanzas-toolbar">
            <div className="stanzas-stats">
              {hasContent && (
                <>
                  <span>{lineCount} lines</span>
                  <span>·</span>
                  <span>{wordCount} words</span>
                  <span>·</span>
                  <span>{charCount} chars</span>
                </>
              )}
              {!hasContent && (
                <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>
                  AI will compose lyrics using your theme & genre if left empty
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              {hasContent && !sections.some((s) => s.tag) && (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={autoStructure}
                  style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                  id="btn-auto-structure"
                >
                  <Plus size={12} /> Auto-Structure
                </button>
              )}
              {hasContent && (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleClear}
                  style={{ fontSize: '0.75rem', padding: '4px 10px', color: 'var(--accent-rose)' }}
                  id="btn-clear-stanzas"
                >
                  <Trash2 size={12} /> Clear
                </button>
              )}
            </div>
          </div>

          {/* Section Preview */}
          {hasContent && sections.length > 0 && (
            <div className="sections-preview-wrap">
              <button
                type="button"
                className="sections-preview-toggle"
                onClick={() => setShowPreview((v) => !v)}
                id="btn-toggle-structure-preview"
              >
                <RotateCcw size={12} />
                {showPreview ? 'Hide structure' : 'Show structure'}
                {showPreview ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>

              {showPreview && (
                <div className="sections-preview">
                  {sections.map((block, idx) => (
                    <div key={idx} className="section-block">
                      {block.tag && (
                        <div className="section-block-tag" style={{ color: block.color, borderColor: `${block.color}44` }}>
                          {SECTION_TAGS.find((s) => s.tag === block.tag)?.emoji} {block.tag.replace(/[\[\]]/g, '')}
                        </div>
                      )}
                      <div
                        className="section-block-lines"
                        style={{
                          direction: (language === 'urdu' || language === 'pashto') ? 'rtl' : 'ltr',
                          fontFamily: language === 'urdu' ? 'var(--font-urdu)' : language === 'pashto' ? 'var(--font-pashto)' : 'var(--font-sans)',
                        }}
                      >
                        {block.lines.filter((l) => l.trim()).map((line, li) => (
                          <p key={li} style={{ margin: '2px 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                            {line}
                          </p>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Helpful tips */}
          <div className="stanzas-tips">
            <span>💡</span>
            <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>
              Use section tags to structure your song. Leave empty to let Gemini AI compose custom lyrics from your theme.
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
