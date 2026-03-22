'use client';

import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Grid, Layers } from 'lucide-react';

import { ComicCanvas } from './ComicCanvas';
import type { PageSpec, EpisodeOutline } from '@/types/comic';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MultiPageViewerProps {
  episode: EpisodeOutline;
  className?: string;
}

type ViewMode = 'single' | 'grid' | 'spread';

// ---------------------------------------------------------------------------
// MultiPageViewer
// ---------------------------------------------------------------------------

/**
 * Multi-page viewer component for displaying manga episodes.
 * Supports single page view, grid view, and spread (two-page) view.
 */
export function MultiPageViewer({ episode, className = '' }: MultiPageViewerProps) {
  const [currentPage, setCurrentPage] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>('single');

  const pages = episode.pages;
  const totalPages = pages.length;

  if (totalPages === 0) {
    return (
      <div className={`flex items-center justify-center h-64 bg-zinc-900 rounded-lg ${className}`}>
        <p className="text-zinc-500">No pages available</p>
      </div>
    );
  }

  const goToPrevPage = () => {
    setCurrentPage((prev) => Math.max(0, prev - 1));
  };

  const goToNextPage = () => {
    setCurrentPage((prev) => Math.min(totalPages - 1, prev + 1));
  };

  const goToPage = (index: number) => {
    setCurrentPage(Math.max(0, Math.min(totalPages - 1, index)));
  };

  return (
    <div className={`flex flex-col gap-4 ${className}`}>
      {/* Header with episode info and controls */}
      <div className="flex items-center justify-between px-4 py-2 bg-zinc-900 rounded-lg">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-bold text-white">
            Episode {episode.episode_number}: {episode.title}
          </h2>
          <span className="text-sm text-zinc-400">
            {totalPages} page{totalPages !== 1 ? 's' : ''}
          </span>
        </div>

        {/* View mode toggle */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode('single')}
            className={`p-2 rounded ${viewMode === 'single' ? 'bg-violet-600' : 'bg-zinc-800 hover:bg-zinc-700'}`}
            title="Single page view"
          >
            <Layers className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 rounded ${viewMode === 'grid' ? 'bg-violet-600' : 'bg-zinc-800 hover:bg-zinc-700'}`}
            title="Grid view"
          >
            <Grid className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main content area */}
      {viewMode === 'single' && (
        <div className="flex items-center gap-4">
          {/* Previous button */}
          <button
            onClick={goToPrevPage}
            disabled={currentPage === 0}
            className="p-3 rounded-full bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-6 h-6" />
          </button>

          {/* Current page */}
          <div className="flex-1 flex flex-col items-center gap-2">
            <ComicCanvas page={pages[currentPage]} className="max-w-lg mx-auto shadow-2xl" />
            <span className="text-sm text-zinc-400">
              Page {currentPage + 1} of {totalPages}
            </span>
          </div>

          {/* Next button */}
          <button
            onClick={goToNextPage}
            disabled={currentPage === totalPages - 1}
            className="p-3 rounded-full bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="w-6 h-6" />
          </button>
        </div>
      )}

      {viewMode === 'grid' && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 p-4">
          {pages.map((page, index) => (
            <div
              key={page.page_id}
              onClick={() => {
                setCurrentPage(index);
                setViewMode('single');
              }}
              className={`cursor-pointer transition-all hover:scale-105 ${
                index === currentPage ? 'ring-2 ring-violet-500' : ''
              }`}
            >
              <ComicCanvas page={page} className="shadow-lg" />
              <p className="text-center text-xs text-zinc-400 mt-1">
                Page {index + 1}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Page thumbnails (single view mode) */}
      {viewMode === 'single' && totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 overflow-x-auto py-2 px-4">
          {pages.map((page, index) => (
            <button
              key={page.page_id}
              onClick={() => goToPage(index)}
              className={`flex-shrink-0 w-12 h-16 rounded overflow-hidden transition-all ${
                index === currentPage
                  ? 'ring-2 ring-violet-500 scale-110'
                  : 'opacity-60 hover:opacity-100'
              }`}
            >
              <div className="w-full h-full bg-zinc-800 flex items-center justify-center text-xs text-zinc-400">
                {index + 1}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Keyboard navigation hint */}
      <p className="text-center text-xs text-zinc-600">
        Use ← → arrow keys to navigate pages
      </p>
    </div>
  );
}

export default MultiPageViewer;
