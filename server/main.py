"""
MangaZine — FastAPI application.

Provides a REST + SSE API that replaces the old ``child_process.spawn``
bridge between Next.js and the Python pipeline.

Start locally::

    uvicorn server.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from adapters import create_image_adapter, create_llm_adapter
from adapters.middleware import TokenTracker, TrackedLLMAdapter
from agents.prompt_director_agent import PromptDirectorAgent
from cli.image_paths import build_internal_image_url, to_project_relative_path
from config import Config
from models.schemas import (
    CharacterBible,
    ComicProject,
    PanelSpec,
    RenderOutput,
    RenderStatus,
    StylePack,
)
from orchestrator.events import EventBus, PipelineEvent
from orchestrator.pipeline import PipelineOrchestrator, PipelineRequest
from server.schemas import (
    PipelineRunRequest,
    PipelineStatusResponse,
    RerenderPanelRequest,
    RerenderPanelResponse,
    TokenUsageSummary,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MangaZine API",
    version="0.3.0",
    description="Multi-agent manga production pipeline API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory run registry (production would use a DB)
_active_runs: dict[UUID, PipelineOrchestrator] = {}
_run_trackers: dict[UUID, TokenTracker] = {}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}


# ---------------------------------------------------------------------------
# Pipeline — SSE streaming run
# ---------------------------------------------------------------------------


@app.post("/api/v1/pipeline/run")
async def run_pipeline(req: PipelineRunRequest):
    """
    Start a full pipeline run and stream events via SSE.

    The response is ``text/event-stream``; each line is a JSON-encoded
    ``PipelineEvent``.
    """
    try:
        Config.validate()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    raw_llm = create_llm_adapter()
    img = create_image_adapter()

    tracker = TokenTracker()
    llm = TrackedLLMAdapter(
        inner=raw_llm,
        tracker=tracker,
        provider=Config.LLM_PROVIDER.value,
    )

    event_bus = EventBus()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in req.premise[:30])
    output_dir = Config.OUTPUT_DIR / f"{timestamp}_{safe.strip().replace(' ', '_')}"

    orchestrator = PipelineOrchestrator(
        llm=llm,
        image_adapter=img,
        event_bus=event_bus,
        output_dir=output_dir,
    )

    pipeline_req = PipelineRequest(
        premise=req.premise,
        target_pages=req.target_pages,
        episode_number=req.episode_number,
        continue_from=req.continue_from,
        output_dir=str(output_dir),
    )

    async def event_stream():
        collected: list[PipelineEvent] = []

        async def _collect(event: PipelineEvent) -> None:
            collected.append(event)

        event_bus.subscribe(_collect)
        task = asyncio.create_task(orchestrator.run(pipeline_req))

        try:
            while not task.done():
                while collected:
                    evt = collected.pop(0)
                    yield f"data: {evt.model_dump_json()}\n\n"
                await asyncio.sleep(0.05)

            while collected:
                evt = collected.pop(0)
                yield f"data: {evt.model_dump_json()}\n\n"

            task.result()

            summary = tracker.summary()
            yield f"data: {json.dumps({'event_type': 'token_summary', **summary})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'event_type': 'error', 'detail': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Panel rerender
# ---------------------------------------------------------------------------


@app.post("/api/v1/panel/rerender", response_model=RerenderPanelResponse)
async def rerender_panel(req: RerenderPanelRequest):
    """Rerender a single panel using PromptDirectorAgent + ImageAdapter."""
    try:
        Config.validate()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        panel = PanelSpec.model_validate(req.panel)
        style_pack = StylePack.model_validate(req.style_pack)
        character_bible = CharacterBible.model_validate(req.character_bible)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}")

    director = PromptDirectorAgent()
    plan = director.synthesize(panel, style_pack, character_bible)

    img = create_image_adapter()
    result = await img.generate_panel_image(
        prompt=plan.final_prompt,
        style_pack=style_pack,
        draft_mode=True,
        aspect_ratio="2:3",
    )

    output_dir = Config.OUTPUT_DIR / "rerenders" / req.page_id / str(panel.panel_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    image_path = output_dir / f"{ts}.png"
    image_path.write_bytes(result.image_bytes)

    return RerenderPanelResponse(
        image_url=build_internal_image_url(image_path),
        model_used=result.model_used,
        generation_params={
            **result.generation_params,
            "local_image_path": to_project_relative_path(image_path),
        },
        generated_at=result.generated_at.isoformat() if result.generated_at else None,
    )


# ---------------------------------------------------------------------------
# Project retrieval
# ---------------------------------------------------------------------------


@app.get("/api/v1/projects")
async def list_projects():
    """List all project_final.json files in the output directory."""
    output_dir = Config.OUTPUT_DIR
    if not output_dir.exists():
        return []

    projects = []
    for pf in sorted(output_dir.rglob("project_final.json"), reverse=True):
        try:
            proj = ComicProject.model_validate_json(pf.read_text(encoding="utf-8"))
            projects.append({
                "project_id": str(proj.project_id),
                "title": proj.title,
                "status": proj.status.value,
                "episode_count": len(proj.episodes),
                "path": str(pf),
            })
        except Exception:
            continue

    return projects


@app.get("/api/v1/project/{project_path:path}")
async def get_project(project_path: str):
    """Load a project_final.json by path."""
    p = Config.OUTPUT_DIR / project_path / "project_final.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    return json.loads(p.read_text(encoding="utf-8"))
