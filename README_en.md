# MangaZine 🖋️

> **Comics are productions, not prompts.**  
> The open-source, multi-agent framework and non-destructive editor for AI manga creation.  
> **Now supports multi-page generation, variable panel layouts, and serialized episodes.**

**[中文 README →](./README.md)**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-e92063)](https://docs.pydantic.dev/latest/)

---

MangaZine is **not** another "text-to-image" wrapper.

It is a **multi-agent runtime + non-destructive editor** built to transform manga creation into a structured, controllable, and traceable production pipeline. Our audience is **creators with great ideas and storyboard instincts who are constrained by their drawing ability** — novelists, screenwriters, tabletop RPG players, and anyone with a story in their head and no way to put it on a page.

> 🎯 **MangaZine gives every storyteller a complete manga studio in their browser.**

We believe: **human control is a feature, not a fallback.**

---

## 💡 Core Philosophy

**1. Comics are productions, not prompts**  
A comic is a continuous production process — character design, narrative pacing, storyboarding, dialogue, and revision. A single prompt cannot produce a comic.

**2. Specialised agents, not one model for everything**  
The Writer Agent handles story. The Storyboarder Agent handles rhythm. The Prompt Director synthesises visuals. Every agent has a clear responsibility boundary and typed output contract.

**3. Structured state over raw strings**  
Every intermediate artefact (Character Bible, Page Specs, Panel Prompts) is persisted as strictly-typed JSON. No black-box generation. Full version history. Deterministic reproducibility.

**4. Open, pluggable infrastructure**  
MangaZine is designed as infrastructure — pluggable models, style packs, and workflow nodes.

---

## ✨ Key Features

### 📖 Multi-Page & Multi-Episode Production (v0.2 NEW)
- **Variable page count**: 1-20 pages per episode via `--pages N` parameter
- **16 layout templates**: 3-8 panels per page, auto-selected optimal layouts (splash, grid, L-shape, cross, etc.)
- **Episode continuity**: Chain episodes with `--continue-from`, auto-inherit CharacterBible and StylePack
- **Story memory**: Auto-inject summaries from previous 3 episodes for narrative consistency
- **Isolated output**: Each project creates timestamped folders to prevent overwriting

### 🎭 Multi-Agent Orchestration Pipeline
| Agent | Responsibility |
|---|---|
| **WriterAgent** | Generates Character Bible, Episode Outline, and Dialogue Draft. Built-in **Critic sub-routine** automatically reviews narrative pacing and triggers revision loops. |
| **StoryboarderAgent** | Converts the script into page layouts and panel specs. Supports variable panel counts and dynamic layout selection. |
| **PromptDirectorAgent** | Deterministically synthesises the final image-generation prompt. Injects character visual descriptions and appends StylePack keywords in a strict, reproducible order. |

### 🧬 Style DNA System
Define art styles through deterministic numeric parameters (line weight, contrast, screentone density, panel regularity) rather than copyrighted artist names. The parameters translate to natural-language prompt modifiers automatically.

### 🛠️ Non-Destructive Editing
- **Page-level & Panel-level** independent re-rendering
- **Character-lock rerender**: keep character appearance, change pose or expression
- **Composition-lock rerender**: keep the panel grid, change the camera angle
- **Revision history**: every rerender snapshots the previous `RenderOutput` into `revision_history` before overwriting — always rollback-able

### 🗂️ Multi-Backend Model Support (BYOK)
Supports multiple LLM and image generation backends:

**LLM Providers:**
- **Gemini** (default): `gemini-3.1-pro-preview`
- **OpenAI**: `gpt-4o`

**Image Generation Providers:**
- **Gemini** (default): `gemini-3.1-flash-image-preview` (draft) / `gemini-3-pro-image-preview` (final)
- **OpenAI**: `dall-e-3`
- **Seedream** (Bytedance Doubao): `seedream-v1`

Switch providers via `LLM_PROVIDER` and `IMAGE_PROVIDER` in `.env` file

---

## 🏗️ Architecture & Data Flow

```
Idea
  │
  ▼
Story Bible              ← CharacterBible + StylePack
  │                         (Multi-episode reuse: --continue-from)
  ▼
Episode Outline          ← WriterAgent + Story memory injection
  │                         (Supports 1-20 pages/episode)
  ▼
Dialogue Draft           ← WriterAgent
  │
  ▼
Multi-Page Specs         ← StoryboarderAgent + 16 layout templates
  │                         (3-8 panels/page, dynamic selection)
  ▼
Panel Prompts            ← PromptDirectorAgent (deterministic synthesis)
  │
  ▼
Renders                  ← ImageAdapter → Gemini / OpenAI / Seedream
  │                         (Organized by page: page_01/panel_0.png)
  ▼
Typesetting → PDF / Webtoon Export   ← [Planned]
```

Every artefact is persisted as **Pydantic V2** strictly-typed JSON — pauseable, inspectable, editable, and resumable at any stage.

---

## 📁 Project Structure

```
MangaZine/
├── models/
│   ├── schemas.py                # Core domain models (Pydantic V2)
│   └── layouts.py                # 16 layout template configs (CSS Grid)
├── agents/
│   ├── writer_agent.py           # WriterAgent + Critic sub-routine
│   ├── storyboarder_agent.py     # StoryboarderAgent + rhythm validation
│   └── prompt_director_agent.py  # Deterministic prompt synthesis
├── adapters/
│   ├── base.py                   # Abstract base interfaces
│   ├── factory.py                # Adapter factory
│   ├── gemini_llm.py             # Gemini LLM adapter
│   ├── gemini_image.py           # Gemini image adapter
│   ├── openai_llm.py             # OpenAI LLM adapter
│   ├── openai_image.py           # OpenAI DALL-E adapter
│   └── seedream_image.py         # Seedream image adapter
├── components/                   # Next.js React components
│   ├── ComicCanvas.tsx           # Variable layout page renderer
│   ├── MultiPageViewer.tsx       # Multi-page navigation component
│   └── PanelEditorSidebar.tsx    # Non-destructive editor sidebar
├── lib/
│   └── layoutConfigs.ts          # Frontend layout configs
├── store/
│   └── comicStore.ts             # Zustand global state
├── types/
│   └── comic.ts                  # TypeScript type definitions
├── config.py                     # Multi-backend config management
└── cli/
    └── run_pipeline.py           # CLI multi-page multi-episode pipeline
```

---

## 🚀 Getting Started

> ⚠️ MangaZine is in active development. v0.2 now supports multi-page and multi-episode serialized production.

```bash
# Clone the repo
git clone git@github.com:HeroBlast10/MangaZine.git
cd MangaZine

# Install backend dependencies
pip install -r requirements.txt

# Configure API Key (one-time setup)
# 1. Copy the .env template file
cp .env.example .env

# 2. Edit .env and configure backend providers
#    Supported LLM: gemini (default), openai
#    Supported Image: gemini (default), openai, seedream
#    Example:
#      LLM_PROVIDER=gemini
#      IMAGE_PROVIDER=gemini
#      GOOGLE_API_KEY=your-actual-key

# 3. Add API keys for your chosen providers
#    - Google AI Studio: https://aistudio.google.com/app/apikey
#    - OpenAI: https://platform.openai.com/api-keys
#    - Seedream (Bytedance Doubao): https://console.volcengine.com/ark

# Run the CLI pipeline (generates multi-page manga)
# Each run creates a unique timestamped folder to avoid overwriting

# Generate single-page comic (default)
python cli/run_pipeline.py "A cyberpunk chef fights food critics with a laser spatula"

# Generate 15-page manga (Episode 1)
python cli/run_pipeline.py "A retired assassin opens a convenience store" --pages 15

# Continue with Episode 2 (auto-inherit characters and style)
python cli/run_pipeline.py "Episode 2: A mysterious customer arrives" --continue-from output/20250322_090000_A_retired_assassin/project_final.json --pages 18

# Install frontend dependencies and start the dev server
npm install
npm run dev
```

**Pipeline output (multi-page mode):**
```
output/20250322_090000_A_retired_assassin/
├── project_final.json           # Full project state (resumable at any time)
├── images/
│   ├── page_01/                 # Page 1
│   │   ├── panel_0.png
│   │   ├── panel_1.png
│   │   ├── panel_2.png
│   │   └── panel_3.png
│   ├── page_02/                 # Page 2
│   │   ├── panel_0.png
│   │   ├── panel_1.png
│   │   ├── panel_2.png
│   │   ├── panel_3.png
│   │   └── panel_4.png          # Variable panel count
│   └── ...
└── checkpoints/
    ├── 01_character_bible.json  # Character settings (reused across episodes)
    ├── 02_episode_outline.json  # Episode outline
    └── 03_page_specs.json       # All page specifications
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic V2 |
| AI SDK | Google GenAI SDK |
| Frontend | Next.js 14 (App Router), React, Tailwind CSS, Zustand |
| State | Zustand + Immer (frontend) / Pydantic JSON (backend) |

---

## 🗺️ Roadmap

- [x] v0.1: Core CLI pipeline + basic frontend editor
- [x] v0.2: Multi-page generation + multi-episode continuity + 16 layout templates
- [ ] v0.3: FastAPI backend + `/api/rerender-panel` endpoint
- [ ] v0.4: Custom StylePack editor UI
- [ ] v0.5: Multi-page frontend editor + episode export
- [ ] v1.0: PDF / webtoon export + Typesetting Agent

---

## 🤝 Contributing

Issues and Pull Requests are welcome. Before contributing code, please read the core philosophy — especially the **structured state over raw strings** principle. Every new feature should have a typed Pydantic model as its input and output contract.

---

## 📄 License

This project is open-source under the [MIT License](./LICENSE).
