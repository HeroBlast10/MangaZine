'use client';

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
import React, { useEffect, useState } from 'react';

import { resolveRenderImageUrl } from '@/lib/projectImageUrl';
import {
  useComicStore,
  usePanelIsRerendering,
  useSelectedPanel,
} from '@/store/comicStore';
import type {
  CharacterBible,
  LockConstraints,
  RenderOutput,
  RerenderRequest,
  RerenderResponse,
  StylePack,
} from '@/types/comic';

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
      {children}
    </h3>
  );
}

function Badge({
  children,
  variant = 'default',
}: {
  children: React.ReactNode;
  variant?: 'default' | 'violet' | 'yellow';
}) {
  const cls = {
    default: 'border-zinc-700 bg-zinc-800 text-zinc-300',
    violet: 'border-violet-800 bg-violet-950 text-violet-300',
    yellow: 'border-yellow-800 bg-yellow-950 text-yellow-300',
  }[variant];

  return (
    <span className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-mono ${cls}`}>
      {children}
    </span>
  );
}

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
        'flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium',
        'select-none transition-all duration-100',
        locked
          ? 'border-violet-600 bg-violet-900/60 text-violet-200 hover:bg-violet-900'
          : 'border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300',
      ].join(' ')}
    >
      {locked ? <Lock size={11} strokeWidth={2.5} /> : <Unlock size={11} strokeWidth={2} />}
      {label}
    </button>
  );
}

interface RevisionHistoryProps {
  history: RenderOutput[];
}

function RevisionHistory({ history }: RevisionHistoryProps) {
  const [open, setOpen] = useState(false);

  if (!history || history.length === 0) {
    return <div className="text-xs italic text-zinc-600">还没有修订历史。</div>;
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-1.5 text-xs text-zinc-400 transition-colors hover:text-zinc-200"
      >
        <History size={12} />
        <span>{history.length} 个版本</span>
        {open ? <ChevronUp size={12} className="ml-auto" /> : <ChevronDown size={12} className="ml-auto" />}
      </button>

      {open && (
        <div className="mt-2 flex gap-2 overflow-x-auto pb-1 scrollbar-thin scrollbar-track-zinc-900 scrollbar-thumb-zinc-700">
          {[...history].reverse().map((revision, index) => {
            const revisionUrl = resolveRenderImageUrl(revision);
            const revisionNumber = history.length - index;

            return (
              <div
                key={`${revision.generated_at ?? 'revision'}-${revisionNumber}`}
                className="group relative h-28 w-20 flex-none overflow-hidden rounded border border-zinc-700 bg-zinc-800"
                title={revision.generated_at ?? '未知时间'}
              >
                {revisionUrl ? (
                  <img
                    src={revisionUrl}
                    alt={`修订版本 ${revisionNumber}`}
                    className="h-full w-full object-cover opacity-70 transition-opacity group-hover:opacity-100"
                    loading="lazy"
                    decoding="async"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-[9px] text-zinc-600">
                    无图片
                  </div>
                )}
                <span className="absolute bottom-0 left-0 right-0 bg-black/60 py-0.5 text-center text-[8px] font-mono text-zinc-400">
                  v{revisionNumber}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

interface PanelEditorSidebarProps {
  characterBible?: CharacterBible;
  stylePack: StylePack;
}

export function PanelEditorSidebar({
  characterBible,
  stylePack,
}: PanelEditorSidebarProps) {
  const panel = useSelectedPanel();
  const selectedPageId = useComicStore((state) => state.selectedPageId);
  const clearSelectedPanel = useComicStore((state) => state.clearSelectedPanel);
  const updatePanelImage = useComicStore((state) => state.updatePanelImage);
  const setRerenderingPanel = useComicStore((state) => state.setRerenderingPanel);
  const isRerendering = usePanelIsRerendering(panel?.panel_id ?? '');

  const [locks, setLocks] = useState<LockConstraints>({
    lock_characters: true,
    lock_style: true,
    lock_composition: false,
    lock_dialogue: false,
  });
  const [promptOverride, setPromptOverride] = useState('');
  const [rerenderError, setRerenderError] = useState<string | null>(null);

  useEffect(() => {
    setPromptOverride(panel?.prompt_plan ?? '');
    setRerenderError(null);
  }, [panel?.panel_id, panel?.prompt_plan]);

  const previewUrl = panel ? resolveRenderImageUrl(panel.render_output) : null;
  const hasImage = Boolean(
    panel &&
      previewUrl &&
      (panel.render_output.status === 'draft_ready' ||
        panel.render_output.status === 'approved'),
  );

  if (!panel || !selectedPageId) {
    return null;
  }

  const toggleLock = (key: keyof LockConstraints) => {
    setLocks((previous) => ({ ...previous, [key]: !previous[key] }));
  };

  const lookupCharacterName = (id: string): string => {
    if (!characterBible) {
      return id.slice(0, 8);
    }

    const character = characterBible.characters.find((item) => item.character_id === id);
    return character?.name ?? id.slice(0, 8);
  };

  const handleRerender = async () => {
    setRerenderError(null);
    setRerenderingPanel(panel.panel_id, true);

    const panelToSend = promptOverride.trim()
      ? { ...panel, prompt_plan: promptOverride.trim() }
      : panel;

    const body: RerenderRequest = {
      panel: panelToSend,
      page_id: selectedPageId,
      style_pack: stylePack,
      character_bible: characterBible ?? { characters: [] },
      lock_constraints: locks,
    };

    try {
      const response = await fetch('/api/rerender-panel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(errorBody?.error ?? response.statusText);
      }

      const data: RerenderResponse = await response.json();
      updatePanelImage(selectedPageId, panel.panel_id, data.image_url, {
        model_used: data.model_used,
        generation_params: data.generation_params,
        generated_at: data.generated_at,
      });
    } catch (error) {
      setRerenderError((error as Error).message);
    } finally {
      setRerenderingPanel(panel.panel_id, false);
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
        onClick={clearSelectedPanel}
        aria-hidden
      />

      <aside
        aria-label="Panel editor"
        className="fixed right-0 top-0 z-50 flex h-full w-96 translate-x-0 flex-col border-l border-zinc-800 bg-zinc-900 shadow-2xl transition-transform duration-200"
      >
        <div className="flex flex-none items-center justify-between border-b border-zinc-800 px-4 py-3">
          <div className="flex items-center gap-2">
            <Camera size={14} className="text-violet-400" />
            <span className="text-sm font-semibold text-zinc-100">分镜 {panel.panel_index}</span>
            <Badge variant="violet">{panel.shot_type.replace(/_/g, ' ')}</Badge>
            <Badge>{panel.camera_angle.replace(/_/g, ' ')}</Badge>
          </div>
          <button
            type="button"
            onClick={clearSelectedPanel}
            className="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
            aria-label="关闭分镜编辑器"
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4 scrollbar-thin scrollbar-track-zinc-900 scrollbar-thumb-zinc-700">
          {hasImage && previewUrl && (
            <div className="relative aspect-[2/3] w-full overflow-hidden rounded border border-zinc-800 bg-zinc-950">
              <img
                src={previewUrl}
                alt={`分镜 ${panel.panel_index} 预览`}
                className="h-full w-full object-cover"
                loading="lazy"
                decoding="async"
              />
              {panel.render_output.model_used && (
                <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1 text-[8px] font-mono text-zinc-400">
                  {panel.render_output.model_used.split('-').slice(-1)[0]}
                </span>
              )}
            </div>
          )}

          <div>
            <SectionHeading>场景信息</SectionHeading>
            {panel.setting_description && (
              <p className="mb-1 text-xs leading-relaxed text-zinc-400">
                <span className="text-zinc-600">场景：</span>
                {panel.setting_description}
              </p>
            )}
            {panel.action_description && (
              <p className="text-xs leading-relaxed text-zinc-400">
                <span className="text-zinc-600">动作：</span>
                {panel.action_description}
              </p>
            )}
          </div>

          {panel.characters.length > 0 && (
            <div>
              <SectionHeading>角色</SectionHeading>
              <div className="flex flex-wrap gap-1.5">
                {panel.characters.map((id) => (
                  <Badge key={id} variant="violet">
                    {lookupCharacterName(id)}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {panel.dialogue.length > 0 && (
            <div>
              <SectionHeading>对白</SectionHeading>
              <div className="space-y-1.5">
                {[...panel.dialogue]
                  .sort((left, right) => left.reading_order - right.reading_order)
                  .map((line, index) => (
                    <div
                      key={`${line.reading_order}-${index}`}
                      className="flex items-start gap-2 rounded border border-zinc-800 bg-zinc-800/50 px-2.5 py-1.5"
                    >
                      <span className="mt-0.5 flex-none text-[9px] font-mono uppercase text-zinc-600">
                        {line.balloon_type}
                      </span>
                      <p className="text-xs leading-snug text-zinc-300">
                        {line.character_id && (
                          <span className="mr-1 font-medium text-violet-400">
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

          <div>
            <SectionHeading>重生成提示词</SectionHeading>
            <textarea
              value={promptOverride}
              onChange={(event) => setPromptOverride(event.target.value)}
              rows={5}
              className="w-full resize-none rounded border border-zinc-700 bg-zinc-800 px-2.5 py-2 text-xs leading-relaxed text-zinc-300 transition-colors placeholder-zinc-600 focus:border-violet-600 focus:outline-none focus:ring-1 focus:ring-violet-600/50"
              placeholder="可在这里补充你希望重生成时强调的画面细节。"
            />
            {promptOverride !== panel.prompt_plan && (
              <p className="mt-1 text-[10px] text-yellow-500">
                已启用临时提示词覆盖，不会改写原始 `PanelSpec` 内容。
              </p>
            )}
          </div>

          <div>
            <SectionHeading>尽量保持项</SectionHeading>
            <p className="mb-2 text-[10px] leading-relaxed text-zinc-600">
              这些选项会以提示词约束的形式尽量保持原有元素，不代表像素级硬锁定。
            </p>
            <div className="flex flex-wrap gap-2">
              <LockToggle
                label="尽量保持角色"
                locked={locks.lock_characters}
                onToggle={() => toggleLock('lock_characters')}
              />
              <LockToggle
                label="尽量保持风格"
                locked={locks.lock_style}
                onToggle={() => toggleLock('lock_style')}
              />
              <LockToggle
                label="尽量保持构图"
                locked={locks.lock_composition}
                onToggle={() => toggleLock('lock_composition')}
              />
              <LockToggle
                label="尽量保持对白"
                locked={locks.lock_dialogue}
                onToggle={() => toggleLock('lock_dialogue')}
              />
            </div>
          </div>

          {rerenderError && (
            <div className="rounded border border-red-800 bg-red-950/50 px-3 py-2">
              <p className="text-xs leading-snug text-red-300">
                <span className="font-semibold">重生成失败：</span>
                {rerenderError}
              </p>
            </div>
          )}

          <div>
            <SectionHeading>修订历史</SectionHeading>
            <RevisionHistory history={panel.revision_history ?? []} />
          </div>

          <div className="h-4" />
        </div>

        <div className="flex-none border-t border-zinc-800 bg-zinc-900 px-4 py-3">
          <button
            type="button"
            onClick={handleRerender}
            disabled={isRerendering}
            className={[
              'flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold',
              'transition-all duration-150',
              isRerendering
                ? 'cursor-not-allowed bg-zinc-800 text-zinc-500'
                : 'bg-violet-600 text-white shadow-lg shadow-violet-900/40 hover:bg-violet-500 active:scale-[0.98]',
            ].join(' ')}
          >
            <RefreshCw
              size={15}
              strokeWidth={2.5}
              className={isRerendering ? 'animate-spin' : ''}
            />
            {isRerendering ? '生成中...' : '重新生成当前分镜'}
          </button>
          <p className="mt-1.5 text-center text-[10px] text-zinc-600">
            当前图片会先保存到修订历史，再写入新的生成结果。
          </p>
        </div>
      </aside>
    </>
  );
}
