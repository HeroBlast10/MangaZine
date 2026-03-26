'use client';

import React from 'react';

import { getLayoutConfig } from '@/lib/layoutConfigs';
import { resolveRenderImageUrl } from '@/lib/projectImageUrl';
import { useComicStore } from '@/store/comicStore';
import type { GridCell, PageLayout, PageSpec, PanelSpec } from '@/types/comic';

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

function cellToGridStyle(cell: GridCell, layout: PageLayout): React.CSSProperties {
  const { columns, rows } = layout;
  const colStart = Math.round(cell.column_start * columns) + 1;
  const colEnd = Math.round(cell.column_end * columns) + 1;
  const rowStart = Math.round(cell.row_start * rows) + 1;
  const rowEnd = Math.round(cell.row_end * rows) + 1;

  return {
    gridColumn: `${colStart} / ${colEnd}`,
    gridRow: `${rowStart} / ${rowEnd}`,
  };
}

function hasRenderedImage(panel: PanelSpec): boolean {
  return Boolean(
    resolveRenderImageUrl(panel.render_output) &&
      (panel.render_output.status === 'draft_ready' ||
        panel.render_output.status === 'approved'),
  );
}

function PanelSkeleton({ panel }: { panel: PanelSpec }) {
  return (
    <div className="relative flex h-full w-full flex-col items-center justify-center overflow-hidden bg-zinc-800 transition-colors group-hover:bg-zinc-700">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            'repeating-linear-gradient(135deg, #fff 0px, #fff 1px, transparent 1px, transparent 12px)',
        }}
      />
      <div className="absolute inset-0 animate-pulse bg-gradient-to-b from-zinc-800 via-zinc-700 to-zinc-800 opacity-50" />

      <div className="relative z-10 flex flex-col items-center gap-1 px-3 text-center">
        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
          {panel.shot_type.replace(/_/g, ' ')}
        </span>
        <span className="text-[8px] font-mono uppercase tracking-widest text-zinc-500/70">
          {panel.camera_angle.replace(/_/g, ' ')}
        </span>
        {(panel.prompt_plan || panel.action_description) && (
          <p className="mt-1 line-clamp-4 max-w-[90%] text-[9px] leading-snug text-zinc-600">
            {panel.prompt_plan || panel.action_description}
          </p>
        )}
      </div>
    </div>
  );
}

function GeneratingOverlay() {
  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 bg-black/70">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-400 border-t-transparent" />
      <span className="text-[10px] font-mono uppercase tracking-wider text-violet-300">
        重新生成中
      </span>
    </div>
  );
}

interface PanelCellProps {
  panel: PanelSpec;
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
  const imageUrl = resolveRenderImageUrl(panel.render_output);
  const rendered = hasRenderedImage(panel);

  return (
    <div
      style={style}
      onClick={onClick}
      role="button"
      className={[
        'group relative cursor-pointer overflow-hidden transition-all duration-150',
        'outline outline-1',
        isSelected
          ? 'outline-2 outline-violet-500 shadow-[0_0_0_2px_rgba(139,92,246,0.5)]'
          : 'outline-zinc-700 hover:outline-zinc-400',
      ].join(' ')}
    >
      {rendered && imageUrl ? (
        <img
          src={imageUrl}
          alt={`Panel ${panel.panel_index} - ${panel.shot_type}`}
          className="h-full w-full object-cover"
          loading="lazy"
          decoding="async"
        />
      ) : (
        <PanelSkeleton panel={panel} />
      )}

      {isRerendering && <GeneratingOverlay />}

      {isSelected && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-violet-500/10"
        />
      )}

      <span className="absolute left-1 top-1 z-10 rounded bg-black/60 px-1 text-[9px] leading-4 text-zinc-300">
        {panel.panel_index}
      </span>

      <span className="absolute right-1 top-1 z-10 rounded bg-violet-950/80 px-1 text-[9px] uppercase leading-4 text-violet-300">
        {SHOT_LABELS[panel.shot_type] ?? panel.shot_type}
      </span>

      {!rendered && !isRerendering && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-end bg-zinc-900/85 p-2 opacity-0 transition-opacity group-hover:opacity-100">
          <p className="line-clamp-3 text-[9px] leading-snug text-zinc-300">
            {panel.action_description || panel.prompt_plan}
          </p>
        </div>
      )}
    </div>
  );
}

export interface ComicCanvasProps {
  page: PageSpec;
  className?: string;
}

export function ComicCanvas({ page, className = '' }: ComicCanvasProps) {
  const selectedPanelId = useComicStore((state) => state.selectedPanelId);
  const rerenderingPanelIds = useComicStore((state) => state.rerenderingPanelIds);
  const setSelectedPanel = useComicStore((state) => state.setSelectedPanel);
  const clearSelectedPanel = useComicStore((state) => state.clearSelectedPanel);

  const { layout, panels, page_id, layout_template } = page;
  const hasExplicitCells = layout.cells.length === panels.length;
  const layoutConfig = layout_template ? getLayoutConfig(layout_template) : null;

  const gridStyle: React.CSSProperties = layoutConfig
    ? {
        display: 'grid',
        gridTemplateColumns: layoutConfig.gridTemplateColumns,
        gridTemplateRows: layoutConfig.gridTemplateRows,
        gridTemplateAreas: layoutConfig.gridTemplateAreas,
        gap: `${layout.gutter_px || 8}px`,
        padding: layout.bleed ? 0 : `${layout.gutter_px || 8}px`,
      }
    : {
        display: 'grid',
        gridTemplateColumns: `repeat(${layout.columns}, 1fr)`,
        gridTemplateRows: `repeat(${layout.rows}, 1fr)`,
        gap: `${layout.gutter_px}px`,
        padding: layout.bleed ? 0 : `${layout.gutter_px}px`,
      };

  return (
    <div
      className={`relative aspect-[2/3] w-full bg-zinc-950 ${className}`}
      style={gridStyle}
    >
      {panels.map((panel, index) => {
        let cellStyle: React.CSSProperties | undefined;

        if (layoutConfig && layoutConfig.panelAreas[index]) {
          cellStyle = { gridArea: layoutConfig.panelAreas[index] };
        } else if (hasExplicitCells) {
          cellStyle = cellToGridStyle(layout.cells[index], layout);
        }

        const isSelected = selectedPanelId === panel.panel_id;
        const isRerendering = rerenderingPanelIds.has(panel.panel_id);

        return (
          <PanelCell
            key={panel.panel_id}
            panel={panel}
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
