# MangaZine 🖋️

> **Comics are production systems, not single prompts.**  
> An open-source multi-agent framework and browser editor for AI manga creation.  
> **Now supports multi-page generation, serialized episodes, panel rerendering, and local image preview.**

**[中文 README →](./README.md)**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-e92063)](https://docs.pydantic.dev/latest/)

---

MangaZine is **not** another text-to-image wrapper.

It is built around a different idea: manga creation should be a traceable production pipeline. Character design, style DNA, episode memory, page layouts, panel prompts, rerendering, and revision history should all live in a structured project model instead of disappearing into one-off prompts.

> 🎯 **MangaZine aims to give every storyteller a browser-based manga studio that actually works like a studio.**

---

## 💡 Core Philosophy

**1. Comics are production pipelines, not prompt lotteries**  
Real comic work is iterative. Character consistency, page rhythm, dialogue, visual composition, and revision all matter. The system is designed to expose and preserve those steps.

**2. Specialised agents beat one giant “do everything” model**  
The Writer handles story and dialogue. The Storyboarder handles pacing and layouts. The Prompt Director turns structured state into deterministic image prompts.

**3. Structured state beats raw text blobs**  
`CharacterBible`, `StylePack`, `EpisodeOutline`, `PageSpec`, and `PanelSpec` are stored as typed JSON so the project can be resumed, inspected, edited, and rerendered safely.

**4. Non-destructive editing matters more than one-shot generation**  
The first image is only a draft. The editor should support local rerenders, best-effort preserve controls, and revision history without destroying the rest of the project.

---

## ✨ Current Capabilities

### 📖 Multi-Page, Multi-Episode Production
- Generate 1 to 20 pages with `--pages N`
- Continue later episodes with `--continue-from`
- Reuse character and style state across episodes
- Inject summaries from previous episodes to preserve story continuity
- Write each run into its own timestamped output directory

### 🧠 Multi-Agent Production Pipeline
| Agent | Responsibility |
|---|---|
| **WriterAgent** | Builds the Character Bible, episode outline, and dialogue draft, then reviews narrative pacing through a Critic sub-flow |
| **StoryboarderAgent** | Expands the story into pages and panels, selecting layout templates automatically |
| **PromptDirectorAgent** | Combines `PanelSpec + CharacterBible + StylePack` into deterministic image prompts |

### 🧬 Style DNA System
`StylePack` encodes style with numeric and categorical controls such as line weight, contrast, screentone density, panel regularity, speed-line intensity, background detail, palette, and tone keywords. The point is to define style behavior, not to imitate a named artist.

### 🛠️ Browser Editor and Non-Destructive Rerendering
- Load an existing `project_final.json` directly in the homepage
- Switch episodes, switch pages, use grid view, and flip pages with keyboard arrows
- Click a panel to open a sidebar with scene info, dialogue, prompt plan, and revision history
- Rerender a single panel with full `style_pack`, `character_bible`, and lock constraints
- “Preserve character / style / composition / dialogue” is implemented as a prompt-level best effort, not pixel-level image editing
- Every rerender snapshots the previous `RenderOutput` into `revision_history`

### 🖼️ Local Image Preview
- The CLI stores generated file paths in `generation_params.local_image_path`
- The frontend prefers `render_output.image_url`
- If `image_url` is missing but a local path exists, the UI resolves it through `/api/project-image`
- `GET /api/project-image` only serves files inside `output/` and rejects path traversal, absolute paths, and non-image suffixes

### 🔌 Multi-Backend Adapter Layer (BYOK)
**LLM:**
- Gemini
- OpenAI

**Image:**
- `adapters/gemini_image.py`
- `adapters/openai_image.py`
- `adapters/seedream_image.py`

These adapter modules translate a shared internal contract (`prompt + StylePack + aspect_ratio + reference images`) into provider-specific API requests, then normalize the results back into `GeneratedImageResult`. That keeps the rest of the pipeline provider-agnostic.

---

## 🏗️ Architecture & Data Flow

```text
Idea
  ↓
CharacterBible + StylePack
  ↓
WriterAgent
  ↓
EpisodeOutline + Dialogue Draft
  ↓
StoryboarderAgent
  ↓
PageSpec / PanelSpec
  ↓
PromptDirectorAgent
  ↓
ImageAdapter (Gemini / OpenAI / Seedream)
  ↓
output/project_final.json + output/images/*
  ↓
Next.js Editor
  ├─ GET /api/project-image      serves local files from output/
  └─ POST /api/rerender-panel    calls python -m cli.rerender_panel
```

---

## 📁 Project Structure

```text
MangaZine/
├── agents/
│   ├── prompt_director_agent.py
│   ├── storyboarder_agent.py
│   └── writer_agent.py
├── adapters/
│   ├── base.py
│   ├── factory.py
│   ├── gemini_image.py
│   ├── gemini_llm.py
│   ├── openai_image.py
│   ├── openai_llm.py
│   └── seedream_image.py
├── app/
│   ├── api/
│   │   ├── project-image/route.ts
│   │   └── rerender-panel/route.ts
│   ├── layout.tsx
│   └── page.tsx
├── cli/
│   ├── image_paths.py
│   ├── rerender_panel.py
│   └── run_pipeline.py
├── components/
│   ├── ComicCanvas.tsx
│   ├── MultiPageViewer.tsx
│   └── PanelEditorSidebar.tsx
├── lib/
│   ├── layoutConfigs.ts
│   ├── projectImageServer.ts
│   └── projectImageUrl.ts
├── models/
│   ├── layouts.py
│   └── schemas.py
├── store/
│   └── comicStore.ts
├── types/
│   └── comic.ts
├── config.py
├── next.config.js
└── package.json
```

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
git clone git@github.com:HeroBlast10/MangaZine.git
cd MangaZine

pip install -r requirements.txt
npm install
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Set the providers you want in `.env`:

```env
LLM_PROVIDER=gemini
IMAGE_PROVIDER=gemini
GOOGLE_API_KEY=your-key
OPENAI_API_KEY=
SEEDREAM_API_KEY=
```

Optional:

```env
# The Next.js rerender route uses `python` by default.
# Override this if your local environment requires a specific interpreter.
PYTHON_EXECUTABLE=python
```

### 3. Run the CLI Pipeline

```bash
# Default: single-page project
python cli/run_pipeline.py "A cyberpunk chef fights food critics with a laser spatula"

# Generate a 15-page Episode 1
python cli/run_pipeline.py "A retired assassin opens a convenience store" --pages 15

# Continue from an existing project
python cli/run_pipeline.py "Episode 2: A mysterious customer arrives" --continue-from output/20250322_090000_A_retired_assassin/project_final.json --pages 18
```

### 4. Start the Browser Editor

```bash
npm run dev
```

Then open `http://localhost:3000` and:

1. Load `output/.../project_final.json`
2. Switch episodes and pages
3. Click a panel to open the editor sidebar
4. Adjust the temporary prompt or preserve controls
5. Click “Rerender Current Panel”

---

## 📦 Output Layout

```text
output/20260326_153000_example_project/
├── project_final.json
├── images/
│   ├── page_01/
│   │   ├── panel_0.png
│   │   ├── panel_1.png
│   │   └── ...
│   └── page_02/
├── rerenders/
│   └── <page_id>/
│       └── <panel_id>/
│           └── 20260326T153522.png
└── checkpoints/
    ├── 01_character_bible.json
    ├── 02_episode_outline.json
    └── 03_page_specs.json
```

`project_final.json` is the resumable project state. `images/` contains the initial pipeline renders. `rerenders/` stores panel-level revisions created from the frontend editor.

---

## ✅ Quality Checks

```bash
npm run type-check
npm run lint
npm run build
python -m compileall adapters agents cli models config.py
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, Pydantic v2, local Python route bridge |
| Frontend | Next.js 14 (App Router), React, Tailwind CSS |
| State | Zustand + Immer |
| Image Integration | Gemini / OpenAI / Seedream adapter layer |
| Project Model | `CharacterBible` / `StylePack` / `PageSpec` / `RenderOutput` |

---

## 🗺️ Roadmap

- [x] v0.1: Core CLI pipeline + basic frontend editor
- [x] v0.2: Multi-page generation + multi-episode continuity + 16 layout templates
- [x] Local image preview + panel rerender route
- [ ] Visual StylePack editor
- [ ] Typesetting / PDF / webtoon export
- [ ] Richer review workflow

---

## 📄 License

This project is open-source under the [MIT License](./LICENSE).
