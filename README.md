# MangaZine 🖋️

> **漫画是工程体系，而非单纯的提示词。**  
> 专为 AI 漫画创作打造的开源多智能体框架与非破坏性编辑器。

**[English README →](./README_en.md)**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-e92063)](https://docs.pydantic.dev/latest/)

---

MangaZine **绝不是**又一个简单的"文生图"套壳工具。

它是一个 **多智能体运行环境（Multi-Agent Runtime）+ 非破坏性编辑器**，旨在将漫画创作转化为一条结构化、可控、可追溯的工业级生产流水线。我们的目标受众是**有绝佳脑洞、懂分镜，却受限于手绘能力的创作者**——网文作者、剧本家、跑团玩家，以及每一个脑子里有个故事却苦于无从落笔的人。

> 🎯 **MangaZine 让每个有故事的人，都能拥有一个浏览器里的漫画工作室。**

我们坚信：**人类的精确控制是核心特性，而非技术降级。**

---

## 💡 核心理念

**1. 漫画是工程体系，而非提示词**  
漫画的本质是连续生产过程——角色设定、故事节奏、分镜排版、对白修稿，环环相扣。一句提示词生不出一本漫画。

**2. 多智能体各司其职，而非一个模型包打天下**  
编剧 Agent 负责故事，分镜 Agent 负责节奏，提示词导演负责画面合成。每个 Agent 都有明确的职责边界与输出契约。

**3. 结构化状态优先于纯文本**  
所有中间产物（设定集、页面规格、单格提示词）均以严格类型的 JSON 结构固化，告别"盲盒式"抽卡，支持完整的版本回溯与确定性复现。

**4. 开放的创作基础设施**  
MangaZine 定位为可插拔的基础设施，支持多模型接入、多风格拓展，以及自定义工作流节点。

---

## ✨ 核心特性

### 🎭 多智能体协作流水线
| Agent | 职责 |
|---|---|
| **WriterAgent（编剧）** | 生成角色圣经、分话大纲、对白草稿；内置 Critic 副程序自动检查叙事节奏 |
| **StoryboarderAgent（分镜师）** | 将剧本转化为页面布局与分格规格；强制执行视觉节奏规则（每页最多 1 个远景/全景） |
| **PromptDirectorAgent（提示词导演）** | 确定性地合成最终图像生成提示词，自动注入角色视觉描述与风格关键词 |

### 🧬 风格基因系统（Style DNA）
通过数值参数（线条粗细、黑白对比、网点密度、分格规律性等）精确定义画风，彻底规避版权风险，拒绝直接使用漫画家名字作为提示词。

### 🛠️ 非破坏性单格修稿
- **单页级 / 单格级**独立重绘，不影响其他页面
- **锁定角色**：保持角色外观不变，仅修改动作或表情
- **锁定构图**：保持分格网格不变，仅调整镜头语言（如将全景改为特写）
- **修订历史**：每次重绘前自动将旧版本快照存入 `revision_history`，随时可回滚

### 🗂️ 模型接入（BYOK）
原生对接 Google GenAI SDK：
- **文本 / 逻辑**：`gemini-3.1-pro-preview`
- **草稿图像**：`gemini-3.1-flash-image-preview`（Nano Banana 2）
- **终稿图像**：`gemini-3-pro-image-preview`（Nano Banana Pro）

---

## 🏗️ 架构与数据流

```
灵感 (Idea)
  │
  ▼
设定集 (Story Bible)         ← CharacterBible + StylePack
  │
  ▼
分话大纲 (Episode Outline)   ← WriterAgent + Critic 审核
  │
  ▼
对白草稿 (Dialogue Draft)    ← WriterAgent
  │
  ▼
页面规格 (Page Specs)        ← StoryboarderAgent + 视觉节奏校验
  │
  ▼
单格提示词 (Panel Prompts)   ← PromptDirectorAgent（确定性合成）
  │
  ▼
图像渲染 (Renders)           ← ImageAdapter → Nano Banana 2 / Pro
  │
  ▼
嵌字排版 → PDF / 条漫导出   ← [规划中]
```

所有中间产物均以 **Pydantic V2** 严格类型的 JSON 格式持久化，可随时暂停、检查、修改并继续。

---

## 📁 项目结构

```
MangaZine/
├── models/
│   └── schemas.py            # 核心领域模型（Pydantic V2）
├── agents/
│   ├── writer_agent.py       # 编剧 Agent + Critic 副程序
│   ├── storyboarder_agent.py # 分镜 Agent + 视觉节奏校验
│   └── prompt_director_agent.py  # 确定性提示词合成
├── adapters/
│   ├── llm_adapter.py        # Google GenAI 文本适配器
│   └── image_adapter.py      # Google GenAI 图像适配器
├── components/               # Next.js React 组件
│   ├── ComicCanvas.tsx       # CSS Grid 页面渲染器
│   └── PanelEditorSidebar.tsx  # 非破坏性编辑侧栏
├── store/
│   └── comicStore.ts         # Zustand 全局状态管理
├── types/
│   └── comic.ts              # TypeScript 类型定义
└── cli/
    └── run_pipeline.py       # 命令行完整流水线入口
```

---

## 🚀 快速开始

> ⚠️ MangaZine 目前处于高强度开发阶段，v0.1 版本的完整运行指南敬请期待。

```bash
# 克隆仓库
git clone git@github.com:HeroBlast10/MangaZine.git
cd MangaZine

# 安装后端依赖
pip install -r requirements.txt

# 配置 API Key（一次性设置）
# 1. 复制 .env 模板文件
copy .env.example .env
# 2. 编辑 .env 文件，填入你的 Google API Key
# GOOGLE_API_KEY=your-actual-api-key-here
# 获取 API Key: https://aistudio.google.com/app/apikey

# 运行 CLI 流水线（从一句话生成单页漫画）
python cli/run_pipeline.py "赛博朋克大厨用激光锅铲对决美食评论家"

# 安装前端依赖并启动开发服务器
npm install
npm run dev
```

**流水线输出：**
```
output/
├── project_final.json           # 完整项目状态（可随时恢复）
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

## 🛠️ 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python 3.11+，FastAPI，Pydantic V2 |
| AI SDK | Google GenAI SDK |
| 前端 | Next.js 14（App Router），React，Tailwind CSS，Zustand |
| 状态管理 | Zustand + Immer（前端） / Pydantic JSON（后端） |

---

## 📄 开源协议

本项目基于 [MIT License](./LICENSE) 开源。
