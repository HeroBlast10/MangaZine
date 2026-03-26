'use client';

import React, { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Grid, Layers } from 'lucide-react';

import { ComicCanvas } from './ComicCanvas';
import type { EpisodeOutline, PageSpec } from '@/types/comic';

interface MultiPageViewerProps {
  episode: EpisodeOutline;
  className?: string;
  onCurrentPageChange?: (page: PageSpec, pageIndex: number) => void;
}

type ViewMode = 'single' | 'grid';

export function MultiPageViewer({
  episode,
  className = '',
  onCurrentPageChange,
}: MultiPageViewerProps) {
  const [currentPage, setCurrentPage] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>('single');

  const pages = episode.pages;
  const totalPages = pages.length;

  useEffect(() => {
    setCurrentPage(0);
    setViewMode('single');
  }, [episode.episode_id]);

  useEffect(() => {
    if (!pages[currentPage]) {
      return;
    }

    onCurrentPageChange?.(pages[currentPage], currentPage);
  }, [currentPage, onCurrentPageChange, pages]);

  useEffect(() => {
    if (viewMode !== 'single') {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'ArrowLeft') {
        setCurrentPage((previous) => Math.max(0, previous - 1));
      }

      if (event.key === 'ArrowRight') {
        setCurrentPage((previous) => Math.min(totalPages - 1, previous + 1));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [totalPages, viewMode]);

  if (totalPages === 0) {
    return (
      <div className={`flex h-64 items-center justify-center rounded-lg bg-zinc-900 ${className}`}>
        <p className="text-zinc-500">当前章节还没有页面。</p>
      </div>
    );
  }

  const goToPrevPage = () => {
    setCurrentPage((previous) => Math.max(0, previous - 1));
  };

  const goToNextPage = () => {
    setCurrentPage((previous) => Math.min(totalPages - 1, previous + 1));
  };

  const goToPage = (pageIndex: number) => {
    setCurrentPage(Math.max(0, Math.min(totalPages - 1, pageIndex)));
  };

  return (
    <div className={`flex flex-col gap-4 ${className}`}>
      <div className="flex items-center justify-between rounded-lg bg-zinc-900 px-4 py-2">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-bold text-white">
            第 {episode.episode_number} 话 · {episode.title}
          </h2>
          <span className="text-sm text-zinc-400">{totalPages} 页</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setViewMode('single')}
            className={`rounded p-2 ${
              viewMode === 'single' ? 'bg-violet-600' : 'bg-zinc-800 hover:bg-zinc-700'
            }`}
            title="单页查看"
            aria-label="单页查看"
          >
            <Layers className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setViewMode('grid')}
            className={`rounded p-2 ${
              viewMode === 'grid' ? 'bg-violet-600' : 'bg-zinc-800 hover:bg-zinc-700'
            }`}
            title="网格查看"
            aria-label="网格查看"
          >
            <Grid className="h-4 w-4" />
          </button>
        </div>
      </div>

      {viewMode === 'single' && (
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={goToPrevPage}
            disabled={currentPage === 0}
            className="rounded-full bg-zinc-800 p-3 transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-30"
            aria-label="上一页"
          >
            <ChevronLeft className="h-6 w-6" />
          </button>

          <div className="flex flex-1 flex-col items-center gap-2">
            <ComicCanvas page={pages[currentPage]} className="mx-auto max-w-lg shadow-2xl" />
            <span className="text-sm text-zinc-400">
              第 {currentPage + 1} 页，共 {totalPages} 页
            </span>
          </div>

          <button
            type="button"
            onClick={goToNextPage}
            disabled={currentPage === totalPages - 1}
            className="rounded-full bg-zinc-800 p-3 transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-30"
            aria-label="下一页"
          >
            <ChevronRight className="h-6 w-6" />
          </button>
        </div>
      )}

      {viewMode === 'grid' && (
        <div className="grid grid-cols-2 gap-4 p-4 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {pages.map((page, index) => (
            <div
              key={page.page_id}
              onClick={() => {
                setCurrentPage(index);
                setViewMode('single');
              }}
              className={`cursor-pointer transition-all hover:scale-[1.02] ${
                index === currentPage ? 'ring-2 ring-violet-500' : ''
              }`}
            >
              <ComicCanvas page={page} className="shadow-lg" />
              <p className="mt-1 text-center text-xs text-zinc-400">第 {index + 1} 页</p>
            </div>
          ))}
        </div>
      )}

      {viewMode === 'single' && totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 overflow-x-auto px-4 py-2">
          {pages.map((page, index) => (
            <button
              key={page.page_id}
              type="button"
              onClick={() => goToPage(index)}
              className={`h-16 w-12 flex-shrink-0 overflow-hidden rounded transition-all ${
                index === currentPage
                  ? 'scale-110 ring-2 ring-violet-500'
                  : 'opacity-60 hover:opacity-100'
              }`}
              aria-label={`跳转到第 ${index + 1} 页`}
            >
              <div className="flex h-full w-full items-center justify-center bg-zinc-800 text-xs text-zinc-400">
                {index + 1}
              </div>
            </button>
          ))}
        </div>
      )}

      {viewMode === 'single' && totalPages > 1 && (
        <p className="text-center text-xs text-zinc-600">
          可使用键盘左右方向键翻页。
        </p>
      )}
    </div>
  );
}

export default MultiPageViewer;
