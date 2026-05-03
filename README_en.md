<p align="center">
  <img src="https://img.shields.io/badge/MangaZine-v0.3.0-7C3AED?style=for-the-badge" alt="MangaZine" />
</p>

<h1 align="center">MangaZine</h1>

<p align="center">
  <strong>Production-Grade Multi-Agent Manga Creation System</strong><br/>
  Comics are engineering systems, not single prompts.
</p>

<p align="center">
  <a href="./README.md"><strong>中文 README →</strong></a>
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

## What Problem Does This Solve?

Every AI image tool today is a **single-image slot machine** — type a prompt, get one picture. But manga is not a collection of standalone images. It is an intricate engineering chain of **characters × style × narrative × storyboarding × composition × iteration**.

MangaZine decomposes this chain into **4 specialised agents + 1 orchestration engine**, making every step inspectable, recoverable, and iterable:

```
Premise → WriterAgent (characters / outline / dialogue / self-critique)
        → StoryboarderAgent (page layouts / visual rhythm validation)
        → PromptDirectorAgent (deterministic prompt synthesis)
        → ImageAdapter (multi-model rendering)
        → QualityReviewerAgent (Vision LLM quality gate + auto-retry)
```

> When an interviewer asks "how do your agents collaborate?", you can walk through the code line by line — because the architecture diagram in the README **matches the implementation exactly**.

---

## Key Highlights

### 1. State-Machine-Driven Agent Orchestrator

Not a 500-line `async` function. A real **finite state machine + event-driven** orchestration engine:

```python
PipelineState: INIT → STYLE_PACK → CHARACTER_BIBLE → EPISODE_OUTLINE
             → STORYBOARD → PROMPT_SYNTHESIS → IMAGE_GENERATION → ASSEMBLY → COMPLETED
```

- Each state transition calls the corresponding Agent's `.run()` method
- `EventBus` async pub-sub — the frontend consumes events in real time via SSE
- `CheckpointManager` saves after every step — supports resume from any checkpoint
- Agents are injected via `BaseLLMAdapter` interface — swap mock / Gemini / OpenAI in one line

### 2. Four Specialised Agents

| Agent | Responsibility | Key Capability |
|---|---|---|
| **WriterAgent** | Character bible, episode outline, dialogue draft | Critic self-review loop (up to 2 revision rounds), narrative pacing check |
| **StoryboarderAgent** | Multi-page layouts, template selection | Visual rhythm validation (limits wide-shot density), auto-correction |
| **PromptDirectorAgent** | PanelSpec + StylePack + CharacterBible → prompt | Fully deterministic, zero LLM calls, 100% unit-testable |
| **QualityReviewerAgent** | Post-generation Vision LLM assessment | 5-dimension scoring + auto prompt refinement + retry |

### 3. End-to-End Observability

```
Trace: pipeline_run_abc123
  ├─ Span: WriterAgent.character_bible     (2.3s, 1200 tokens, $0.0021)
  ├─ Span: WriterAgent.critic_review       (1.8s, 800 tokens, $0.0014)
  ├─ Span: StoryboarderAgent.page_1        (2.5s, 1600 tokens, $0.0028)
  ├─ Span: PromptDirectorAgent.synthesize  (0.01s, deterministic)
  └─ Span: ImageAdapter.render_panel_1     (8.2s)
```

- **TokenTracker**: Automatically records input/output token counts, latency, and estimated cost for every LLM call
- **AgentMessage protocol**: `trace_id` for end-to-end tracing + `parent_message_id` for causal chains
- **OpenTelemetry**: Export spans to Jaeger / Zipkin; graceful no-op fallback when the SDK is not installed

### 4. FastAPI Backend + SSE Streaming

Replaces the `child_process.spawn` workaround with a proper Python API server:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/pipeline/run` | SSE event stream — track every Agent step in real time |
| `POST /api/v1/panel/rerender` | Single-panel rerender |
| `GET /api/v1/projects` | List all projects |
| `GET /api/v1/project/{path}` | Retrieve a project |

### 5. 35 Automated Tests

```
tests/
├── unit/
│   ├── test_prompt_director.py     # 13 tests — deterministic logic, 100% coverage
│   ├── test_writer_agent.py        # 4 tests — Critic loop control flow
│   ├── test_storyboarder_agent.py  # 7 tests — visual rhythm validation
│   ├── test_orchestrator.py        # 4 tests — state machine + EventBus
│   └── test_middleware.py          # 5 tests — TokenTracker
├── integration/
│   └── test_pipeline_e2e.py        # 2 tests — full pipeline with mock adapters
└── conftest.py                     # MockLLMAdapter + MockImageAdapter
```

### 6. Frontend Pipeline Console

The `/pipeline` page drives the entire Agent pipeline from the browser:

- Enter a story premise + page count, hit "Start Pipeline"
- 7-step Agent chain visualisation with live progress indicators
- SSE real-time event log with colour-coded entries
- Cost dashboard: LLM calls, total tokens, estimated USD cost, total latency

---

## Architecture & Data Flow

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

## Project Structure

```text
MangaZine/
├── orchestrator/               # Orchestration engine (v0.3)
│   ├── pipeline.py             #   State machine + PipelineOrchestrator
│   ├── events.py               #   EventBus + PipelineEvent
│   ├── messages.py             #   AgentMessage protocol
│   ├── checkpoint.py           #   Checkpoint save / restore
│   └── tracing.py              #   OpenTelemetry integration
├── agents/
│   ├── writer_agent.py         #   WriterAgent (Critic self-review)
│   ├── storyboarder_agent.py   #   StoryboarderAgent (rhythm check)
│   ├── prompt_director_agent.py#   PromptDirectorAgent (deterministic)
│   └── quality_reviewer_agent.py#  QualityReviewerAgent (v0.3)
├── adapters/
│   ├── base.py                 #   BaseLLMAdapter / BaseImageAdapter
│   ├── factory.py              #   Adapter factory
│   ├── middleware.py           #   TokenTracker (v0.3)
│   ├── gemini_llm.py / gemini_image.py
│   ├── openai_llm.py / openai_image.py
│   └── seedream_image.py
├── server/                     # FastAPI backend (v0.3)
│   ├── main.py                 #   /api/v1/* endpoints
│   └── schemas.py              #   Request / response models
├── tests/                      # Test suite (v0.3)
│   ├── unit/                   #   5 test modules
│   ├── integration/            #   E2E mock tests
│   └── conftest.py             #   Shared fixtures
├── app/                        # Next.js 14 frontend
│   ├── page.tsx                #   Home + project viewer
│   └── pipeline/page.tsx       #   Pipeline console (v0.3)
├── cli/run_pipeline.py         # CLI entry point (v0.3 rewrite)
├── .github/workflows/ci.yml   # GitHub Actions CI
├── Dockerfile                  # Multi-stage build
├── docker-compose.yml          # One-command deployment
└── CHANGELOG.md                # Release notes
```

---

## Getting Started

### 1. Install Dependencies

```bash
git clone git@github.com:HeroBlast10/MangaZine.git
cd MangaZine

pip install -r requirements.txt
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
```

```env
LLM_PROVIDER=gemini          # or openai
IMAGE_PROVIDER=gemini         # or openai / seedream
GOOGLE_API_KEY=your-key
```

### 3. CLI Generation

```bash
# Single page
python cli/run_pipeline.py "A cyberpunk chef fights food critics with a laser spatula"

# 15-page episode
python cli/run_pipeline.py "A retired assassin opens a convenience store" --pages 15

# Continue episode 2
python cli/run_pipeline.py "Episode 2: A mysterious customer" \
  --continue-from output/.../project_final.json --pages 18
```

### 4. Start FastAPI Backend (optional)

```bash
uvicorn server.main:app --reload --port 8000
```

### 5. Start Frontend

```bash
npm run dev
```

Open `http://localhost:3000`, load a project or navigate to `/pipeline` to start online generation.

### 6. Docker Deployment

```bash
docker-compose up --build
```

### 7. Run Tests

```bash
python -m pytest tests/ -v
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | Finite State Machine + EventBus + Checkpoint |
| Agent Layer | WriterAgent / StoryboarderAgent / PromptDirectorAgent / QualityReviewerAgent |
| Backend | Python 3.11+, FastAPI, Pydantic v2, SSE |
| Frontend | Next.js 14 (App Router), React 18, Tailwind CSS, Zustand |
| Observability | TokenTracker, AgentMessage Protocol, OpenTelemetry |
| Image Providers | Gemini / OpenAI / Seedream adapter layer |
| Testing | Pytest + MockLLMAdapter + MockImageAdapter (35 tests) |
| CI/CD | GitHub Actions + Docker Compose |

---

## Roadmap

- [x] v0.1: Core CLI pipeline + basic frontend editor
- [x] v0.2: Multi-page generation + multi-episode continuity + 16 layout templates
- [x] **v0.3: Agent orchestrator + observability + FastAPI + QualityReviewer + tests + CI/CD + Pipeline console**
- [ ] v0.4: Visual StylePack editor
- [ ] v0.5: Typesetting / PDF / webtoon export
- [ ] v0.6: Parallel agent scheduling + DAG orchestration

---

## License

This project is open-source under the [MIT License](./LICENSE).
