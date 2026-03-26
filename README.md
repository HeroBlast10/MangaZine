# MangaZine 🖋️

> **漫画是工程体系，而不是一句提示词。**  
> 面向 AI 漫画创作的开源多智能体框架与浏览器编辑器。  
> **现已支持多页生成、多话连续创作、单格重生成与本地图片直连预览。**

**[English README →](./README_en.md)**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-e92063)](https://docs.pydantic.dev/latest/)

---

MangaZine **不是**又一个“文生图”壳子。

它的目标，是把漫画创作拆成一条可检查、可回放、可迭代的生产链：先有角色设定、风格 DNA、剧情节奏和页面布局，再落到单格提示词与图像生成，最后回到浏览器里做面向项目状态的重生成和修订。

> 🎯 **MangaZine 想给每个有故事的人，一个真正能工作的漫画工作室。**

---

## 💡 核心理念

**1. 漫画是生产流程，不是抽卡提示词**  
角色、分镜、对白、风格、返工，本质上是一条连续的工程链。MangaZine 的设计重点，是让这条链路可追踪，而不是让用户不断重写提示词碰运气。

**2. 多智能体分工，而不是单模型包打天下**  
Writer 负责故事和对白，Storyboarder 负责页面节奏和布局，Prompt Director 负责把结构化状态转成稳定的图像提示词。

**3. 结构化状态优先于自由文本**  
`CharacterBible`、`StylePack`、`EpisodeOutline`、`PageSpec`、`PanelSpec` 都会固化成强类型 JSON，中间态可以保存、恢复、检查和继续编辑。

**4. 非破坏式编辑优先于一次性生成**  
生成不是终点。项目应当支持重新载入、局部重生成、尽量保持角色或风格，并保留修订历史。

---

## ✨ 当前能力

### 📖 多页、多话连载制作
- 支持 `--pages N` 生成 1 到 20 页
- 支持 `--continue-from` 继承上一个项目的角色与风格，继续创作后续话数
- 自动注入前几话摘要，保持连续性
- 每次运行创建独立输出目录，避免覆盖

### 🧠 多智能体流水线
| Agent | 职责 |
|---|---|
| **WriterAgent** | 生成角色圣经、话数大纲、对白草稿，并通过 Critic 子流程检查叙事节奏 |
| **StoryboarderAgent** | 将剧情拆成多页分镜，自动选择布局模板，产出页面与 panel 规格 |
| **PromptDirectorAgent** | 将 `PanelSpec + CharacterBible + StylePack` 合成为稳定的最终提示词 |

### 🧬 风格 DNA 系统
`StylePack` 不依赖漫画家名字，而是使用线条粗细、对比度、网点密度、分格规律性、速度线强度、背景细节、色板和 tone keywords 等参数来定义风格语言。

### 🛠️ 浏览器编辑器与非破坏式重生成
- 首页可载入 `project_final.json`
- 支持 episode 切换、页码切换、网格视图与键盘左右翻页
- 点击 panel 打开侧栏，查看场景、角色、对白、提示词和修订历史
- 支持单格 rerender，且请求会携带 `style_pack`、`character_bible` 与锁定约束
- “尽量保持角色 / 风格 / 构图 / 对白” 仅作为提示词级约束，不承诺像素级硬锁定
- 每次 rerender 前会将旧的 `RenderOutput` 推入 `revision_history`

### 🖼️ 本地图片直连预览
- CLI 生成的图片会写入 `generation_params.local_image_path`
- 前端会优先使用 `render_output.image_url`
- 如果 `image_url` 为空，但存在本地路径，则自动通过 `/api/project-image` 读取 `output/` 子树里的图片
- `GET /api/project-image` 会拒绝绝对路径、`..` 穿越和非图片后缀

### 🔌 多后端适配器（BYOK）
**LLM：**
- Gemini
- OpenAI

**Image：**
- `adapters/gemini_image.py`
- `adapters/openai_image.py`
- `adapters/seedream_image.py`

这些适配器文件负责把统一的 `StylePack + prompt + aspect_ratio + reference images` 输入，翻译成各家图片模型能理解的请求，再把结果统一包装回 `GeneratedImageResult`，让上层流水线与前端无需关心具体供应商差异。

---

## 🏗️ 架构与数据流

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
  ├─ GET /api/project-image      读取 output/ 下的本地图片
  └─ POST /api/rerender-panel    调用 python -m cli.rerender_panel
```

---

## 📁 项目结构

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

## 🚀 快速开始

### 1. 安装依赖

```bash
git clone git@github.com:HeroBlast10/MangaZine.git
cd MangaZine

pip install -r requirements.txt
npm install
```

### 2. 配置环境变量

```bash
copy .env.example .env
```

在 `.env` 中配置：

```env
LLM_PROVIDER=gemini
IMAGE_PROVIDER=gemini
GOOGLE_API_KEY=your-key
OPENAI_API_KEY=
SEEDREAM_API_KEY=
```

可选项：

```env
# 前端 route 调用 Python 时默认使用 `python`
# 如果你的环境需要指定解释器，可覆盖它
PYTHON_EXECUTABLE=python
```

### 3. 运行 CLI 生成项目

```bash
# 默认生成单页项目
python cli/run_pipeline.py "赛博朋克大厨用激光锅铲对决美食评论家"

# 生成 15 页的第 1 话
python cli/run_pipeline.py "发福的退休杀手开了一家便利店" --pages 15

# 基于已有项目继续生成下一话
python cli/run_pipeline.py "第2话：神秘顾客登场" --continue-from output/20250322_090000_发福的退休杀手/project_final.json --pages 18
```

### 4. 启动前端编辑器

```bash
npm run dev
```

浏览器打开 `http://localhost:3000` 后：

1. 载入 `output/.../project_final.json`
2. 在首页切换不同 episode 和 page
3. 点击 panel 打开侧栏
4. 修改临时提示词或锁定选项
5. 点击“重新生成当前分镜”

---

## 📦 输出结构

```text
output/20260326_153000_示例项目/
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

`project_final.json` 是整个项目的恢复点；`images/` 是流水线初次生成结果；`rerenders/` 保存前端局部重生成产生的新版本。

---

## ✅ 质量检查

```bash
npm run type-check
npm run lint
npm run build
python -m compileall adapters agents cli models config.py
```

---

## 🛠️ 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python 3.11+、Pydantic v2、本地 Python route bridge |
| 前端 | Next.js 14（App Router）、React、Tailwind CSS |
| 状态管理 | Zustand + Immer |
| 图像接入 | Gemini / OpenAI / Seedream 适配器层 |
| 项目模型 | `CharacterBible` / `StylePack` / `PageSpec` / `RenderOutput` |

---

## 🗺️ Roadmap

- [x] v0.1：核心 CLI 流水线 + 基础前端编辑器
- [x] v0.2：多页生成 + 多话连续性 + 16 种布局模板
- [x] 本地图片直连预览 + 单格 rerender route
- [ ] StylePack 可视化编辑器
- [ ] 嵌字 / PDF / 条漫导出
- [ ] 更完整的审阅工作流

---

## 📄 开源协议

本项目基于 [MIT License](./LICENSE) 开源。
