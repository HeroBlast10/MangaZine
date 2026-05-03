"""
MangaZine — Event system for the pipeline orchestrator.

Provides a lightweight, async-first EventBus that agents and the
orchestrator use to emit structured events.  Consumers (CLI, FastAPI SSE,
WebSocket) subscribe to the bus and receive events in real time.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class EventType(str, Enum):
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"

    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    STEP_SKIPPED = "step.skipped"

    AGENT_MESSAGE = "agent.message"
    CHECKPOINT_SAVED = "checkpoint.saved"

    IMAGE_GENERATED = "image.generated"
    IMAGE_FAILED = "image.failed"

    CRITIC_REVIEW = "critic.review"
    RHYTHM_CHECK = "rhythm.check"
    QUALITY_REVIEW = "quality.review"


class PipelineEvent(BaseModel):
    """Immutable event emitted during pipeline execution."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    pipeline_run_id: UUID
    step_name: str = ""
    agent_name: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    elapsed_ms: float = 0.0

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------

EventHandler = Callable[[PipelineEvent], Coroutine[Any, Any, None]]


class EventBus:
    """
    Async publish-subscribe event bus.

    Subscribers receive *all* events; filtering by type is the subscriber's
    responsibility (or use ``subscribe_to``).
    """

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []
        self._queue: asyncio.Queue[PipelineEvent] = asyncio.Queue()

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def subscribe_to(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        async def _filtered(event: PipelineEvent) -> None:
            if event.event_type == event_type:
                await handler(event)

        self._handlers.append(_filtered)

    async def emit(self, event: PipelineEvent) -> None:
        await self._queue.put(event)
        for handler in self._handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception("Event handler failed for %s", event.event_type)

    async def stream(self):
        """Async generator that yields events as they arrive."""
        while True:
            event = await self._queue.get()
            yield event
