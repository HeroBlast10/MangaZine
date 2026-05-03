<p align="center">
  <img src="https://img.shields.io/badge/MangaZine-v0.3.0-7C3AED?style=for-the-badge" alt="MangaZine" />
</p>

<h1 align="center">MangaZine</h1>

<p align="center">
  <strong>生产级多 Agent 协作漫画创作系统</strong><br/>
  漫画是一整套工程体系，而不是一句提示词。
</p>

<p align="center">
  <a href="./README_en.md"><strong>English README →</strong></a>
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python" /></a>
  <a href="https://nextjs.org/"><img src="https://img.shields.io/badge/Next.js-14-black" alt="Next.js" /></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.111+-009688" alt="FastAPI" /></a>
  <a href="https://docs.pydantic.dev/"><img src="https://img.shields.io/badge/Pydantic-v2-e92063" alt="Pydantic" /></a>
  <img src="https://img.shields.io/badge/tests-35%20passed-brightgreen" alt="Tests" />
</p>

---

## 这个项目解决什么问题？

市面上的 AI 图像工具都是**单图抽卡**模式——输入一句提示词，等待一张图。但漫画不是单张图片的集合，它是**角色 × 风格 × 叙事 × 分镜 × 构图 × 迭代**的复杂工程链。

MangaZine 将这条链路拆解为**4 个专职 Agent + 1 套编排引擎**，让每个环节可检查、可回退、可迭代：

```
故事前提 → WriterAgent（角色/大纲/对白/自审） → StoryboarderAgent（分镜/节奏校验）
         → PromptDirectorAgent（确定性提示词合成） → ImageAdapter（多模型渲染）
         → QualityReviewerAgent（Vision LLM 质量门控 + 自动重生成）
```

> 面试官问你"Agent 之间怎么协作的"，你可以打开代码逐行回答——因为 README 描述的架构图和代码实现**完全一致**。

---

## 核心亮点

### 1. 状态机驱动的 Agent 编排引擎

不是一个 500 行的 `async` 函数，而是真正的**有限状态机 + 事件驱动**编排：

```python
PipelineState: INIT → STYLE_PACK → CHARACTER_BIBLE → EPISODE_OUTLINE
             → STORYBOARD → PROMPT_SYNTHESIS → IMAGE_GENERATION → ASSEMBLY → COMPLETED
```

- 每个状态转换真正调用对应 Agent 的 `.run()` 方法
- `EventBus` 异步发布-订阅，前端通过 SSE 实时消费
- `CheckpointManager` 每步自动保存，支持断点恢复
- Agent 通过 `BaseLLMAdapter` 接口注入，一行代码切换 mock / Gemini / OpenAI

### 2. 四大专职 Agent

| Agent | 职责 | 关键能力 |
|---|---|---|
| **WriterAgent** | 角色圣经、剧情大纲、对白草稿 | Critic 自审循环（最多 2 轮修订），叙事节奏检查 |
| **StoryboarderAgent** | 多页分镜、布局模板选择 | 视觉节奏校验（限制广角镜头密度），自动修正 |
| **PromptDirectorAgent** | PanelSpec + StylePack + CharacterBible → 提示词 | 完全确定性，零 LLM 调用，100% 可测试 |
| **QualityReviewerAgent** | Vision LLM 后生成评估 | 5 维评分 + 自动 prompt refinement + 重生成 |

### 3. 全链路可观测性

```
Trace: pipeline_run_abc123
  ├─ Span: WriterAgent.character_bible     (2.3s, 1200 tokens, $0.0021)
  ├─ Span: WriterAgent.critic_review       (1.8s, 800 tokens, $0.0014)
  ├─ Span: StoryboarderAgent.page_1        (2.5s, 1600 tokens, $0.0028)
  ├─ Span: PromptDirectorAgent.synthesize  (0.01s, deterministic)
  └─ Span: ImageAdapter.render_panel_1     (8.2s)
```

- **TokenTracker**：每次 LLM 调用自动记录 input/output token 数、延迟、成本估算
- **AgentMessage 协议**：trace_id 全链路追踪 + parent_message_id 因果链
- **OpenTelemetry**：可导出到 Jaeger / Zipkin，未安装 SDK 时 no-op 降级

### 4. FastAPI 后端 + SSE 实时流

彻底替代 `child_process.spawn` 的临时方案：

| 端点 | 功能 |
|---|---|
| `POST /api/v1/pipeline/run` | SSE 流式事件推送，实时追踪每个 Agent 步骤 |
| `POST /api/v1/panel/rerender` | 单格重生成 |
| `GET /api/v1/projects` | 项目列表 |
| `GET /api/v1/project/{path}` | 项目详情 |

### 5. 35 项自动化测试

```
tests/
├── unit/
│   ├── test_prompt_director.py     # 13 项 — 确定性逻辑 100% 覆盖
│   ├── test_writer_agent.py        # 4 项 — Critic 循环控制流
│   ├── test_storyboarder_agent.py  # 7 项 — 视觉节奏校验
│   ├── test_orchestrator.py        # 4 项 — 状态机 + EventBus
│   └── test_middleware.py          # 5 项 — TokenTracker
├── integration/
│   └── test_pipeline_e2e.py        # 2 项 — 全流水线 mock 集成
└── conftest.py                     # MockLLMAdapter + MockImageAdapter
```

### 6. 前端 Pipeline 控制台

`/pipeline` 页面——在浏览器中直接驱动整个 Agent 流水线：

- 输入故事前提 + 页数，一键启动
- 7 步 Agent 链路可视化进度条
- SSE 实时事件流滚动显示
- 成本仪表盘：LLM 调用次数、Token 总量、预估费用、总耗时

---

## 架构与数据流

```text
                         ┌──────────────────────────────────────────┐
                         │           PipelineOrchestrator           │
                         │     (State Machine + EventBus + CP)      │
                         └──┬────────┬────────┬────────┬───────┬───┘
                            │        │        │        │       │
                         ┌──▼──┐  ┌──▼──┐  ┌──▼──┐ ┌──▼──┐ ┌──▼──┐
                         │Write│  │Story│  │Prompt│ │Image│ │QualR│
                         │Agent│  │board│  │Direc│ │Adapt│ │eview│
                         └──┬──┘  └──┬──┘  └──┬──┘ └──┬──┘ └──┬──┘
                            │        │        │        │       │
                    ┌───────▼────────▼────────▼────────▼───────▼───┐
                    │              BaseLLMAdapter                   │
                    │        (TrackedLLMAdapter wrapper)            │
                    │    Gemini  │  OpenAI  │  Mock (testing)       │
                    └──────────────────────────────────────────────┘
                                        │
                    ┌───────────────────▼───────────────────────────┐
                    │                FastAPI Server                  │
                    │   SSE /pipeline/run  │  /panel/rerender       │
                    └───────────────────┬───────────────────────────┘
                                        │
                    ┌───────────────────▼───────────────────────────┐
                    │          Next.js 14 Frontend                  │
                    │   Pipeline Console  │  Comic Viewer/Editor    │
                    └──────────────────────────────────────────────┘
```

---

## 项目结构

```text
MangaZine/
├── orchestrator/               # 编排引擎（v0.3 新增）
│   ├── pipeline.py             #   状态机 + PipelineOrchestrator
│   ├── events.py               #   EventBus + PipelineEvent
│   ├── messages.py             #   AgentMessage 通信协议
│   ├── checkpoint.py           #   断点保存/恢复
│   └── tracing.py              #   OpenTelemetry 集成
├── agents/
│   ├── writer_agent.py         #   WriterAgent（Critic 自审循环）
│   ├── storyboarder_agent.py   #   StoryboarderAgent（节奏校验）
│   ├── prompt_director_agent.py#   PromptDirectorAgent（确定性）
│   └── quality_reviewer_agent.py#  QualityReviewerAgent（v0.3 新增）
├── adapters/
│   ├── base.py                 #   BaseLLMAdapter / BaseImageAdapter
│   ├── factory.py              #   适配器工厂
│   ├── middleware.py           #   TokenTracker（v0.3 新增）
│   ├── gemini_llm.py / gemini_image.py
│   ├── openai_llm.py / openai_image.py
│   └── seedream_image.py
├── server/                     # FastAPI 后端（v0.3 新增）
│   ├── main.py                 #   /api/v1/* 端点
│   └── schemas.py              #   API 请求/响应模型
├── tests/                      # 自动化测试（v0.3 新增）
│   ├── unit/                   #   5 个测试模块
│   ├── integration/            #   E2E mock 测试
│   └── conftest.py             #   共享 fixtures
├── app/                        # Next.js 14 前端
│   ├── page.tsx                #   首页 + 项目查看器
│   └── pipeline/page.tsx       #   Pipeline 控制台（v0.3 新增）
├── cli/run_pipeline.py         # CLI 入口（v0.3 重写）
├── .github/workflows/ci.yml   # GitHub Actions CI
├── Dockerfile                  # 多阶段构建
├── docker-compose.yml          # 一键部署
└── CHANGELOG.md                # 更新日志
```

---

## 快速开始

### 1. 安装依赖

```bash
git clone git@github.com:HeroBlast10/MangaZine.git
cd MangaZine

pip install -r requirements.txt
npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

```env
LLM_PROVIDER=gemini          # 或 openai
IMAGE_PROVIDER=gemini         # 或 openai / seedream
GOOGLE_API_KEY=your-key
```

### 3. CLI 生成

```bash
# 单页
python cli/run_pipeline.py "赛博朋克大厨用激光锅铲对决美食评论家"

# 15 页完整话
python cli/run_pipeline.py "发福的退休杀手开了一家便利店" --pages 15

# 续写第 2 话
python cli/run_pipeline.py "第2话：神秘顾客登场" \
  --continue-from output/.../project_final.json --pages 18
```

### 4. 启动 FastAPI 后端（可选）

```bash
uvicorn server.main:app --reload --port 8000
```

### 5. 启动前端

```bash
npm run dev
```

打开 `http://localhost:3000`，载入项目或前往 `/pipeline` 启动在线生成。

### 6. Docker 一键部署

```bash
docker-compose up --build
```

### 7. 运行测试

```bash
python -m pytest tests/ -v
```

---

## 技术栈

| 层级 | 技术 |
|---|---|
| 编排引擎 | 有限状态机 + EventBus + Checkpoint |
| Agent 层 | WriterAgent / StoryboarderAgent / PromptDirectorAgent / QualityReviewerAgent |
| 后端 | Python 3.11+, FastAPI, Pydantic v2, SSE |
| 前端 | Next.js 14 (App Router), React 18, Tailwind CSS, Zustand |
| 可观测性 | TokenTracker, AgentMessage Protocol, OpenTelemetry |
| 图像接入 | Gemini / OpenAI / Seedream 适配器层 |
| 测试 | Pytest + MockLLMAdapter + MockImageAdapter (35 tests) |
| CI/CD | GitHub Actions + Docker Compose |

---

## Roadmap

- [x] v0.1：核心 CLI 流水线 + 基础前端编辑器
- [x] v0.2：多页生成 + 多话连续性 + 16 种布局模板
- [x] **v0.3：Agent 编排引擎 + 可观测性 + FastAPI + QualityReviewer + 测试 + CI/CD + Pipeline 控制台**
- [ ] v0.4：StylePack 可视化编辑器
- [ ] v0.5：嵌字 / PDF / 条漫导出
- [ ] v0.6：多 Agent 并行调度 + DAG 编排

---

## 开源协议

本项目基于 [MIT License](./LICENSE) 开源。
