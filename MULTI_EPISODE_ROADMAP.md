# 多话连载漫画制作路线图 / Multi-Episode Manga Production Roadmap

## 当前状态 / Current Status (v0.2)

✅ **已实现 / Implemented:**
- 单页漫画生产（4分格）
- 角色圣经持久化（CharacterBible）
- 风格系统（StylePack）
- 多后端支持（Gemini, OpenAI, Seedream）
- 独立项目文件夹（时间戳命名）
- **多页漫画生成（1话 = 1-20页）** ✨ NEW
- **可变分格布局（每页3-8个panel，16种布局模板）** ✨ NEW
- **多话剧情连续性（--continue-from 参数）** ✨ NEW
- **话与话之间的状态复用（CharacterBible + StylePack 继承）** ✨ NEW
- **剧情记忆注入（前3话摘要自动注入）** ✨ NEW

🎉 **所有核心功能已实现！**

---

## 日式漫画制作需求 / Japanese Manga Production Requirements

### 标准结构 / Standard Structure
```
Series (系列)
├── Episode 1 (第1话)
│   ├── Page 1 (页1) → 3-7 panels (可变分格)
│   ├── Page 2 (页2) → 4-6 panels
│   ├── ...
│   └── Page 15 (页15) → 扉页/结尾
├── Episode 2 (第2话)
│   ├── Page 1-18
│   └── ...
└── Episode N
```

### 核心挑战 / Core Challenges

1. **EpisodeOutline → 多页映射 / Multi-Page Mapping**
   - 当前: 1 scene = 1 page (固定4格)
   - 需要: 1 scene = 多页, 每页不同panel数量
   - 解决方案: StoryboarderAgent 需要生成 `List[PageSpec]` 而非单个 `PageSpec`

2. **可变分格布局 / Variable Panel Layouts**
   - 当前: 2x2 CSS Grid (固定)
   - 需要: 灵活布局 (3格, 5格, 7格, etc.)
   - 解决方案: PageSpec 需要包含 `layout_template` 字段
   
   ```python
   class PageSpec(BaseModel):
       page_number: int
       layout_template: LayoutTemplate  # NEW: "manga_3panel", "manga_5panel_L", etc.
       panels: List[PanelSpec]
   ```

3. **话间连续性 / Episode Continuity**
   - 当前: 每次运行独立生成
   - 需要: Episode 2 复用 Episode 1 的 CharacterBible
   - 解决方案: `--continue-from` 参数加载前一话的项目状态
   
   ```bash
   # Episode 1
   python cli/run_pipeline.py "故事前提" --pages 15
   
   # Episode 2 (复用角色和设定)
   python cli/run_pipeline.py "第2话剧情" --continue-from output/ep1/project.json --pages 18
   ```

---

## 实现路线图 / Implementation Roadmap

### Phase 1: 多页单话支持 / Multi-Page Single Episode (v0.2)

**目标:** 生成1话 = 10-20页的完整剧集

**需要修改:**

1. **`StoryboarderAgent.generate_pages()`**
   ```python
   async def generate_pages(
       self, 
       outline: EpisodeOutline,
       target_pages: int = 15,  # NEW
   ) -> List[PageSpec]:
       """
       将 EpisodeOutline 的 scenes 分配到多页
       每页根据场景复杂度动态决定panel数量
       """
   ```

2. **`PageSpec` 扩展**
   ```python
   class LayoutTemplate(str, Enum):
       GRID_2X2 = "grid_2x2"          # 当前默认
       MANGA_3PANEL = "manga_3panel"  # 3格纵向
       MANGA_5PANEL_L = "manga_5panel_l"  # 5格L型
       MANGA_7PANEL = "manga_7panel"  # 7格复杂
   
   class PageSpec(BaseModel):
       layout_template: LayoutTemplate = LayoutTemplate.GRID_2X2
       # ...其他字段保持不变
   ```

3. **前端 `ComicCanvas.tsx`**
   - 支持渲染不同 `layout_template`
   - 使用 CSS Grid 模板字符串动态布局

**CLI 更新:**
```bash
python cli/run_pipeline.py "故事" --pages 15
```

---

### Phase 2: 可变分格布局 / Variable Panel Layouts (v0.3)

**目标:** 每页支持 3-8 个分格，自动选择最佳布局

**实现方案:**

1. **布局规则库 / Layout Rules Database**
   ```python
   LAYOUT_RULES = {
       3: ["manga_3panel_vertical", "manga_3panel_horizontal"],
       4: ["grid_2x2", "manga_4panel_Z"],
       5: ["manga_5panel_L", "manga_5panel_cross"],
       6: ["manga_6panel_grid", "manga_6panel_dynamic"],
       7: ["manga_7panel_splash"],
   }
   ```

2. **StoryboarderAgent 自动布局选择**
   - 根据场景类型（action vs. dialogue）选择布局
   - 确保视觉节奏（节奏控制：不超过1个全景/页）

---

### Phase 3: 多话连载支持 / Multi-Episode Series (v0.4)

**目标:** 支持 Episode 1 → Episode 2 → ... → Episode N 的连续创作

**需要功能:**

1. **项目状态继承**
   ```python
   class SeriesState(BaseModel):
       series_id: UUID
       title: str
       character_bible: CharacterBible  # 跨话复用
       style_pack: StylePack            # 跨话复用
       episodes: List[EpisodeOutline]   # 累积所有话的大纲
       story_memory: str                # 剧情记忆摘要
   ```

2. **WriterAgent 剧情记忆 / Story Memory**
   - 在生成 Episode N 时，读取 Episode 1..N-1 的摘要
   - 确保角色成长、伏笔回收

3. **CLI 参数扩展**
   ```bash
   # 创建系列
   python cli/create_series.py "系列名" --genre action
   
   # 生成第1话
   python cli/generate_episode.py --series my_series --episode 1 --premise "..." --pages 15
   
   # 生成第2话（自动继承角色和风格）
   python cli/generate_episode.py --series my_series --episode 2 --premise "..." --pages 18
   ```

---

## 所需代码改动清单 / Required Code Changes

### 立即可做（无需模型升级）/ Immediate (No Model Upgrade Needed)

- [x] 独立项目文件夹 ✅ (已在 v0.1 实现)
- [ ] `--pages N` 参数支持
- [ ] `StoryboarderAgent` 生成 `List[PageSpec]`
- [ ] `ComicCanvas` 支持多页滚动查看

### 中期（需要调整 prompt）/ Medium-term (Prompt Tuning Required)

- [ ] `LayoutTemplate` enum 和 CSS 模板库
- [ ] StoryboarderAgent 自动布局选择逻辑
- [ ] 前端动态布局渲染

### 长期（需要系统重构）/ Long-term (System Refactor Required)

- [ ] `SeriesState` 数据模型
- [ ] `create_series.py` 和 `generate_episode.py` CLI
- [ ] WriterAgent 剧情记忆注入机制
- [ ] 前端系列管理界面

---

## 现在就可以做的变通方案 / Current Workarounds

虽然 v0.1 不支持多页，但可以通过以下方式模拟连载：

```bash
# 生成第1话（单页）
python cli/run_pipeline.py "第1话：主角登场"

# 手动保存 character_bible.json
cp output/20250321_180000_第1话/checkpoints/01_character_bible.json ./series_bible.json

# 生成第2话时，手动编辑 run_pipeline.py，加载 series_bible.json 而非重新生成
# 修改 line 280: bible = json.loads(Path("series_bible.json").read_text())
python cli/run_pipeline.py "第2话：遭遇反派"

# 在前端分别加载两个 project_final.json，手动切换查看
```

---

## 总结 / Summary

**当前 v0.1 能做什么:**
✅ 单页漫画（4分格）  
✅ 多后端（Gemini/OpenAI/Seedream）  
✅ 独立项目文件夹  
✅ 角色圣经持久化  

**要实现连载漫画，还需要:**
❌ 多页支持（1话 = 10-20页）  
❌ 可变分格布局  
❌ 话间状态继承  

**最快路径到多话连载:**
1. v0.2: 实现 `--pages N` → 生成多个 PageSpec
2. v0.3: 实现可变布局模板
3. v0.4: 实现 `SeriesState` 和剧情记忆

**预计工作量:**  
- v0.2: ~3-5天（主要是 StoryboarderAgent 改造）
- v0.3: ~2-3天（布局模板 + 前端渲染）
- v0.4: ~5-7天（系列状态系统 + CLI 重构）

**总计:** ~2-3周可实现完整的多话连载功能
