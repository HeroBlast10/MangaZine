'use client';

import {
  Activity,
  ArrowLeft,
  CheckCircle2,
  CircleDot,
  Clock,
  DollarSign,
  Image,
  Loader2,
  Play,
  Sparkles,
  XCircle,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import { useCallback, useRef, useState } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PipelineEvent {
  event_type: string;
  pipeline_run_id?: string;
  step_name?: string;
  agent_name?: string;
  payload?: Record<string, unknown>;
  timestamp?: string;
  elapsed_ms?: number;
}

interface StepInfo {
  name: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  elapsed_ms?: number;
}

const STEP_LABELS: Record<string, string> = {
  style_pack: '风格 DNA',
  character_bible: '角色圣经',
  episode_outline: '剧情大纲',
  storyboard: '分镜排版',
  prompt_synthesis: '提示词合成',
  image_generation: '图像渲染',
  assembly: '项目组装',
};

const ALL_STEPS = Object.keys(STEP_LABELS);

interface TokenSummary {
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  total_latency_ms: number;
}

// ---------------------------------------------------------------------------
// Pipeline console page
// ---------------------------------------------------------------------------

export default function PipelinePage() {
  const [premise, setPremise] = useState('');
  const [pages, setPages] = useState(4);
  const [isRunning, setIsRunning] = useState(false);
  const [steps, setSteps] = useState<StepInfo[]>(
    ALL_STEPS.map((name) => ({ name, label: STEP_LABELS[name], status: 'pending' })),
  );
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [tokenSummary, setTokenSummary] = useState<TokenSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const resetState = useCallback(() => {
    setSteps(ALL_STEPS.map((name) => ({ name, label: STEP_LABELS[name], status: 'pending' })));
    setEvents([]);
    setTokenSummary(null);
    setError(null);
    setCompleted(false);
  }, []);

  const handleStart = useCallback(async () => {
    if (!premise.trim()) return;
    resetState();
    setIsRunning(true);

    try {
      const response = await fetch(`${apiBase}/api/v1/pipeline/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          premise: premise.trim(),
          target_pages: pages,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event: PipelineEvent = JSON.parse(line.slice(6));
            setEvents((prev) => [...prev, event]);

            if (event.event_type === 'step.started') {
              setSteps((prev) =>
                prev.map((s) =>
                  s.name === event.step_name ? { ...s, status: 'running' } : s,
                ),
              );
            } else if (event.event_type === 'step.completed') {
              setSteps((prev) =>
                prev.map((s) =>
                  s.name === event.step_name
                    ? {
                        ...s,
                        status: 'completed',
                        elapsed_ms: (event.payload?.elapsed_ms as number) || 0,
                      }
                    : s,
                ),
              );
            } else if (event.event_type === 'step.failed') {
              setSteps((prev) =>
                prev.map((s) =>
                  s.name === event.step_name ? { ...s, status: 'failed' } : s,
                ),
              );
            } else if (event.event_type === 'pipeline.completed') {
              setCompleted(true);
            } else if (event.event_type === 'pipeline.failed') {
              setError((event.payload?.error as string) || 'Pipeline failed');
            } else if (event.event_type === 'token_summary') {
              setTokenSummary(event as unknown as TokenSummary);
            }
          } catch {
            // skip malformed lines
          }
        }
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsRunning(false);
    }
  }, [premise, pages, apiBase, resetState]);

  const completedSteps = steps.filter((s) => s.status === 'completed').length;
  const totalElapsed = steps.reduce((sum, s) => sum + (s.elapsed_ms || 0), 0);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-zinc-800 bg-zinc-900/60 backdrop-blur-sm">
        <div className="container mx-auto flex items-center gap-4 px-6 py-4">
          <Link href="/" className="text-zinc-500 transition-colors hover:text-zinc-200">
            <ArrowLeft size={20} />
          </Link>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-purple-600">
              <Sparkles size={20} className="text-white" strokeWidth={2.5} />
            </div>
            <div>
              <h1 className="text-xl font-bold text-zinc-100">Pipeline 控制台</h1>
              <p className="text-[10px] tracking-wide text-zinc-500">
                实时多 Agent 生产流水线
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          {/* Left: Input & Steps */}
          <div className="space-y-6 lg:col-span-1">
            {/* Input form */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500">
                创作参数
              </h2>
              <div className="space-y-4">
                <div>
                  <label className="mb-1 block text-xs text-zinc-500">故事前提</label>
                  <textarea
                    value={premise}
                    onChange={(e) => setPremise(e.target.value)}
                    rows={3}
                    placeholder="赛博朋克大厨用激光锅铲对决美食评论家..."
                    disabled={isRunning}
                    className="w-full resize-none rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 transition-colors focus:border-violet-500 focus:outline-none disabled:opacity-50"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-zinc-500">页数</label>
                  <input
                    type="number"
                    value={pages}
                    onChange={(e) => setPages(Math.max(1, Math.min(20, Number(e.target.value))))}
                    min={1}
                    max={20}
                    disabled={isRunning}
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 focus:border-violet-500 focus:outline-none disabled:opacity-50"
                  />
                </div>
                <button
                  onClick={handleStart}
                  disabled={isRunning || !premise.trim()}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-900/40 transition-all hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isRunning ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      运行中...
                    </>
                  ) : (
                    <>
                      <Play size={16} />
                      启动 Pipeline
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Step progress */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500">
                Agent 执行链路
              </h2>
              <div className="space-y-3">
                {steps.map((step, i) => (
                  <div key={step.name} className="flex items-center gap-3">
                    <div className="flex h-7 w-7 flex-none items-center justify-center">
                      {step.status === 'completed' ? (
                        <CheckCircle2 size={18} className="text-green-400" />
                      ) : step.status === 'running' ? (
                        <Loader2 size={18} className="animate-spin text-violet-400" />
                      ) : step.status === 'failed' ? (
                        <XCircle size={18} className="text-red-400" />
                      ) : (
                        <CircleDot size={18} className="text-zinc-700" />
                      )}
                    </div>
                    <div className="flex-1">
                      <p
                        className={`text-sm font-medium ${
                          step.status === 'running'
                            ? 'text-violet-300'
                            : step.status === 'completed'
                              ? 'text-zinc-300'
                              : 'text-zinc-600'
                        }`}
                      >
                        {step.label}
                      </p>
                    </div>
                    {step.elapsed_ms != null && step.elapsed_ms > 0 && (
                      <span className="text-xs font-mono text-zinc-600">
                        {(step.elapsed_ms / 1000).toFixed(1)}s
                      </span>
                    )}
                  </div>
                ))}
              </div>
              {(isRunning || completed) && (
                <div className="mt-4 border-t border-zinc-800 pt-3">
                  <div className="flex items-center justify-between text-xs text-zinc-500">
                    <span>{completedSteps}/{ALL_STEPS.length} 步完成</span>
                    <span className="flex items-center gap-1">
                      <Clock size={12} />
                      {(totalElapsed / 1000).toFixed(1)}s
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-800">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-violet-500 to-purple-500 transition-all duration-500"
                      style={{ width: `${(completedSteps / ALL_STEPS.length) * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Cost dashboard */}
            {tokenSummary && (
              <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500">
                  成本仪表盘
                </h2>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-zinc-800 p-3">
                    <div className="flex items-center gap-2 text-xs text-zinc-500">
                      <Zap size={12} />
                      LLM 调用
                    </div>
                    <p className="mt-1 text-lg font-bold text-zinc-200">
                      {tokenSummary.total_calls}
                    </p>
                  </div>
                  <div className="rounded-lg bg-zinc-800 p-3">
                    <div className="flex items-center gap-2 text-xs text-zinc-500">
                      <Activity size={12} />
                      Token 总量
                    </div>
                    <p className="mt-1 text-lg font-bold text-zinc-200">
                      {tokenSummary.total_tokens.toLocaleString()}
                    </p>
                  </div>
                  <div className="rounded-lg bg-zinc-800 p-3">
                    <div className="flex items-center gap-2 text-xs text-zinc-500">
                      <DollarSign size={12} />
                      预估费用
                    </div>
                    <p className="mt-1 text-lg font-bold text-green-400">
                      ${tokenSummary.total_cost_usd.toFixed(4)}
                    </p>
                  </div>
                  <div className="rounded-lg bg-zinc-800 p-3">
                    <div className="flex items-center gap-2 text-xs text-zinc-500">
                      <Clock size={12} />
                      总耗时
                    </div>
                    <p className="mt-1 text-lg font-bold text-zinc-200">
                      {(tokenSummary.total_latency_ms / 1000).toFixed(1)}s
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right: Event log */}
          <div className="lg:col-span-2">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500">
                实时事件流
              </h2>

              {error && (
                <div className="mb-4 rounded-lg border border-red-800 bg-red-950/50 p-3">
                  <p className="text-sm text-red-300">{error}</p>
                </div>
              )}

              {completed && (
                <div className="mb-4 rounded-lg border border-green-800 bg-green-950/50 p-3">
                  <p className="flex items-center gap-2 text-sm text-green-300">
                    <CheckCircle2 size={16} />
                    Pipeline 完成! 前往首页载入项目文件查看结果。
                  </p>
                </div>
              )}

              {events.length === 0 && !isRunning ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Activity size={40} className="mb-4 text-zinc-800" />
                  <p className="text-sm text-zinc-600">
                    输入故事前提并点击"启动 Pipeline"，
                    <br />
                    事件流将在这里实时显示。
                  </p>
                </div>
              ) : (
                <div className="max-h-[600px] space-y-1 overflow-y-auto font-mono text-xs scrollbar-thin scrollbar-track-zinc-900 scrollbar-thumb-zinc-700">
                  {events.map((event, i) => (
                    <div
                      key={i}
                      className={`rounded px-3 py-1.5 ${
                        event.event_type.includes('failed') || event.event_type === 'error'
                          ? 'bg-red-950/30 text-red-400'
                          : event.event_type.includes('completed')
                            ? 'bg-green-950/20 text-green-400'
                            : event.event_type.includes('started')
                              ? 'bg-violet-950/20 text-violet-400'
                              : event.event_type === 'image.generated'
                                ? 'bg-blue-950/20 text-blue-400'
                                : 'bg-zinc-900 text-zinc-500'
                      }`}
                    >
                      <span className="mr-2 text-zinc-700">
                        {event.timestamp
                          ? new Date(event.timestamp).toLocaleTimeString()
                          : '--:--:--'}
                      </span>
                      <span className="mr-2 font-semibold">
                        [{event.event_type}]
                      </span>
                      {event.step_name && (
                        <span className="mr-2">{event.step_name}</span>
                      )}
                      {event.payload && Object.keys(event.payload).length > 0 && (
                        <span className="text-zinc-600">
                          {JSON.stringify(event.payload)}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
