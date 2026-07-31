"""
MangaZine — FastAPI application.

Provides a REST + SSE API that replaces the old ``child_process.spawn``
bridge between Next.js and the Python pipeline.

Start locally::

    uvicorn server.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import secrets
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import ValidationError

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from adapters import create_image_adapter, create_llm_adapter
from adapters.middleware import TokenTracker, TrackedLLMAdapter
from cli.rerender_panel import (
    LockConstraintsPayload,
    RerenderPanelPayload,
    _rerender_panel,
)
from config import Config
from models.schemas import ComicProject
from orchestrator.events import EventBus, PipelineEvent
from orchestrator.pipeline import PipelineOrchestrator, PipelineRequest
from orchestrator.tracing import init_tracer
from server.schemas import (
    PipelineRunRequest,
    RerenderPanelRequest,
    RerenderPanelResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MangaZine API",
    version="0.3.1",
    description="Multi-agent manga production pipeline API.",
)

_CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_tracer(
    service_name="mangazine-api",
    export_to_console=os.environ.get("OTEL_CONSOLE_EXPORT", "").lower() == "true",
    otlp_endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_pipeline_semaphore = asyncio.Semaphore(Config.MAX_PIPELINE_CONCURRENCY)
_generation_request_times: deque[float] = deque()
_generation_rate_lock = asyncio.Lock()


async def require_api_key(
    supplied_key: str | None = Security(_api_key_header),
) -> None:
    """Protect project data and cost-incurring endpoints with a server-side key."""
    expected_key = Config.API_KEY
    if not expected_key:
        raise HTTPException(
            status_code=503,
            detail="MANGAZINE_API_KEY is not configured on the server",
        )
    if not supplied_key or not secrets.compare_digest(supplied_key, expected_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def enforce_generation_rate_limit() -> None:
    """Apply a small in-process rate limit to cost-incurring endpoints."""
    now = time.monotonic()
    cutoff = now - 60.0
    async with _generation_rate_lock:
        while _generation_request_times and _generation_request_times[0] <= cutoff:
            _generation_request_times.popleft()
        if (
            len(_generation_request_times)
            >= Config.MAX_GENERATION_REQUESTS_PER_MINUTE
        ):
            retry_after = max(
                1,
                int(60 - (now - _generation_request_times[0])),
            )
            raise HTTPException(
                status_code=429,
                detail="Generation request rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
        _generation_request_times.append(now)


def _resolve_under_output(requested_path: str) -> Path:
    """Resolve a user-controlled path and enforce the configured output root."""
    output_dir = Config.OUTPUT_DIR.resolve()
    normalized = requested_path.replace("\\", "/").strip()
    if normalized.lower().startswith("output/"):
        normalized = normalized[7:]
    relative = Path(normalized)
    if not normalized or relative.is_absolute():
        raise HTTPException(status_code=400, detail="Invalid output path")
    candidate = (output_dir / relative).resolve()
    if not candidate.is_relative_to(output_dir):
        raise HTTPException(status_code=403, detail="Access denied")
    return candidate


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "0.3.1"}


# ---------------------------------------------------------------------------
# Pipeline — SSE streaming run
# ---------------------------------------------------------------------------


@app.post(
    "/api/v1/pipeline/run",
    dependencies=[
        Depends(require_api_key),
        Depends(enforce_generation_rate_limit),
    ],
)
async def run_pipeline(req: PipelineRunRequest, request: Request):
    """
    Start a full pipeline run and stream events via SSE.

    The response is ``text/event-stream``; each line is a JSON-encoded
    ``PipelineEvent``.
    """
    try:
        Config.validate()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if req.continue_from and req.resume_from:
        raise HTTPException(
            status_code=400,
            detail="continue_from and resume_from cannot be used together",
        )

    continue_from: str | None = None
    if req.continue_from:
        candidate = _resolve_under_output(req.continue_from)
        if candidate.is_dir():
            candidate = candidate / "project_final.json"
        if candidate.name != "project_final.json" or not candidate.is_file():
            raise HTTPException(status_code=404, detail="Previous project not found")
        continue_from = str(candidate)

    raw_llm = create_llm_adapter()
    img = create_image_adapter()

    tracker = TokenTracker()
    llm = TrackedLLMAdapter(
        inner=raw_llm,
        tracker=tracker,
        provider=Config.LLM_PROVIDER.value,
    )

    event_bus = EventBus()

    if req.resume_from:
        output_dir = _resolve_under_output(req.resume_from)
        if not output_dir.is_dir():
            raise HTTPException(status_code=404, detail="Resume directory not found")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(
            c if c.isalnum() or c in " _-" else "_"
            for c in req.premise[:30]
        )
        safe_name = safe.strip().replace(" ", "_") or "untitled"
        output_dir = (
            Config.OUTPUT_DIR
            / f"{timestamp}_{safe_name}_{uuid4().hex[:8]}"
        )

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
        continue_from=continue_from,
        output_dir=str(output_dir),
    )

    try:
        await asyncio.wait_for(_pipeline_semaphore.acquire(), timeout=0.01)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=429,
            detail="Maximum concurrent pipeline runs reached; retry later",
        ) from exc

    async def event_stream():
        collected: asyncio.Queue[PipelineEvent] = asyncio.Queue(maxsize=256)

        async def _collect(event: PipelineEvent) -> None:
            await collected.put(event)

        event_bus.subscribe(_collect)
        task = asyncio.create_task(orchestrator.run(pipeline_req))

        try:
            while not task.done() or not collected.empty():
                if await request.is_disconnected():
                    logger.info("Pipeline client disconnected; cancelling %s", pipeline_req)
                    break
                try:
                    evt = await asyncio.wait_for(collected.get(), timeout=0.5)
                    yield f"data: {evt.model_dump_json()}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"

            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                return

            await task

            summary = tracker.summary()
            yield f"data: {json.dumps({'event_type': 'token_summary', **summary})}\n\n"

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            yield f"data: {json.dumps({'event_type': 'error', 'detail': str(exc)})}\n\n"
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            _pipeline_semaphore.release()

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


@app.post(
    "/api/v1/panel/rerender",
    response_model=RerenderPanelResponse,
    dependencies=[
        Depends(require_api_key),
        Depends(enforce_generation_rate_limit),
    ],
)
async def rerender_panel(req: RerenderPanelRequest):
    """Rerender a panel while applying the requested preservation constraints."""
    try:
        Config.validate()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        payload = RerenderPanelPayload(
            panel=req.panel,
            page_id=req.page_id,
            style_pack=req.style_pack,
            character_bible=req.character_bible,
            lock_constraints=LockConstraintsPayload(
                **req.lock_constraints.model_dump()
            ),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}")

    try:
        result = await _rerender_panel(payload)
    except Exception as exc:
        logger.exception("Panel rerender failed")
        raise HTTPException(status_code=502, detail=f"Rerender failed: {exc}") from exc

    return RerenderPanelResponse(
        image_url=result.image_url,
        model_used=result.model_used,
        generation_params=result.generation_params,
        generated_at=result.generated_at,
    )


# ---------------------------------------------------------------------------
# Project retrieval
# ---------------------------------------------------------------------------


@app.get("/api/v1/projects", dependencies=[Depends(require_api_key)])
async def list_projects():
    """List all project_final.json files in the output directory."""
    output_dir = Config.OUTPUT_DIR.resolve()
    if not output_dir.exists():
        return []

    projects = []
    for pf in sorted(output_dir.rglob("project_final.json"), reverse=True):
        try:
            proj = ComicProject.model_validate_json(pf.read_text(encoding="utf-8"))
            relative_path = str(pf.parent.relative_to(output_dir))
            projects.append({
                "project_id": str(proj.project_id),
                "title": proj.title,
                "status": proj.status.value,
                "episode_count": len(proj.episodes),
                "path": relative_path,
            })
        except Exception:
            logger.debug("Skipping unreadable project file: %s", pf, exc_info=True)
            continue

    return projects


@app.get(
    "/api/v1/project/{project_path:path}",
    dependencies=[Depends(require_api_key)],
)
async def get_project(project_path: str):
    """Load a project_final.json by path."""
    project_dir = _resolve_under_output(project_path)
    p = project_dir / "project_final.json"
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        proj = ComicProject.model_validate_json(p.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="Project file is invalid") from exc
    return proj.model_dump(mode="json")


@app.get("/api/v1/image", dependencies=[Depends(require_api_key)])
async def get_project_image(path: str):
    """Serve a generated image after enforcing the output-directory boundary."""
    image_path = _resolve_under_output(path)
    allowed_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    if image_path.suffix.lower() not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported image type")
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(
        image_path,
        headers={"Cache-Control": "private, max-age=300"},
    )
