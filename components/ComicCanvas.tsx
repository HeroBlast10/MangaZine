'use client';

import Image from 'next/image';
import React from 'react';

import { useComicStore } from '@/store/comicStore';
import type { GridCell, PageLayout, PageSpec, PanelSpec } from '@/types/comic';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SHOT_LABELS: Record<string, string> = {
  extreme_close_up: 'ECU',
  close_up: 'CU',
  medium_close_up: 'MCU',
  medium_shot: 'MS',
  medium_wide: 'MW',
  wide_shot: 'WS',
  extreme_wide: 'EWS',
  over_the_shoulder: 'OTS',
  pov: 'POV',
  insert: 'INS',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Convert a normalised [0, 1] GridCell to CSS grid-column / grid-row span strings.
 * Grid line numbers start at 1; total lines = dimension + 1.
 */
function cellToGridStyle(
  cell: GridCell,
  layout: PageLayout,
): React.CSSProperties {
  const { columns, rows } = layout;
  const colStart = Math.round(cell.column_start * columns) + 1;
  const colEnd   = Math.round(cell.column_end   * columns) + 1;
  const rowStart = Math.round(cell.row_start    * rows)    + 1;
  const rowEnd   = Math.round(cell.row_end      * rows)    + 1;
  return {
    gridColumn: `${colStart} / ${colEnd}`,
    gridRow:    `${rowStart} / ${rowEnd}`,
  };
}

function hasRenderedImage(panel: PanelSpec): boolean {
  return (
    !!panel.render_output.image_url &&
    (panel.render_output.status === 'draft_ready' ||
      panel.render_output.status === 'approved')
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PanelSkeleton({ panel }: { panel: PanelSpec }) {
  return (
    <div className="relative w-full h-full flex flex-col items-center justify-center bg-zinc-800 overflow-hidden group-hover:bg-zinc-750 transition-colors">
      {/* Manga speed-line texture */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage:
            'repeating-linear-gradient(135deg, #fff 0px, #fff 1px, transparent 1px, transparent 12px)',
        }}
      />
      {/* Pulse shimmer */}
      <div className="absolute inset-0 animate-pulse bg-gradient-to-b from-zinc-800 via-zinc-750 to-zinc-800 opacity-50" />

      <div className="relative z-10 flex flex-col items-center gap-1 px-3 text-center">
        <span className="text-zinc-500 text-[10px] font-mono uppercase tracking-widest">
          {panel.shot_type.replace(/_/g, ' ')}
        </span>
        <span className="text-zinc-500 text-[8px] font-mono uppercase tracking-widest opacity-60">
          {panel.camera_angle.replace(/_/g, ' ')}
        </span>
        {(panel.prompt_plan || panel.action_description) && (
          <p className="mt-1 text-zinc-600 text-[9px] leading-snug line-clamp-4 max-w-[90%]">
            {panel.prompt_plan || panel.action_description}
          </p>
        )}
      </div>
    </div>
  );
}

function GeneratingOverlay() {
  return (
    <div className="absolute inset-0 z-20 bg-black/70 flex flex-col items-center justify-center gap-2">
      <div className="w-6 h-6 rounded-full border-2 border-violet-400 border-t-transparent animate-spin" />
      <span className="text-violet-300 text-[10px] font-mono uppercase tracking-wider">
        Generating…
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PanelCell
// ---------------------------------------------------------------------------

interface PanelCellProps {
  panel: PanelSpec;
  pageId: string;
  style?: React.CSSProperties;
  isSelected: boolean;
  isRerendering: boolean;
  onClick: () => void;
}

function PanelCell({
  panel,
  style,
  isSelected,
  isRerendering,
  onClick,
}: PanelCellProps) {
  const rendered = hasRenderedImage(panel);

  return (
    <div
      style={style}
      onClick={onClick}
      role="button"
      aria-selected={isSelected}
      className={[
        'group relative overflow-hidden cursor-pointer transition-all duration-150',
        'outline outline-1',
        isSelected
          ? 'outline-2 outline-violet-500 shadow-[0_0_0_2px_rgba(139,92,246,0.5)]'
          : 'outline-zinc-700 hover:outline-zinc-400',
      ].join(' ')}
    >
      {/* Main content: image or skeleton */}
      {rendered ? (
        <Image
          src={panel.render_output.image_url!}
          alt={`Panel ${panel.panel_index} — ${panel.shot_type}`}
          fill
          className="object-cover"
          sizes="(max-width: 768px) 100vw, 50vw"
          unoptimized
        />
      ) : (
        <PanelSkeleton panel={panel} />
      )}

      {/* Generating overlay */}
      {isRerendering && <GeneratingOverlay />}

      {/* Selected tint */}
      {isSelected && (
        <div
          aria-hidden
          className="absolute inset-0 bg-violet-500/10 pointer-events-none"
        />
      )}

      {/* Top-left: panel index */}
      <span className="absolute top-1 left-1 z-10 text-[9px] font-mono bg-black/60 text-zinc-300 px-1 rounded leading-4">
        {panel.panel_index}
      </span>

      {/* Top-right: shot type badge */}
      <span className="absolute top-1 right-1 z-10 text-[9px] font-mono bg-violet-950/80 text-violet-300 px-1 rounded leading-4 uppercase">
        {SHOT_LABELS[panel.shot_type] ?? panel.shot_type}
      </span>

      {/* Hover caption (non-rendered panels only) */}
      {!rendered && !isRerendering && (
        <div className="absolute inset-0 z-10 opacity-0 group-hover:opacity-100 transition-opacity bg-zinc-900/85 flex items-end p-2 pointer-events-none">
          <p className="text-[9px] text-zinc-300 line-clamp-3 leading-snug">
            {panel.action_description || panel.prompt_plan}
          </p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ComicCanvas
// ---------------------------------------------------------------------------

export interface ComicCanvasProps {
  page: PageSpec;
  className?: string;
}

/**
 * Renders a single ``PageSpec`` as a CSS Grid of panel cells.
 *
 * Grid geometry is derived directly from ``page.layout``:
 * - ``layout.columns`` / ``layout.rows``  → ``grid-template-*``
 * - ``layout.cells[i]``  (normalised 0–1) → explicit ``grid-column``/``grid-row``
 *   for each panel when the cells array length matches the panels array length.
 * - Falls back to CSS auto-placement when cells are absent.
 *
 * Clicking a panel calls ``setSelectedPanel`` on the Zustand store, which
 * triggers the ``PanelEditorSidebar`` to open.
 */
export function ComicCanvas({ page, className = '' }: ComicCanvasProps) {
  const selectedPanelId    = useComicStore((s) => s.selectedPanelId);
  const rerenderingPanelIds = useComicStore((s) => s.rerenderingPanelIds);
  const setSelectedPanel   = useComicStore((s) => s.setSelectedPanel);
  const clearSelectedPanel = useComicStore((s) => s.clearSelectedPanel);

  const { layout, panels, page_id } = page;
  const hasExplicitCells = layout.cells.length === panels.length;

  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: `repeat(${layout.columns}, 1fr)`,
    gridTemplateRows: `repeat(${layout.rows}, 1fr)`,
    gap: `${layout.gutter_px}px`,
    padding: layout.bleed ? 0 : `${layout.gutter_px}px`,
  };

  return (
    <div
      className={`relative bg-zinc-950 w-full aspect-[2/3] ${className}`}
      style={gridStyle}
    >
      {panels.map((panel, idx) => {
        const cellStyle = hasExplicitCells
          ? cellToGridStyle(layout.cells[idx], layout)
          : undefined;

        const isSelected    = selectedPanelId === panel.panel_id;
        const isRerendering = rerenderingPanelIds.has(panel.panel_id);

        return (
          <PanelCell
            key={panel.panel_id}
            panel={panel}
            pageId={page_id}
            style={cellStyle}
            isSelected={isSelected}
            isRerendering={isRerendering}
            onClick={() =>
              isSelected
                ? clearSelectedPanel()
                : setSelectedPanel(page_id, panel.panel_id)
            }
          />
        );
      })}
    </div>
  );
}
