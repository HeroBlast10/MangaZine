# Changelog

## v0.3.0 — Production-Grade Multi-Agent Orchestration (2026-05-03)

MangaZine 从原型级 CLI 工具跃升为**真正可运维的多 Agent 协作系统**。本次升级覆盖 6 大模块、20+ 新文件、35 项自动化测试，彻底解决了 Agent 模块与主路径脱节、缺乏编排层和可观测性等核心断层。

### Module A: Agent Orchestration Layer

- **新建 `orchestrator/` 目录**，实现有限状态机（`PipelineState`）+ 事件驱动（`EventBus`）编排引擎。
- `PipelineOrchestrator` 按 INIT → STYLE_PACK → CHARACTER_BIBLE → EPISODE_OUTLINE → STORYBOARD → PROMPT_SYNTHESIS → IMAGE_GENERATION → ASSEMBLY → COMPLETED 顺序调度。
- **每个 Agent 真正被调用**：`WriterAgent.run()` → `StoryboarderAgent.run()` → `PromptDirectorAgent.synthesize()`，消除原先 `cli/run_pipeline.py` 中手动 LLM 调用与 Agent 类并存的断层。
- 新增 `CheckpointManager`，每步完成后自动序列化中间产物，支持断点恢复。
- 重写 `cli/run_pipeline.py`，从 500 行扁平 async 函数精简为委托 `PipelineOrchestrator` 的 CLI 入口。

### Module A+: Unified LLM Adapter

- 将 `adapters/llm_adapter.py`（Agent 类专用）降级为向后兼容 shim，统一指向 `adapters/gemini_llm.py`（`GeminiLLMAdapter`）。
- `WriterAgent` 和 `StoryboarderAgent` 改为依赖 `BaseLLMAdapter` 接口注入，与工厂函数 `create_llm_adapter()` 完全对齐。

### Module B: Agent Communication Protocol & Observability

- **`orchestrator/messages.py`**：结构化 `AgentMessage` 协议 — 支持 `trace_id` 全链路追踪、`parent_message_id` 因果链、5 种消息类型（request / response / feedback / revision / error）。
- **`adapters/middleware.py`**：`TokenTracker` + `TrackedLLMAdapter` 装饰器 — 自动记录每次 LLM 调用的 input/output token 数、延迟、成本估算。
- **`orchestrator/tracing.py`**：OpenTelemetry 集成 — 每个 Agent 步骤为一个 span，支持导出到 Jaeger/Zipkin。未安装 OTel SDK 时自动降级为 no-op，不影响核心流程。

### Module C: FastAPI Backend + SSE

- **新建 `server/main.py`**，实现完整的 FastAPI 后端：
  - `POST /api/v1/pipeline/run` — SSE 流式事件推送，替代 `child_process.spawn`。
  - `POST /api/v1/panel/rerender` — 单格重生成端点。
  - `GET /api/v1/projects` — 项目列表查询。
  - `GET /api/v1/project/{path}` — 项目详情查询。
  - `GET /api/v1/health` — 健康检查。
- `server/schemas.py`：API 请求/响应 Pydantic 模型，与内部 domain model 解耦。

### Module D: QualityReviewerAgent

- **新建 `agents/quality_reviewer_agent.py`**：Vision LLM 驱动的后生成质量门控。
- 评估 5 个维度：角色一致性、构图准确性、风格匹配度、技术质量、叙事清晰度。
- 输出 `QualityReport`（1-10 评分 + 具体问题 + 提示词修正建议）。
- `review_and_retry()` 方法：低分时自动用 `prompt_refinement` 反馈重新生成。

### Module E: Test Suite & CI/CD

- **35 项自动化测试，全部通过**：
  - `test_prompt_director.py`（13 项）— 确定性逻辑 100% 覆盖。
  - `test_writer_agent.py`（4 项）— Critic 循环（通过 / 修订 / 耗尽重试）。
  - `test_storyboarder_agent.py`（7 项）— 视觉节奏校验。
  - `test_orchestrator.py`（4 项）— 状态机转换 + EventBus。
  - `test_middleware.py`（5 项）— TokenTracker 追踪。
  - `test_pipeline_e2e.py`（2 项）— 全流水线 mock 集成测试。
- `conftest.py`：`MockLLMAdapter` + `MockImageAdapter` 可复用测试 fixtures。
- `.github/workflows/ci.yml`：GitHub Actions CI（Python 3.11/3.12 + Node.js 20）。
- `Dockerfile`：多阶段构建（backend + frontend）。
- `docker-compose.yml`：一键部署 backend + frontend。

### Module F: Frontend Pipeline Console

- **新增 `/pipeline` 页面**：在浏览器中输入故事前提，一键启动完整 Agent 流水线。
- **Agent 执行链路可视化**：7 步进度条 + 实时状态（旋转动画 / 绿色完成 / 红色失败）。
- **实时事件流**：SSE 连接后端，所有 Pipeline 事件按时间轴滚动显示。
- **成本仪表盘**：LLM 调用次数、Token 总量、预估费用、总耗时。
- 首页 header 新增 "Pipeline 控制台" 入口按钮。

### Other Changes

- `requirements.txt` 新增 `opentelemetry-api`、`opentelemetry-sdk`、`pytest`、`pytest-asyncio`。
- `pytest.ini` 配置 `asyncio_mode = auto`。
- `agents/__init__.py` 新增 `QualityReviewerAgent` 和 `QualityReport` 导出。
- `orchestrator/__init__.py` 统一导出所有编排层类型。

---

## v0.2.0 — Multi-Page & Multi-Episode (2026-03-26)

- Multi-page generation (`--pages N`)
- Multi-episode continuity (`--continue-from`)
- 16 layout templates
- Story memory injection across episodes

## v0.1.0 — Initial Release (2026-03-22)

- Core CLI pipeline
- WriterAgent / StoryboarderAgent / PromptDirectorAgent
- Browser-based project viewer
- Single-page generation
- Gemini adapter
