/**
 * MangaZine global Zustand store.
 * Holds the entire ComicProject JSON state and exposes typed actions.
 * Uses the immer middleware so actions can mutate draft state directly.
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

import type {
  ComicProject,
  PanelSpec,
  RenderOutput,
} from '@/types/comic';

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

interface ComicState {
  /** The root project model; null until loadProject is called */
  project: ComicProject | null;

  /** ID of the currently selected page (for sidebar context) */
  selectedPageId: string | null;

  /** ID of the currently selected panel (opens PanelEditorSidebar) */
  selectedPanelId: string | null;

  /**
   * Set of panel IDs that have an active rerender request in-flight.
   * Used to show per-panel loading states without blocking the whole UI.
   */
  rerenderingPanelIds: Set<string>;
}

// ---------------------------------------------------------------------------
// Actions shape
// ---------------------------------------------------------------------------

interface ComicActions {
  /**
   * Load (or replace) the project from a raw JSON string or a parsed object.
   * Accepts both `string` (paste from disk) and `ComicProject` (API response).
   */
  loadProject: (json: string | ComicProject | null) => void;

  /**
   * Deep-merge `newData` into the panel identified by `panelId` on `pageId`.
   * Searches all episodes' pages so callers don't need to know the episode.
   */
  updatePanel: (
    pageId: string,
    panelId: string,
    newData: Partial<PanelSpec>,
  ) => void;

  /**
   * Non-destructive image update:
   * 1. Pushes the current `render_output` snapshot onto `revision_history`.
   * 2. Replaces `render_output.image_url` with the new URL and sets status
   *    to `draft_ready`.
   */
  updatePanelImage: (
    pageId: string,
    panelId: string,
    imageUrl: string,
    meta?: Pick<RenderOutput, 'model_used' | 'generation_params' | 'generated_at'>,
  ) => void;

  /** Open the editor sidebar for a specific panel */
  setSelectedPanel: (pageId: string, panelId: string) => void;

  /** Close the editor sidebar */
  clearSelectedPanel: () => void;

  /** Mark a panel render as in-flight */
  setRerenderingPanel: (panelId: string, isRendering: boolean) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Walk all episodes → pages looking for a page with the given ID.
 * Returns `[episodeIdx, pageIdx]` or `[-1, -1]` if not found.
 */
function findPageIndices(
  project: ComicProject,
  pageId: string,
): [number, number] {
  for (let ei = 0; ei < project.episodes.length; ei++) {
    const pi = project.episodes[ei].pages.findIndex((p) => p.page_id === pageId);
    if (pi !== -1) return [ei, pi];
  }
  return [-1, -1];
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useComicStore = create<ComicState & ComicActions>()(
  devtools(
    immer((set) => ({
      // ── Initial state ───────────────────────────────────────────────────
      project: null,
      selectedPageId: null,
      selectedPanelId: null,
      rerenderingPanelIds: new Set<string>(),

      // ── Actions ─────────────────────────────────────────────────────────

      loadProject: (json) => {
        set((state) => {
          state.project =
            json === null
              ? null
              : typeof json === 'string'
                ? (JSON.parse(json) as ComicProject)
                : json;
          state.selectedPageId = null;
          state.selectedPanelId = null;
        });
      },

      updatePanel: (pageId, panelId, newData) => {
        set((state) => {
          if (!state.project) return;
          const [ei, pi] = findPageIndices(state.project, pageId);
          if (ei === -1) return;
          const page = state.project.episodes[ei].pages[pi];
          const panelIdx = page.panels.findIndex((p) => p.panel_id === panelId);
          if (panelIdx === -1) return;
          Object.assign(page.panels[panelIdx], newData);
        });
      },

      updatePanelImage: (pageId, panelId, imageUrl, meta) => {
        set((state) => {
          if (!state.project) return;
          const [ei, pi] = findPageIndices(state.project, pageId);
          if (ei === -1) return;
          const page = state.project.episodes[ei].pages[pi];
          const panel = page.panels.find((p) => p.panel_id === panelId);
          if (!panel) return;

          // Snapshot current render_output into revision history before overwriting
          if (!panel.revision_history) panel.revision_history = [];
          panel.revision_history.push({ ...panel.render_output });

          panel.render_output = {
            ...panel.render_output,
            status: 'draft_ready',
            image_url: imageUrl,
            model_used: meta?.model_used ?? panel.render_output.model_used,
            generation_params: meta?.generation_params ?? panel.render_output.generation_params,
            generated_at: meta?.generated_at ?? new Date().toISOString(),
          };
        });
      },

      setSelectedPanel: (pageId, panelId) => {
        set((state) => {
          state.selectedPageId = pageId;
          state.selectedPanelId = panelId;
        });
      },

      clearSelectedPanel: () => {
        set((state) => {
          state.selectedPageId = null;
          state.selectedPanelId = null;
        });
      },

      setRerenderingPanel: (panelId, isRendering) => {
        set((state) => {
          if (isRendering) {
            state.rerenderingPanelIds.add(panelId);
          } else {
            state.rerenderingPanelIds.delete(panelId);
          }
        });
      },
    })),
    { name: 'ComicStore' },
  ),
);

// ---------------------------------------------------------------------------
// Convenience selectors  (use these in components to minimise re-renders)
// ---------------------------------------------------------------------------

/** Returns the selected panel object, or null */
export function useSelectedPanel() {
  return useComicStore((state) => {
    if (!state.project || !state.selectedPageId || !state.selectedPanelId) {
      return null;
    }
    for (const episode of state.project.episodes) {
      const page = episode.pages.find((p) => p.page_id === state.selectedPageId);
      if (!page) continue;
      const panel = page.panels.find((p) => p.panel_id === state.selectedPanelId);
      if (panel) return panel;
    }
    return null;
  });
}

/** Returns true when `panelId` has a rerender in-flight */
export function usePanelIsRerendering(panelId: string) {
  return useComicStore((state) => state.rerenderingPanelIds.has(panelId));
}
