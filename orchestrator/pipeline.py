"""
MangaZine — PipelineOrchestrator
=================================
State-machine-based orchestrator that wires together the full Agent pipeline:

    WriterAgent  ->  StoryboarderAgent  ->  PromptDirectorAgent  ->  ImageAdapter

Each state transition invokes the corresponding Agent, persists a checkpoint,
and emits structured events via the EventBus.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time
from enum import Enum
from pathlib import Path
from typing import AsyncIterator
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from adapters.base import BaseLLMAdapter, BaseImageAdapter, LLMAdapterError, ImageAdapterError
from agents.prompt_director_agent import PromptDirectorAgent, PromptPlan
from agents.quality_reviewer_agent import QualityReviewerAgent
from agents.storyboarder_agent import StoryboarderAgent, StoryboarderOutput
from agents.writer_agent import WriterAgent, WriterAgentOutput
from models.schemas import (
    CharacterBible,
    ComicProject,
    EpisodeOutline,
    LayoutTemplate,
    LayoutType,
    PageSpec,
    ProjectStatus,
    RenderOutput,
    RenderStatus,
    StylePack,
)
from orchestrator.checkpoint import CheckpointManager
from orchestrator.events import EventBus, EventType, PipelineEvent
from orchestrator.tracing import trace_step
from config import Config

logger = logging.getLogger(__name__)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write a file atomically so interrupted runs do not leave partial artefacts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Pipeline state machine
# ---------------------------------------------------------------------------


class PipelineState(str, Enum):
    INIT = "init"
    STYLE_PACK = "style_pack"
    CHARACTER_BIBLE = "character_bible"
    EPISODE_OUTLINE = "episode_outline"
    STORYBOARD = "storyboard"
    PROMPT_SYNTHESIS = "prompt_synthesis"
    IMAGE_GENERATION = "image_generation"
    ASSEMBLY = "assembly"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Pipeline request / context
# ---------------------------------------------------------------------------


class PipelineRequest(BaseModel):
    premise: str
    target_pages: int = Field(default=1, ge=1, le=20)
    episode_number: int = Field(default=1, ge=1)
    continue_from: str | None = None
    output_dir: str | None = None


class PipelineContext(BaseModel):
    """Mutable state accumulated during a pipeline run."""

    run_id: UUID = Field(default_factory=uuid4)
    premise: str = ""
    episode_number: int = 1
    target_pages: int = 1

    style_pack: StylePack | None = None
    character_bible: CharacterBible | None = None
    episode_outline: EpisodeOutline | None = None
    writer_output: WriterAgentOutput | None = None
    storyboard_outputs: list[StoryboarderOutput] = Field(default_factory=list)
    prompt_plans: list[PromptPlan] = Field(default_factory=list)
    pages: list[PageSpec] = Field(default_factory=list)
    project: ComicProject | None = None

    previous_project: ComicProject | None = None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


_LAYOUT_OPTIONS: list[tuple[LayoutTemplate, int]] = [
    (LayoutTemplate.PANELS_4_GRID, 4),
    (LayoutTemplate.PANELS_5_STAGGERED, 5),
    (LayoutTemplate.PANELS_6_GRID, 6),
    (LayoutTemplate.PANELS_3_VERTICAL, 3),
    (LayoutTemplate.PANELS_4_L_SHAPE, 4),
]


def _make_style_pack(premise: str) -> StylePack:
    p = premise.lower()
    if any(w in p for w in ("cyber", "neon", "laser", "robot", "sci-fi", "scifi")):
        return StylePack(
            name="Cyberpunk Ink",
            line_weight=0.65, contrast=0.85, screentone_density=0.40,
            panel_regularity=0.50, speed_line_intensity=0.55,
            background_detail=0.65,
            color_palette=["#0d0d0d", "#f2f2f2", "#00eaff", "#ff2d55"],
            tone_keywords=["neon noir", "cinematic", "high contrast manga", "gritty"],
        )
    if any(w in p for w in ("horror", "dark", "shadow", "ghost", "demon", "fear")):
        return StylePack(
            name="Manga Noir",
            line_weight=0.70, contrast=0.90, screentone_density=0.55,
            panel_regularity=0.45, speed_line_intensity=0.30,
            background_detail=0.70,
            color_palette=["#080808", "#ebebeb"],
            tone_keywords=["dark atmosphere", "heavy shadows", "horror manga"],
        )
    return StylePack(
        name="Shonen Bold",
        line_weight=0.60, contrast=0.75, screentone_density=0.35,
        panel_regularity=0.65, speed_line_intensity=0.65,
        background_detail=0.50,
        color_palette=["#0d0d0d", "#f2f2f2"],
        tone_keywords=["dynamic", "energetic", "shonen action manga"],
    )


class PipelineOrchestrator:
    """
    State-machine-based pipeline orchestrator.

    Transitions through ``PipelineState`` values in order.  Each transition
    delegates work to the appropriate Agent, saves a checkpoint, and emits
    events via the ``EventBus``.

    Usage::

        orchestrator = PipelineOrchestrator(llm, img, event_bus)
        project = await orchestrator.run(PipelineRequest(premise="...", target_pages=5))
    """

    _STATE_ORDER: list[PipelineState] = [
        PipelineState.INIT,
        PipelineState.STYLE_PACK,
        PipelineState.CHARACTER_BIBLE,
        PipelineState.EPISODE_OUTLINE,
        PipelineState.STORYBOARD,
        PipelineState.PROMPT_SYNTHESIS,
        PipelineState.IMAGE_GENERATION,
        PipelineState.ASSEMBLY,
        PipelineState.COMPLETED,
    ]

    def __init__(
        self,
        llm: BaseLLMAdapter,
        image_adapter: BaseImageAdapter,
        event_bus: EventBus,
        output_dir: Path | None = None,
    ) -> None:
        self._llm = llm
        self._image_adapter = image_adapter
        self._event_bus = event_bus
        self._output_dir = output_dir or Path("output")

        self._writer = WriterAgent(llm=llm)
        self._storyboarder = StoryboarderAgent(llm=llm)
        self._prompt_director = PromptDirectorAgent()
        self._quality_reviewer = QualityReviewerAgent(llm=llm)

        self._state = PipelineState.INIT
        self._ctx: PipelineContext | None = None
        self._checkpoint: CheckpointManager | None = None
        self._image_concurrency = max(1, Config.MAX_IMAGE_CONCURRENCY)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, request: PipelineRequest) -> ComicProject:
        """Execute the full pipeline and return the assembled project."""
        self._ctx = PipelineContext(
            premise=request.premise,
            episode_number=request.episode_number,
            target_pages=request.target_pages,
        )

        out_dir = Path(request.output_dir) if request.output_dir else self._output_dir
        images_dir = out_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint = CheckpointManager(out_dir / "checkpoints")

        if request.continue_from:
            self._load_previous_project(request.continue_from)

        await self._emit(EventType.PIPELINE_STARTED, step_name="pipeline", payload={
            "premise": request.premise,
            "target_pages": request.target_pages,
            "episode_number": self._ctx.episode_number,
        })

        ctx = self._ctx

        try:
            for state in self._STATE_ORDER[1:-1]:  # skip INIT and COMPLETED
                self._state = state

                if self._try_restore_checkpoint(state, ctx):
                    await self._emit(
                        EventType.STEP_SKIPPED,
                        step_name=state.value,
                        payload={"reason": "restored from checkpoint"},
                    )
                    continue

                t0 = time.monotonic()
                await self._emit(EventType.STEP_STARTED, step_name=state.value)

                agent_name = {
                    PipelineState.CHARACTER_BIBLE: "WriterAgent",
                    PipelineState.EPISODE_OUTLINE: "WriterAgent",
                    PipelineState.STORYBOARD: "StoryboarderAgent",
                    PipelineState.PROMPT_SYNTHESIS: "PromptDirectorAgent",
                    PipelineState.IMAGE_GENERATION: "ImageGeneration",
                    PipelineState.ASSEMBLY: "PipelineOrchestrator",
                }.get(state, "PipelineOrchestrator")
                tracking_context = (
                    self._llm.tracking_context(agent_name, state.value)
                    if hasattr(self._llm, "tracking_context")
                    else contextlib.nullcontext()
                )
                async with trace_step(
                    agent_name,
                    state.value,
                    attributes={"pipeline.run_id": str(ctx.run_id)},
                ):
                    with tracking_context:
                        await self._execute_step(state, images_dir)

                elapsed = (time.monotonic() - t0) * 1000
                await self._emit(
                    EventType.STEP_COMPLETED,
                    step_name=state.value,
                    payload={"elapsed_ms": round(elapsed, 1)},
                )

            self._state = PipelineState.COMPLETED
            await self._emit(EventType.PIPELINE_COMPLETED, step_name="pipeline")
            return self._ctx.project  # type: ignore[return-value]

        except Exception as exc:
            failed_at = self._state.value
            self._state = PipelineState.FAILED
            await self._emit(EventType.STEP_FAILED, step_name=failed_at, payload={
                "error": str(exc),
            })
            await self._emit(EventType.PIPELINE_FAILED, step_name="pipeline", payload={
                "error": str(exc),
                "failed_state": failed_at,
            })
            raise

    async def run_stream(
        self, request: PipelineRequest,
    ) -> AsyncIterator[PipelineEvent]:
        """Run the pipeline and yield events as an async stream (for SSE)."""
        collected: asyncio.Queue[PipelineEvent] = asyncio.Queue(maxsize=256)

        async def _collector(event: PipelineEvent) -> None:
            await collected.put(event)

        self._event_bus.subscribe(_collector)

        task = asyncio.create_task(self.run(request))

        try:
            while not task.done() or not collected.empty():
                try:
                    yield await asyncio.wait_for(collected.get(), timeout=0.5)
                except TimeoutError:
                    continue
            await task
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    # ------------------------------------------------------------------
    # Step dispatcher
    # ------------------------------------------------------------------

    async def _execute_step(self, state: PipelineState, images_dir: Path) -> None:
        ctx = self._ctx
        assert ctx is not None
        assert self._checkpoint is not None

        if state == PipelineState.STYLE_PACK:
            await self._step_style_pack(ctx)

        elif state == PipelineState.CHARACTER_BIBLE:
            await self._step_character_bible(ctx)

        elif state == PipelineState.EPISODE_OUTLINE:
            await self._step_episode_outline(ctx)

        elif state == PipelineState.STORYBOARD:
            await self._step_storyboard(ctx)

        elif state == PipelineState.PROMPT_SYNTHESIS:
            await self._step_prompt_synthesis(ctx)

        elif state == PipelineState.IMAGE_GENERATION:
            await self._step_image_generation(ctx, images_dir)

        elif state == PipelineState.ASSEMBLY:
            await self._step_assembly(ctx, images_dir.parent)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _step_style_pack(self, ctx: PipelineContext) -> None:
        if ctx.previous_project:
            ctx.style_pack = ctx.previous_project.style_pack
        else:
            ctx.style_pack = _make_style_pack(ctx.premise)
        self._checkpoint.save("01_style_pack", ctx.style_pack)

    async def _step_character_bible(self, ctx: PipelineContext) -> None:
        if ctx.previous_project:
            ctx.character_bible = ctx.previous_project.character_bible
            self._checkpoint.save("02_character_bible", ctx.character_bible)
            return

        writer_output = await self._writer.run(
            ctx.premise,
            style_pack=ctx.style_pack,
            target_pages=ctx.target_pages,
            episode_number=ctx.episode_number,
        )
        # Detach from provider/mock-owned instances before normalizing request
        # metadata and storing mutable pipeline state.
        ctx.writer_output = writer_output.model_copy(deep=True)
        ctx.writer_output.episode_outline.episode_number = ctx.episode_number
        ctx.writer_output.episode_outline.target_page_count = ctx.target_pages
        ctx.character_bible = ctx.writer_output.character_bible
        ctx.episode_outline = ctx.writer_output.episode_outline

        self._checkpoint.save("02_character_bible", ctx.character_bible)
        self._checkpoint.save("02_writer_output", ctx.writer_output)

        await self._emit(EventType.CRITIC_REVIEW, step_name="writer_critic", payload={
            "critic_rounds": writer_output.critic_rounds_taken,
            "final_score": writer_output.final_critic_score,
        })

    async def _step_episode_outline(self, ctx: PipelineContext) -> None:
        if ctx.episode_outline is not None:
            self._checkpoint.save("03_episode_outline", ctx.episode_outline)
            return

        story_memory = ""
        if ctx.previous_project and ctx.previous_project.episodes:
            memory_parts = ["Previous episode summaries for continuity:"]
            for ep in ctx.previous_project.episodes[-3:]:
                memory_parts.append(
                    f"- Episode {ep.episode_number} \u00ab{ep.title}\u00bb: {ep.logline}"
                )
            story_memory = "\n".join(memory_parts)

        scene_count = max(1, min(ctx.target_pages // 3 + 1, 6))
        bible_json = ctx.character_bible.model_dump_json(indent=2)

        outline: EpisodeOutline = await self._llm.generate_structured_response(
            prompt=_PROMPT_EPISODE_OUTLINE.format(
                premise=ctx.premise,
                bible_json=bible_json,
                episode_number=ctx.episode_number,
                target_pages=ctx.target_pages,
                scene_count=scene_count,
                story_memory=story_memory,
            ),
            response_schema=EpisodeOutline,
            system_instruction=_SYSTEM_COMIC_WRITER,
            temperature=0.75,
        )
        ctx.episode_outline = outline
        self._checkpoint.save("03_episode_outline", outline)

    async def _step_storyboard(self, ctx: PipelineContext) -> None:
        assert ctx.writer_output is not None or ctx.character_bible is not None
        assert ctx.episode_outline is not None

        writer_out = ctx.writer_output
        if writer_out is None:
            from agents.writer_agent import DialogueDraft, WriterAgentOutput
            writer_out = WriterAgentOutput(
                character_bible=ctx.character_bible,
                episode_outline=ctx.episode_outline,
                dialogue_draft=DialogueDraft(episode_title=ctx.episode_outline.title),
                critic_rounds_taken=0,
                final_critic_score=0,
            )

        pages: list[PageSpec] = []
        for page_num in range(1, ctx.target_pages + 1):
            if page_num == 1:
                layout_template = LayoutTemplate.PANELS_4_GRID
                panel_count = 4
            elif page_num == ctx.target_pages:
                layout_template = LayoutTemplate.PANELS_5_STAGGERED
                panel_count = 5
            else:
                layout_template, panel_count = random.choice(_LAYOUT_OPTIONS)

            layout_type = (
                LayoutType.UNIFORM_GRID
                if layout_template in {
                    LayoutTemplate.PANELS_4_GRID,
                    LayoutTemplate.PANELS_6_GRID,
                    LayoutTemplate.PANELS_3_VERTICAL,
                }
                else LayoutType.ASYMMETRIC
            )
            sb_output: StoryboarderOutput = await self._storyboarder.run(
                writer_output=writer_out,
                page_number=page_num,
                panel_count=panel_count,
                layout_type=layout_type.value,
            )
            ctx.storyboard_outputs.append(sb_output)
            page = sb_output.page
            page.layout_template = layout_template
            pages.append(page)

            await self._emit(EventType.RHYTHM_CHECK, step_name=f"storyboard_page_{page_num}", payload={
                "page_number": page_num,
                "panel_count": len(page.panels),
                "rhythm_rounds": sb_output.rhythm_check_rounds,
            })

        ctx.pages = pages
        self._checkpoint.save("04_page_specs", pages)

    async def _step_prompt_synthesis(self, ctx: PipelineContext) -> None:
        assert ctx.character_bible is not None
        assert ctx.style_pack is not None

        plans: list[PromptPlan] = []
        for page in ctx.pages:
            page_plans = self._prompt_director.batch_synthesize(
                panels=page.panels,
                style_pack=ctx.style_pack,
                character_bible=ctx.character_bible,
            )
            plans.extend(page_plans)

            for panel, plan in zip(page.panels, page_plans):
                panel.prompt_plan = plan.final_prompt
                if plan.negative_prompt:
                    panel.render_refs.negative_prompt = plan.negative_prompt

        ctx.prompt_plans = plans
        self._checkpoint.save("05_prompt_plans", [p.model_dump() for p in plans])

    async def _step_image_generation(self, ctx: PipelineContext, images_dir: Path) -> None:
        assert ctx.style_pack is not None
        assert ctx.character_bible is not None
        assert self._checkpoint is not None

        from cli.image_paths import build_internal_image_url, to_project_relative_path

        progress = self._checkpoint.load("06_render_progress")
        if isinstance(progress, list):
            try:
                restored_pages = [PageSpec.model_validate(item) for item in progress]
                restored_outputs = {
                    panel.panel_id: panel.render_output
                    for page in restored_pages
                    for panel in page.panels
                }
                for page in ctx.pages:
                    for panel in page.panels:
                        restored = restored_outputs.get(panel.panel_id)
                        if restored is not None:
                            panel.render_output = restored
            except Exception:
                logger.warning("Render progress checkpoint is invalid; regenerating", exc_info=True)

        total = sum(len(p.panels) for p in ctx.pages)
        rendered = sum(
            1
            for page in ctx.pages
            for panel in page.panels
            if panel.render_output.status in {
                RenderStatus.DRAFT_READY,
                RenderStatus.APPROVED,
            }
        )
        counter_lock = asyncio.Lock()
        semaphore = asyncio.Semaphore(self._image_concurrency)

        async def render_panel(page: PageSpec, panel) -> None:
            nonlocal rendered
            page_dir = images_dir / f"page_{page.page_number:02d}"
            image_path = page_dir / f"panel_{panel.panel_index}.png"

            if (
                image_path.exists()
                and panel.render_output.status
                in {RenderStatus.DRAFT_READY, RenderStatus.APPROVED}
            ):
                return

            char_visuals: list[str] = []
            reference_images: list[str] = [
                str(url) for url in ctx.style_pack.reference_image_urls
            ]
            for cid in panel.characters:
                char = ctx.character_bible.get_by_id(cid)
                if char:
                    char_visuals.append(f"{char.name}: {char.visual_description}")
                    reference_images.extend(str(url) for url in char.reference_image_urls)
            reference_images = list(dict.fromkeys(reference_images))

            enriched_prompt = panel.prompt_plan
            if char_visuals:
                enriched_prompt += "  Characters in frame — " + "; ".join(char_visuals)

            async with semaphore:
                try:
                    image_result = await self._image_adapter.generate_panel_image(
                        prompt=enriched_prompt,
                        style_pack=ctx.style_pack,
                        reference_images=reference_images or None,
                        draft_mode=True,
                        aspect_ratio="2:3",
                        negative_prompt=panel.render_refs.negative_prompt or None,
                    )
                    _atomic_write_bytes(image_path, image_result.image_bytes)
                    internal_url = build_internal_image_url(image_path)

                    panel.render_output = RenderOutput(
                        status=RenderStatus.DRAFT_READY,
                        model_used=image_result.model_used,
                        image_url=internal_url,
                        generation_params={
                            **image_result.generation_params,
                            "local_image_path": to_project_relative_path(image_path),
                        },
                        generated_at=image_result.generated_at,
                    )
                    async with counter_lock:
                        rendered += 1
                        rendered_snapshot = rendered

                    await self._emit(EventType.IMAGE_GENERATED, step_name="render", payload={
                        "page": page.page_number,
                        "panel": panel.panel_index,
                        "size_kb": len(image_result.image_bytes) // 1024,
                        "rendered": rendered_snapshot,
                        "total": total,
                    })

                    try:
                        report, final_bytes = await self._quality_reviewer.review_and_retry(
                            panel=panel,
                            image_bytes=image_result.image_bytes,
                            character_bible=ctx.character_bible,
                            style_pack=ctx.style_pack,
                            image_adapter=self._image_adapter,
                        )
                        if final_bytes != image_result.image_bytes:
                            _atomic_write_bytes(image_path, final_bytes)

                        panel.render_output.status = (
                            RenderStatus.APPROVED if report.passed else RenderStatus.REJECTED
                        )
                        panel.render_output.reviewer_notes = "; ".join(report.issues) or None
                        panel.render_output.generation_params["quality_score"] = report.overall_score
                        panel.render_output.generation_params["quality_passed"] = report.passed

                        await self._emit(EventType.QUALITY_REVIEW, step_name="quality", payload={
                            "page": page.page_number,
                            "panel": panel.panel_index,
                            "score": report.overall_score,
                            "passed": report.passed,
                            "issues": report.issues[:3],
                        })
                    except Exception as qr_exc:
                        panel.render_output.status = RenderStatus.REJECTED
                        panel.render_output.reviewer_notes = (
                            f"Quality review failed: {qr_exc}"
                        )
                        logger.warning(
                            "Quality review failed for panel %s: %s",
                            panel.panel_id,
                            qr_exc,
                        )

                except ImageAdapterError as exc:
                    panel.render_output.status = RenderStatus.REJECTED
                    panel.render_output.reviewer_notes = str(exc)

                    await self._emit(EventType.IMAGE_FAILED, step_name="render", payload={
                        "page": page.page_number,
                        "panel": panel.panel_index,
                        "error": str(exc),
                    })

        for page in ctx.pages:
            await asyncio.gather(*(render_panel(page, panel) for panel in page.panels))
            self._checkpoint.save("06_render_progress", ctx.pages)

        self._checkpoint.save("06_rendered_pages", ctx.pages)

    async def _step_assembly(self, ctx: PipelineContext, output_dir: Path) -> None:
        assert ctx.episode_outline is not None
        assert ctx.style_pack is not None
        assert ctx.character_bible is not None

        from datetime import datetime as dt, timezone

        ctx.episode_outline.pages = ctx.pages

        if ctx.previous_project:
            project = ctx.previous_project.model_copy(deep=True)
            project.episodes.append(ctx.episode_outline)
            project.updated_at = dt.now(timezone.utc)
            project.status = ProjectStatus.REVIEW
        else:
            project = ComicProject(
                title=ctx.episode_outline.title,
                subtitle=ctx.premise[:120],
                genre=["action"],
                status=ProjectStatus.REVIEW,
                style_pack=ctx.style_pack,
                character_bible=ctx.character_bible,
                episodes=[ctx.episode_outline],
                author="MangaZine Pipeline",
            )

        ctx.project = project
        final_path = output_dir / "project_final.json"
        _atomic_write_text(final_path, project.model_dump_json(indent=2))
        self._checkpoint.save("07_project", project)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    _CHECKPOINT_MAP: dict[PipelineState, tuple[str, str]] = {
        PipelineState.STYLE_PACK: ("01_style_pack", "style_pack"),
        PipelineState.CHARACTER_BIBLE: ("02_character_bible", "character_bible"),
        PipelineState.EPISODE_OUTLINE: ("03_episode_outline", "episode_outline"),
    }

    def _try_restore_checkpoint(self, state: PipelineState, ctx: PipelineContext) -> bool:
        """Try to restore a pipeline step from checkpoint. Returns True if skipped."""
        if self._checkpoint is None:
            return False

        if state == PipelineState.CHARACTER_BIBLE:
            writer_data = self._checkpoint.load("02_writer_output")
            if isinstance(writer_data, dict):
                try:
                    writer_output = WriterAgentOutput.model_validate(writer_data)
                    ctx.writer_output = writer_output
                    ctx.character_bible = writer_output.character_bible
                    ctx.episode_outline = writer_output.episode_outline
                    logger.info("Restored checkpoint: 02_writer_output")
                    return True
                except Exception:
                    logger.warning(
                        "Checkpoint 02_writer_output invalid, falling back",
                        exc_info=True,
                    )

        if state == PipelineState.STORYBOARD:
            data = self._checkpoint.load("04_page_specs")
            if isinstance(data, list):
                try:
                    ctx.pages = [PageSpec.model_validate(item) for item in data]
                    logger.info("Restored checkpoint: 04_page_specs")
                    return True
                except Exception:
                    logger.warning("Checkpoint 04_page_specs invalid", exc_info=True)
            return False

        if state == PipelineState.PROMPT_SYNTHESIS:
            data = self._checkpoint.load("05_prompt_plans")
            if isinstance(data, list) and ctx.pages:
                try:
                    plans = [PromptPlan.model_validate(item) for item in data]
                    by_panel_id = {plan.panel_id: plan for plan in plans}
                    for page in ctx.pages:
                        for panel in page.panels:
                            plan = by_panel_id.get(str(panel.panel_id))
                            if plan is None:
                                raise ValueError(
                                    f"Missing prompt checkpoint for panel {panel.panel_id}"
                                )
                            panel.prompt_plan = plan.final_prompt
                            panel.render_refs.negative_prompt = plan.negative_prompt
                    ctx.prompt_plans = plans
                    logger.info("Restored checkpoint: 05_prompt_plans")
                    return True
                except Exception:
                    logger.warning("Checkpoint 05_prompt_plans invalid", exc_info=True)
            return False

        if state == PipelineState.IMAGE_GENERATION:
            data = self._checkpoint.load("06_rendered_pages")
            if isinstance(data, list):
                try:
                    ctx.pages = [PageSpec.model_validate(item) for item in data]
                    logger.info("Restored checkpoint: 06_rendered_pages")
                    return True
                except Exception:
                    logger.warning("Checkpoint 06_rendered_pages invalid", exc_info=True)
            return False

        if state == PipelineState.ASSEMBLY:
            data = self._checkpoint.load("07_project")
            if isinstance(data, dict):
                try:
                    ctx.project = ComicProject.model_validate(data)
                    logger.info("Restored checkpoint: 07_project")
                    return True
                except Exception:
                    logger.warning("Checkpoint 07_project invalid", exc_info=True)
            return False

        mapping = self._CHECKPOINT_MAP.get(state)
        if mapping is None:
            return False
        cp_name, ctx_attr = mapping
        if not self._checkpoint.has_checkpoint(cp_name):
            return False
        if getattr(ctx, ctx_attr, None) is not None:
            return False

        data = self._checkpoint.load(cp_name)
        if data is None:
            return False

        schema_map: dict[str, type] = {
            "style_pack": StylePack,
            "character_bible": CharacterBible,
            "episode_outline": EpisodeOutline,
        }
        model_cls = schema_map.get(ctx_attr)
        if model_cls and isinstance(data, dict):
            try:
                setattr(ctx, ctx_attr, model_cls.model_validate(data))
                logger.info("Restored checkpoint: %s", cp_name)
                return True
            except Exception:
                logger.warning("Checkpoint %s invalid, re-running step", cp_name)
                return False
        return False

    def _load_previous_project(self, path_str: str) -> None:
        p = Path(path_str)
        if not p.exists():
            logger.warning("Continue-from path not found: %s", p)
            return
        try:
            prev = ComicProject.model_validate_json(p.read_text(encoding="utf-8"))
            self._ctx.previous_project = prev
            auto_episode = len(prev.episodes) + 1
            if self._ctx.episode_number <= 1:
                self._ctx.episode_number = auto_episode
            logger.info(
                "Loaded previous project (%d episodes), episode_number=%d",
                len(prev.episodes), self._ctx.episode_number,
            )
        except Exception:
            logger.warning("Failed to load previous project from %s", p, exc_info=True)

    async def _emit(
        self,
        event_type: EventType,
        step_name: str = "",
        payload: dict | None = None,
    ) -> None:
        event = PipelineEvent(
            event_type=event_type,
            pipeline_run_id=self._ctx.run_id if self._ctx else uuid4(),
            step_name=step_name,
            payload=payload or {},
        )
        await self._event_bus.emit(event)


# ---------------------------------------------------------------------------
# Prompt templates (used only when WriterAgent doesn't produce an outline,
# e.g. when continuing from a previous project)
# ---------------------------------------------------------------------------

_SYSTEM_COMIC_WRITER = (
    "You are an expert manga script writer and comic book director. "
    "You produce precisely structured, vivid, and cinematically aware descriptions. "
    "IMPORTANT: Do not generate any UUID / ID fields — they are auto-assigned by the system."
)

_PROMPT_EPISODE_OUTLINE = """\
Create an EpisodeOutline for Episode {episode_number} of this manga.

Premise: "{premise}"

CharacterBible (the character_id values are already system-assigned — copy them
verbatim into characters_present when referencing characters in scenes):
{bible_json}

{story_memory}

Requirements:
- episode_number : {episode_number}
- title          : a compelling episode title
- logline        : one gripping sentence describing the central conflict
- scenes         : {scene_count} scenes for this {target_pages}-page episode
  * For each scene's characters_present, use the EXACT character_id UUID strings
    from the CharacterBible JSON above — do not invent new ones.
  * Distribute scenes across pages: assign page_range tuples like (1, 3) or (4, 5)
- target_page_count : {target_pages}
- Do NOT include: episode_id, pages, created_at, updated_at.
"""
