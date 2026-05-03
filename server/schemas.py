"""
MangaZine — FastAPI request / response schemas.

Kept separate from ``models.schemas`` (domain models) to maintain a clean
boundary between the API contract and the internal domain layer.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from orchestrator.pipeline import PipelineState


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class PipelineRunRequest(BaseModel):
    """POST /api/v1/pipeline/run"""

    premise: str = Field(..., min_length=1, max_length=500)
    target_pages: int = Field(default=1, ge=1, le=20)
    episode_number: int = Field(default=1, ge=1)
    continue_from: str | None = None


class PipelineStatusResponse(BaseModel):
    """GET /api/v1/pipeline/{run_id}/status"""

    run_id: UUID
    state: PipelineState
    elapsed_ms: float = 0.0
    steps_completed: int = 0
    steps_total: int = 7


class PipelineResumeRequest(BaseModel):
    """POST /api/v1/pipeline/{run_id}/resume"""

    from_step: PipelineState


# ---------------------------------------------------------------------------
# Panel rerender
# ---------------------------------------------------------------------------


class RerenderPanelRequest(BaseModel):
    """POST /api/v1/panel/rerender"""

    panel: dict[str, Any]
    page_id: str
    style_pack: dict[str, Any]
    character_bible: dict[str, Any]
    lock_constraints: dict[str, bool] = Field(default_factory=dict)


class RerenderPanelResponse(BaseModel):
    image_url: str
    model_used: str | None = None
    generation_params: dict[str, Any] = Field(default_factory=dict)
    generated_at: str | None = None


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectListItem(BaseModel):
    project_id: UUID
    title: str
    status: str
    episode_count: int
    created_at: str


class TokenUsageSummary(BaseModel):
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
