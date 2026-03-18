'use client';

import Image from 'next/image';
import {
  Camera,
  ChevronDown,
  ChevronUp,
  History,
  Lock,
  RefreshCw,
  Unlock,
  X,
} from 'lucide-react';
import React, { useState } from 'react';

import {
  useComicStore,
  useSelectedPanel,
  usePanelIsRerendering,
} from '@/store/comicStore';
import type {
  CharacterBible,
  LockConstraints,
  RenderOutput,
  RerenderRequest,
  RerenderResponse,
} from '@/types/comic';

// ---------------------------------------------------------------------------
// Small UI primitives
// ---------------------------------------------------------------------------

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500 mb-2">
      {children}
    </h3>
  );
}

function Badge({ children, variant = 'default' }: { children: React.ReactNode; variant?: 'default' | 'violet' | 'yellow' }) {
  const cls = {
    default: 'bg-zinc-800 text-zinc-300 border-zinc-700',
    violet:  'bg-violet-950 text-violet-300 border-violet-800',
    yellow:  'bg-yellow-950 text-yellow-300 border-yellow-800',
  }[variant];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono border ${cls}`}>
      {children}
    </span>
  );
}

// ---------------------------------------------------------------------------
// LockToggle
// ---------------------------------------------------------------------------

interface LockToggleProps {
  label: string;
  locked: boolean;
  onToggle: () => void;
}

function LockToggle({ label, locked, onToggle }: LockToggleProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={[
        'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium',
        'border transition-all duration-100 select-none',
        locked
          ? 'bg-violet-900/60 text-violet-200 border-violet-600 hover:bg-violet-900'
          : 'bg-zinc-800 text-zinc-400 border-zinc-700 hover:border-zinc-500 hover:text-zinc-300',
      ].join(' ')}
    >
      {locked ? <Lock size={11} strokeWidth={2.5} /> : <Unlock size={11} strokeWidth={2} />}
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// RevisionHistory
// ---------------------------------------------------------------------------

interface RevisionHistoryProps {
  history: RenderOutput[];
}

function RevisionHistory({ history }: RevisionHistoryProps) {
  const [open, setOpen] = useState(false);

  if (!history || history.length === 0) {
    return (
      <div className="text-zinc-600 text-xs italic">No revision history yet.</div>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors w-full"
      >
        <History size={12} />
        <span>{history.length} revision{history.length !== 1 ? 's' : ''}</span>
        {open ? <ChevronUp size={12} className="ml-auto" /> : <ChevronDown size={12} className="ml-auto" />}
      </button>

      {open && (
        <div className="mt-2 flex gap-2 overflow-x-auto pb-1 scrollbar-thin scrollbar-track-zinc-900 scrollbar-thumb-zinc-700">
          {[...history].reverse().map((rev, i) => (
            <div
              key={i}
              className="flex-none w-20 h-28 relative rounded overflow-hidden border border-zinc-700 bg-zinc-800 group"
              title={rev.generated_at ?? 'unknown time'}
            >
              {rev.image_url ? (
                <Image
                  src={rev.image_url}
                  alt={`Revision ${history.length - i}`}
                  fill
                  className="object-cover opacity-70 group-hover:opacity-100 transition-opacity"
                  sizes="80px"
                  unoptimized
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-zinc-600 text-[9px]">
                  No image
                </div>
              )}
              <span className="absolute bottom-0 left-0 right-0 text-center text-[8px] font-mono text-zinc-400 bg-black/60 py-0.5">
                v{history.length - i}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PanelEditorSidebar
// ---------------------------------------------------------------------------

interface PanelEditorSidebarProps {
  /** Passed from the parent page so the sidebar can do character lookups */
  characterBible?: CharacterBible;
}

/**
 * Non-destructive panel editor sidebar.
 *
 * Opens when a panel is selected in ``ComicCanvas``.
 * Reads ``selectedPanelId`` / ``selectedPageId`` from the Zustand store and
 * writes back via ``updatePanelImage`` (which snapshots the old render into
 * ``revision_history`` before overwriting).
 *
 * The "Rerender Panel" button POSTs to ``/api/rerender-panel`` with the full
 * ``PanelSpec`` and the current lock constraints.
 */
export function PanelEditorSidebar({ characterBible }: PanelEditorSidebarProps) {
  const panel         = useSelectedPanel();
  const selectedPageId = useComicStore((s) => s.selectedPageId);
  const clearSelectedPanel  = useComicStore((s) => s.clearSelectedPanel);
  const updatePanelImage    = useComicStore((s) => s.updatePanelImage);
  const setRerenderingPanel = useComicStore((s) => s.setRerenderingPanel);
  const isRerendering = usePanelIsRerendering(panel?.panel_id ?? '');

  // Lock state
  const [locks, setLocks] = useState<LockConstraints>({
    lock_characters:  true,
    lock_style:       true,
    lock_composition: false,
    lock_dialogue:    false,
  });

  // Prompt override (starts with existing prompt_plan; user can edit before rerender)
  const [promptOverride, setPromptOverride] = useState<string>('');

  // Error state
  const [rerenderError, setRerenderError] = useState<string | null>(null);

  // Sync prompt textarea when panel changes
  React.useEffect(() => {
    setPromptOverride(panel?.prompt_plan ?? '');
    setRerenderError(null);
  }, [panel?.panel_id]);  // eslint-disable-line react-hooks/exhaustive-deps

  // ── Not open ──────────────────────────────────────────────────────────────
  if (!panel || !selectedPageId) return null;

  // ── Helpers ───────────────────────────────────────────────────────────────

  function toggleLock(key: keyof LockConstraints) {
    setLocks((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function lookupCharacterName(id: string): string {
    if (!characterBible) return id.slice(0, 8) + '…';
    const char = characterBible.characters.find((c) => c.character_id === id);
    return char?.name ?? id.slice(0, 8) + '…';
  }

  async function handleRerender() {
    if (!panel || !selectedPageId) return;

    setRerenderError(null);
    setRerenderingPanel(panel.panel_id, true);

    const panelToSend = promptOverride.trim()
      ? { ...panel, prompt_plan: promptOverride.trim() }
      : panel;

    const body: RerenderRequest = {
      panel: panelToSend,
      page_id: selectedPageId,
      lock_constraints: locks,
    };

    try {
      const res = await fetch('/api/rerender-panel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const msg = await res.text().catch(() => res.statusText);
        throw new Error(`${res.status} ${msg}`);
      }

      const data: RerenderResponse = await res.json();

      updatePanelImage(selectedPageId, panel.panel_id, data.image_url, {
        model_used: data.model_used,
        generation_params: data.generation_params,
      });
    } catch (err) {
      setRerenderError((err as Error).message);
    } finally {
      setRerenderingPanel(panel.panel_id, false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const hasImage =
    !!panel.render_output.image_url &&
    (panel.render_output.status === 'draft_ready' ||
      panel.render_output.status === 'approved');

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
        onClick={clearSelectedPanel}
        aria-hidden
      />

      {/* Sidebar panel */}
      <aside
        aria-label="Panel editor"
        className={[
          'fixed right-0 top-0 h-full z-50',
          'w-96 bg-zinc-900 border-l border-zinc-800',
          'flex flex-col shadow-2xl',
          'translate-x-0 transition-transform duration-200',
        ].join(' ')}
      >
        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 flex-none">
          <div className="flex items-center gap-2">
            <Camera size={14} className="text-violet-400" />
            <span className="text-sm font-semibold text-zinc-100">
              Panel {panel.panel_index}
            </span>
            <Badge variant="violet">{panel.shot_type.replace(/_/g, ' ')}</Badge>
            <Badge>{panel.camera_angle.replace(/_/g, ' ')}</Badge>
          </div>
          <button
            type="button"
            onClick={clearSelectedPanel}
            className="text-zinc-500 hover:text-zinc-200 transition-colors p-1 rounded hover:bg-zinc-800"
            aria-label="Close panel editor"
          >
            <X size={16} />
          </button>
        </div>

        {/* ── Scrollable body ────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5 scrollbar-thin scrollbar-track-zinc-900 scrollbar-thumb-zinc-700">

          {/* Current image preview */}
          {hasImage && (
            <div className="relative w-full aspect-[2/3] rounded overflow-hidden border border-zinc-800 bg-zinc-950">
              <Image
                src={panel.render_output.image_url!}
                alt={`Panel ${panel.panel_index} preview`}
                fill
                className="object-cover"
                sizes="384px"
                unoptimized
              />
              {panel.render_output.model_used && (
                <span className="absolute bottom-1 right-1 text-[8px] font-mono bg-black/70 text-zinc-400 px-1 rounded">
                  {panel.render_output.model_used.split('-').slice(-1)[0]}
                </span>
              )}
            </div>
          )}

          {/* ── Scene details ──────────────────────────────────────────── */}
          <div>
            <SectionHeading>Scene</SectionHeading>
            {panel.setting_description && (
              <p className="text-xs text-zinc-400 leading-relaxed mb-1">
                <span className="text-zinc-600">Setting — </span>
                {panel.setting_description}
              </p>
            )}
            {panel.action_description && (
              <p className="text-xs text-zinc-400 leading-relaxed">
                <span className="text-zinc-600">Action — </span>
                {panel.action_description}
              </p>
            )}
          </div>

          {/* ── Characters ─────────────────────────────────────────────── */}
          {panel.characters.length > 0 && (
            <div>
              <SectionHeading>Characters</SectionHeading>
              <div className="flex flex-wrap gap-1.5">
                {panel.characters.map((id) => (
                  <Badge key={id} variant="violet">
                    {lookupCharacterName(id)}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* ── Dialogue ───────────────────────────────────────────────── */}
          {panel.dialogue.length > 0 && (
            <div>
              <SectionHeading>Dialogue</SectionHeading>
              <div className="space-y-1.5">
                {[...panel.dialogue]
                  .sort((a, b) => a.reading_order - b.reading_order)
                  .map((line, i) => (
                    <div
                      key={i}
                      className="flex gap-2 items-start bg-zinc-800/50 rounded px-2.5 py-1.5 border border-zinc-800"
                    >
                      <span className="text-[9px] font-mono uppercase text-zinc-600 mt-0.5 flex-none">
                        {line.balloon_type}
                      </span>
                      <p className="text-xs text-zinc-300 leading-snug">
                        {line.character_id && (
                          <span className="text-violet-400 font-medium mr-1">
                            {lookupCharacterName(line.character_id)}:
                          </span>
                        )}
                        {line.text}
                      </p>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* ── Prompt plan (editable override) ────────────────────────── */}
          <div>
            <SectionHeading>Prompt Plan</SectionHeading>
            <textarea
              value={promptOverride}
              onChange={(e) => setPromptOverride(e.target.value)}
              rows={5}
              className={[
                'w-full rounded bg-zinc-800 border border-zinc-700',
                'text-xs text-zinc-300 placeholder-zinc-600',
                'px-2.5 py-2 resize-none leading-relaxed',
                'focus:outline-none focus:border-violet-600 focus:ring-1 focus:ring-violet-600/50',
                'transition-colors',
              ].join(' ')}
              placeholder="Describe the panel for the image model…"
            />
            {promptOverride !== panel.prompt_plan && (
              <p className="mt-1 text-[10px] text-yellow-500">
                ⚡ Prompt override active — original plan preserved in PanelSpec.
              </p>
            )}
          </div>

          {/* ── Lock constraints ───────────────────────────────────────── */}
          <div>
            <SectionHeading>Lock Constraints</SectionHeading>
            <p className="text-[10px] text-zinc-600 mb-2 leading-relaxed">
              Locked elements are passed as fixed constraints to the rerender API,
              keeping them unchanged while other elements can vary.
            </p>
            <div className="flex flex-wrap gap-2">
              <LockToggle
                label="Characters"
                locked={locks.lock_characters}
                onToggle={() => toggleLock('lock_characters')}
              />
              <LockToggle
                label="Style"
                locked={locks.lock_style}
                onToggle={() => toggleLock('lock_style')}
              />
              <LockToggle
                label="Composition"
                locked={locks.lock_composition}
                onToggle={() => toggleLock('lock_composition')}
              />
              <LockToggle
                label="Dialogue"
                locked={locks.lock_dialogue}
                onToggle={() => toggleLock('lock_dialogue')}
              />
            </div>
          </div>

          {/* ── Error message ──────────────────────────────────────────── */}
          {rerenderError && (
            <div className="rounded border border-red-800 bg-red-950/50 px-3 py-2">
              <p className="text-xs text-red-300 leading-snug">
                <span className="font-semibold">Rerender failed: </span>
                {rerenderError}
              </p>
            </div>
          )}

          {/* ── Revision history ───────────────────────────────────────── */}
          <div>
            <SectionHeading>Revision History</SectionHeading>
            <RevisionHistory history={panel.revision_history ?? []} />
          </div>

          {/* Bottom padding so the sticky footer doesn't overlap content */}
          <div className="h-4" />
        </div>

        {/* ── Sticky rerender button ─────────────────────────────────────── */}
        <div className="flex-none border-t border-zinc-800 px-4 py-3 bg-zinc-900">
          <button
            type="button"
            onClick={handleRerender}
            disabled={isRerendering}
            className={[
              'w-full flex items-center justify-center gap-2',
              'rounded-lg px-4 py-2.5 text-sm font-semibold',
              'transition-all duration-150',
              isRerendering
                ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                : 'bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-900/40 active:scale-[0.98]',
            ].join(' ')}
          >
            <RefreshCw
              size={15}
              strokeWidth={2.5}
              className={isRerendering ? 'animate-spin' : ''}
            />
            {isRerendering ? 'Generating…' : 'Rerender Panel'}
          </button>
          <p className="mt-1.5 text-center text-[10px] text-zinc-600">
            Current image will be saved to revision history.
          </p>
        </div>
      </aside>
    </>
  );
}
