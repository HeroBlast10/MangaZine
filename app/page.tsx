'use client';

import { useState } from 'react';
import { useComicStore } from '@/store/comicStore';
import { ComicCanvas } from '@/components/ComicCanvas';
import { PanelEditorSidebar } from '@/components/PanelEditorSidebar';
import { Upload, Sparkles, BookOpen, Users, Palette, Layers } from 'lucide-react';

export default function Home() {
  const project = useComicStore((s) => s.project);
  const loadProject = useComicStore((s) => s.loadProject);
  const selectedPanelId = useComicStore((s) => s.selectedPanelId);
  const [isDragging, setIsDragging] = useState(false);

  const handleFileUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const json = e.target?.result as string;
        loadProject(json);
      } catch (err) {
        alert('Invalid project JSON file');
        console.error(err);
      }
    };
    reader.readAsText(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.json')) {
      handleFileUpload(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const currentPage = project?.episodes[0]?.pages[0];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-30">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
              <Sparkles size={20} className="text-white" strokeWidth={2.5} />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-violet-400 to-purple-400 bg-clip-text text-transparent">
                MangaZine
              </h1>
              <p className="text-[10px] text-zinc-500 tracking-wide">Multi-Agent Comic Studio</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <span className="px-2 py-1 rounded bg-zinc-800 border border-zinc-700">v0.1.0-alpha</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        {!project ? (
          <div className="max-w-4xl mx-auto">
            {/* Hero Section */}
            <div className="text-center mb-12 space-y-4">
              <h2 className="text-4xl font-bold mb-3">
                漫画是工程体系，
                <br />
                <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                  而非单纯的提示词
                </span>
              </h2>
              <p className="text-zinc-400 text-lg max-w-2xl mx-auto leading-relaxed">
                MangaZine 是一个开源的多智能体漫画创作框架。
                <br />
                编剧、分镜师、提示词导演各司其职，结构化状态驱动整个生产流水线。
              </p>
            </div>

            {/* Feature Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
              <div className="p-6 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-violet-500/50 transition-all">
                <Users className="w-8 h-8 text-violet-400 mb-3" />
                <h3 className="font-semibold mb-2">多智能体协作</h3>
                <p className="text-sm text-zinc-500">
                  WriterAgent、StoryboarderAgent、PromptDirector 各司其职
                </p>
              </div>
              <div className="p-6 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-purple-500/50 transition-all">
                <Palette className="w-8 h-8 text-purple-400 mb-3" />
                <h3 className="font-semibold mb-2">风格基因系统</h3>
                <p className="text-sm text-zinc-500">
                  通过参数精确定义画风，拒绝版权侵权式提示词
                </p>
              </div>
              <div className="p-6 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-pink-500/50 transition-all">
                <Layers className="w-8 h-8 text-pink-400 mb-3" />
                <h3 className="font-semibold mb-2">非破坏性编辑</h3>
                <p className="text-sm text-zinc-500">
                  单格重绘、锁定角色、修订历史，完整的版本控制
                </p>
              </div>
            </div>

            {/* Upload Zone */}
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
              <div className="p-12 text-center space-y-4">
                <div className="flex justify-center">
                  <div className="w-16 h-16 rounded-full bg-zinc-800 flex items-center justify-center">
                    <Upload size={28} className="text-zinc-500" />
                  </div>
                </div>
                <div>
                  <h3 className="text-lg font-semibold mb-2">加载漫画项目</h3>
                  <p className="text-sm text-zinc-500 mb-4">
                    拖拽 <code className="px-1.5 py-0.5 rounded bg-zinc-800 text-violet-400 text-xs font-mono">project_final.json</code> 文件到此处
                  </p>
                  <label className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-medium cursor-pointer transition-colors">
                    <BookOpen size={16} />
                    浏览文件
                    <input
                      type="file"
                      accept=".json"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleFileUpload(file);
                      }}
                    />
                  </label>
                </div>
                <div className="pt-4 border-t border-zinc-800">
                  <p className="text-xs text-zinc-600">
                    运行 <code className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500 font-mono">python cli/run_pipeline.py "你的故事"</code> 生成项目 JSON
                  </p>
                </div>
              </div>
            </div>

            {/* Quick Links */}
            <div className="mt-8 flex justify-center gap-4 text-sm">
              <a
                href="https://github.com/HeroBlast10/MangaZine"
                target="_blank"
                rel="noopener noreferrer"
                className="text-zinc-500 hover:text-violet-400 transition-colors"
              >
                GitHub 仓库
              </a>
              <span className="text-zinc-700">·</span>
              <a
                href="https://github.com/HeroBlast10/MangaZine/blob/master/README.md"
                target="_blank"
                rel="noopener noreferrer"
                className="text-zinc-500 hover:text-violet-400 transition-colors"
              >
                使用文档
              </a>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Project Info Bar */}
            <div className="flex items-center justify-between p-4 rounded-xl bg-zinc-900 border border-zinc-800">
              <div>
                <h2 className="text-lg font-semibold">{project.title}</h2>
                <p className="text-sm text-zinc-500">
                  {project.episodes[0]?.title || 'Episode 1'} · Page {currentPage?.page_number || 1}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-3 py-1 rounded-full bg-violet-500/20 text-violet-300 text-xs font-medium">
                  {currentPage?.panels.length || 0} panels
                </span>
                <button
                  onClick={() => loadProject(null as any)}
                  className="px-4 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm transition-colors"
                >
                  关闭项目
                </button>
              </div>
            </div>

            {/* Canvas */}
            {currentPage && (
              <div className="flex gap-6">
                <div className="flex-1">
                  <ComicCanvas
                    page={currentPage}
                    className="rounded-xl overflow-hidden border border-zinc-800 shadow-2xl"
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Sidebar */}
      {selectedPanelId && project && (
        <PanelEditorSidebar characterBible={project.character_bible} />
      )}

      {/* Footer */}
      <footer className="border-t border-zinc-800 mt-16 py-6">
        <div className="container mx-auto px-6 text-center text-xs text-zinc-600">
          <p>
            MangaZine · 开源于{' '}
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
