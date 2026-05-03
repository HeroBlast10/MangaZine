'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  BookOpen,
  Layers,
  Palette,
  Play,
  Sparkles,
  Upload,
  Users,
} from 'lucide-react';
import Link from 'next/link';

import { MultiPageViewer } from '@/components/MultiPageViewer';
import { PanelEditorSidebar } from '@/components/PanelEditorSidebar';
import { useComicStore } from '@/store/comicStore';

export default function Home() {
  const project = useComicStore((state) => state.project);
  const loadProject = useComicStore((state) => state.loadProject);
  const selectedPanelId = useComicStore((state) => state.selectedPanelId);
  const clearSelectedPanel = useComicStore((state) => state.clearSelectedPanel);

  const [isDragging, setIsDragging] = useState(false);
  const [selectedEpisodeIndex, setSelectedEpisodeIndex] = useState(0);
  const [currentPageIndex, setCurrentPageIndex] = useState(0);

  const episodes = project?.episodes ?? [];
  const selectedEpisode = episodes[selectedEpisodeIndex] ?? episodes[0];
  const currentPage = useMemo(
    () => selectedEpisode?.pages[currentPageIndex] ?? selectedEpisode?.pages[0] ?? null,
    [currentPageIndex, selectedEpisode],
  );

  useEffect(() => {
    setSelectedEpisodeIndex(0);
    setCurrentPageIndex(0);
  }, [project?.project_id]);

  useEffect(() => {
    if (!selectedEpisode) {
      setCurrentPageIndex(0);
      return;
    }

    if (!selectedEpisode.pages[currentPageIndex]) {
      setCurrentPageIndex(0);
    }
  }, [currentPageIndex, selectedEpisode]);

  useEffect(() => {
    clearSelectedPanel();
  }, [clearSelectedPanel, currentPageIndex, selectedEpisodeIndex]);

  const handleFileUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const json = event.target?.result as string;
        loadProject(json);
      } catch (error) {
        alert('项目 JSON 无法解析，请确认文件格式正确。');
        console.error(error);
      }
    };
    reader.readAsText(file);
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(false);

    const file = event.dataTransfer.files[0];
    if (file && file.name.endsWith('.json')) {
      handleFileUpload(file);
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleEpisodeChange = (nextEpisodeIndex: number) => {
    setSelectedEpisodeIndex(nextEpisodeIndex);
    setCurrentPageIndex(0);
  };

  const handleCloseProject = () => {
    loadProject(null);
    setSelectedEpisodeIndex(0);
    setCurrentPageIndex(0);
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="sticky top-0 z-30 border-b border-zinc-800 bg-zinc-900/60 backdrop-blur-sm">
        <div className="container mx-auto flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-purple-600">
              <Sparkles size={20} className="text-white" strokeWidth={2.5} />
            </div>
            <div>
              <h1 className="bg-gradient-to-r from-violet-400 to-purple-400 bg-clip-text text-xl font-bold text-transparent">
                MangaZine
              </h1>
              <p className="text-[10px] tracking-wide text-zinc-500">
                Multi-Agent Comic Studio
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/pipeline"
              className="flex items-center gap-1.5 rounded-lg border border-violet-700 bg-violet-900/30 px-3 py-1.5 text-xs font-medium text-violet-300 transition-colors hover:bg-violet-800/50"
            >
              <Play size={12} />
              Pipeline 控制台
            </Link>
            <span className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs text-zinc-500">
              v0.3.0
            </span>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">
        {!project ? (
          <div className="mx-auto max-w-5xl">
            <div className="mb-12 space-y-4 text-center">
              <h2 className="text-4xl font-bold leading-tight">
                漫画是一整套生产流程，
                <br />
                <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                  而不是一句提示词
                </span>
              </h2>
              <p className="mx-auto max-w-2xl text-lg leading-relaxed text-zinc-400">
                MangaZine 是一个面向 AI 漫画创作的多智能体工作台。
                <br />
                从角色设定、分镜拆解到单格重生成，全部围绕结构化项目状态来驱动。
              </p>
            </div>

            <div className="mb-12 grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6 transition-all hover:border-violet-500/50">
                <Users className="mb-3 h-8 w-8 text-violet-400" />
                <h3 className="mb-2 font-semibold">多智能体协作</h3>
                <p className="text-sm text-zinc-500">
                  Writer、Storyboarder、Prompt Director 分工协作，让漫画生产链条可追踪、可迭代。
                </p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6 transition-all hover:border-purple-500/50">
                <Palette className="mb-3 h-8 w-8 text-purple-400" />
                <h3 className="mb-2 font-semibold">风格 DNA</h3>
                <p className="text-sm text-zinc-500">
                  用可控参数描述画风，而不是依赖模糊的作者名提示词。
                </p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6 transition-all hover:border-pink-500/50">
                <Layers className="mb-3 h-8 w-8 text-pink-400" />
                <h3 className="mb-2 font-semibold">非破坏式迭代</h3>
                <p className="text-sm text-zinc-500">
                  支持单格重生成、修订历史和尽量保持角色、风格、构图的返工流程。
                </p>
              </div>
            </div>

            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              className={[
                'relative rounded-2xl border-2 border-dashed transition-all duration-200',
                isDragging
                  ? 'border-violet-500 bg-violet-500/10'
                  : 'border-zinc-700 bg-zinc-900/50 hover:border-zinc-600',
              ].join(' ')}
            >
              <div className="space-y-4 p-12 text-center">
                <div className="flex justify-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-zinc-800">
                    <Upload size={28} className="text-zinc-500" />
                  </div>
                </div>
                <div>
                  <h3 className="mb-2 text-lg font-semibold">载入漫画项目</h3>
                  <p className="mb-4 text-sm text-zinc-500">
                    将
                    {' '}
                    <code className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-violet-400">
                      project_final.json
                    </code>
                    {' '}
                    拖到这里，或直接从磁盘选择文件。
                  </p>
                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-violet-600 px-6 py-2.5 font-medium text-white transition-colors hover:bg-violet-500">
                    <BookOpen size={16} />
                    浏览文件
                    <input
                      type="file"
                      accept=".json"
                      className="hidden"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) {
                          handleFileUpload(file);
                        }
                      }}
                    />
                  </label>
                </div>
                <div className="border-t border-zinc-800 pt-4">
                  <p className="text-xs text-zinc-600">
                    也可以先运行
                    {' '}
                    <code className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-zinc-400">
                      python cli/run_pipeline.py &quot;你的故事&quot;
                    </code>
                    {' '}
                    生成项目 JSON。
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-8 flex justify-center gap-4 text-sm">
              <a
                href="https://github.com/HeroBlast10/MangaZine"
                target="_blank"
                rel="noopener noreferrer"
                className="text-zinc-500 transition-colors hover:text-violet-400"
              >
                GitHub 仓库
              </a>
              <span className="text-zinc-700">·</span>
              <a
                href="https://github.com/HeroBlast10/MangaZine/blob/master/README.md"
                target="_blank"
                rel="noopener noreferrer"
                className="text-zinc-500 transition-colors hover:text-violet-400"
              >
                使用说明
              </a>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900 p-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-lg font-semibold">{project.title}</h2>
                <p className="text-sm text-zinc-500">
                  {selectedEpisode?.title ?? '未命名章节'}
                  {' · '}
                  第 {currentPage?.page_number ?? 1} 页
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                {episodes.length > 0 && (
                  <label className="flex items-center gap-2 text-sm text-zinc-400">
                    <span>章节</span>
                    <select
                      value={selectedEpisodeIndex}
                      onChange={(event) => handleEpisodeChange(Number(event.target.value))}
                      className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm text-zinc-200 outline-none transition-colors focus:border-violet-500"
                    >
                      {episodes.map((episode, index) => (
                        <option key={episode.episode_id} value={index}>
                          第 {episode.episode_number} 话 · {episode.title}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <span className="rounded-full bg-violet-500/20 px-3 py-1 text-xs font-medium text-violet-300">
                  当前页 {currentPage?.panels.length ?? 0} 个分镜
                </span>
                <button
                  type="button"
                  onClick={handleCloseProject}
                  className="rounded-lg bg-zinc-800 px-4 py-1.5 text-sm transition-colors hover:bg-zinc-700"
                >
                  关闭项目
                </button>
              </div>
            </div>

            {selectedEpisode && (
              <MultiPageViewer
                key={selectedEpisode.episode_id}
                episode={selectedEpisode}
                onCurrentPageChange={(_, pageIndex) => {
                  setCurrentPageIndex(pageIndex);
                }}
              />
            )}
          </div>
        )}
      </main>

      {selectedPanelId && project && (
        <PanelEditorSidebar
          characterBible={project.character_bible}
          stylePack={project.style_pack}
        />
      )}

      <footer className="mt-16 border-t border-zinc-800 py-6">
        <div className="container mx-auto px-6 text-center text-xs text-zinc-600">
          <p>
            MangaZine · 基于
            {' '}
            <a
              href="https://github.com/HeroBlast10/MangaZine"
              className="text-violet-400 hover:underline"
            >
              MIT License
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
