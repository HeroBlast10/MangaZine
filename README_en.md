# MangaZine 🖋️

> **Comics are productions, not prompts.**  
> The open-source, multi-agent framework and non-destructive editor for AI manga creation.

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

### 🎭 Multi-Agent Orchestration Pipeline
| Agent | Responsibility |
|---|---|
| **WriterAgent** | Generates Character Bible, Episode Outline, and Dialogue Draft. Built-in **Critic sub-routine** automatically reviews narrative pacing and triggers revision loops. |
| **StoryboarderAgent** | Converts the script into page layouts and panel specs. Enforces the **visual rhythm constraint**: ≤1 wide/extreme-wide shot per page. Auto-corrects violations. |
| **PromptDirectorAgent** | Deterministically synthesises the final image-generation prompt. Injects character visual descriptions and appends StylePack keywords in a strict, reproducible order. |

### 🧬 Style DNA System
Define art styles through deterministic numeric parameters (line weight, contrast, screentone density, panel regularity) rather than copyrighted artist names. The parameters translate to natural-language prompt modifiers automatically.

### 🛠️ Non-Destructive Editing
- **Page-level & Panel-level** independent re-rendering
- **Character-lock rerender**: keep character appearance, change pose or expression
- **Composition-lock rerender**: keep the panel grid, change the camera angle
- **Revision history**: every rerender snapshots the previous `RenderOutput` into `revision_history` before overwriting — always rollback-able

### 🗂️ Bring Your Own Key (BYOK)
Native Google GenAI SDK integration:
- **Text / logic**: `gemini-3.1-pro-preview`
- **Draft images**: `gemini-3.1-flash-image-preview` (Nano Banana 2)
- **Final images**: `gemini-3-pro-image-preview` (Nano Banana Pro)

---

## 🏗️ Architecture & Data Flow

```
Idea
  │
  ▼
Story Bible              ← CharacterBible + StylePack
  │
  ▼
Episode Outline          ← WriterAgent + Critic review loop
  │
  ▼
Dialogue Draft           ← WriterAgent
  │
  ▼
Page Specs               ← StoryboarderAgent + visual rhythm validation
  │
  ▼
Panel Prompts            ← PromptDirectorAgent (deterministic synthesis)
  │
  ▼
Renders                  ← ImageAdapter → Nano Banana 2 / Pro
  │
  ▼
Typesetting → PDF / Webtoon Export   ← [Planned]
```

Every artefact is persisted as **Pydantic V2** strictly-typed JSON — pauseable, inspectable, editable, and resumable at any stage.

---

## 📁 Project Structure

```
MangaZine/
├── models/
│   └── schemas.py                # Core domain models (Pydantic V2)
├── agents/
│   ├── writer_agent.py           # WriterAgent + Critic sub-routine
│   ├── storyboarder_agent.py     # StoryboarderAgent + rhythm validation
│   └── prompt_director_agent.py  # Deterministic prompt synthesis
├── adapters/
│   ├── llm_adapter.py            # Google GenAI text adapter
│   └── image_adapter.py          # Google GenAI image adapter
├── components/                   # Next.js React components
│   ├── ComicCanvas.tsx           # CSS Grid page renderer
│   └── PanelEditorSidebar.tsx    # Non-destructive editor sidebar
├── store/
│   └── comicStore.ts             # Zustand global state
├── types/
│   └── comic.ts                  # TypeScript type definitions
└── cli/
    └── run_pipeline.py           # CLI full-pipeline entry point
```

---

## 🚀 Getting Started

> ⚠️ MangaZine is in active development. Full v0.1 instructions coming soon.

```bash
# Clone the repo
git clone git@github.com:HeroBlast10/MangaZine.git
cd MangaZine

# Install backend dependencies
pip install -r requirements.txt

# Configure API Key (one-time setup)
# 1. Copy the .env template file
cp .env.example .env
# 2. Edit .env and add your Google API Key
# GOOGLE_API_KEY=your-actual-api-key-here
# Get your API Key: https://aistudio.google.com/app/apikey

# Run the CLI pipeline (generates a single-page comic from a premise)
python cli/run_pipeline.py "A cyberpunk chef fights food critics with a laser spatula"

# Install frontend dependencies and start the dev server
npm install
npm run dev
```

**Pipeline output:**
```
output/
├── project_final.json           # Full project state (resumable at any time)
├── images/
│   ├── panel_0.png
│   ├── panel_1.png
│   ├── panel_2.png
│   └── panel_3.png
└── checkpoints/
    ├── 01_character_bible.json
    ├── 02_episode_outline.json
    └── 03_page_spec.json
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

- [ ] v0.1: Core CLI pipeline + basic frontend editor
- [ ] v0.2: FastAPI backend + `/api/rerender-panel` endpoint
- [ ] v0.3: Multi-page editor + episode export
- [ ] v0.4: Custom StylePack editor UI
- [ ] v1.0: PDF / webtoon export + Typesetting Agent

---

## 🤝 Contributing

Issues and Pull Requests are welcome. Before contributing code, please read the core philosophy — especially the **structured state over raw strings** principle. Every new feature should have a typed Pydantic model as its input and output contract.

---

## 📄 License

This project is open-source under the [MIT License](./LICENSE).
