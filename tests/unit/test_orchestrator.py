"""
Tests for PipelineOrchestrator — state machine transitions and event emission.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from agents.writer_agent import (
    CriticFeedback,
    DialogueDraft,
    DialogueDraftLine,
    WriterAgentOutput,
)
from models.schemas import (
    CameraAngle,
    CharacterBible,
    EpisodeOutline,
    PageSpec,
    PanelSpec,
    ShotType,
)
from orchestrator.events import EventBus, EventType, PipelineEvent
from orchestrator.pipeline import PipelineOrchestrator, PipelineRequest, PipelineState
from tests.conftest import MockImageAdapter, MockLLMAdapter


def _make_page(page_num: int = 1) -> PageSpec:
    return PageSpec(
        page_number=page_num,
        panels=[
            PanelSpec(
                panel_index=i,
                shot_type=ShotType.MEDIUM_SHOT,
                camera_angle=CameraAngle.EYE_LEVEL,
                setting_description="Test setting",
                action_description="Test action",
                prompt_plan="Test prompt",
            )
            for i in range(4)
        ],
    )


def _build_mock_llm(bible: CharacterBible, outline: EpisodeOutline) -> MockLLMAdapter:
    """Build a MockLLMAdapter with all responses needed for a full pipeline run."""
    from agents.writer_agent import _RevisionResponse

    dialogue = DialogueDraft(
        episode_title="Test",
        lines=[DialogueDraftLine(
            scene_index=0, beat_index=0,
            character_name="Test", text="Hello",
        )],
    )
    critic = CriticFeedback(
        overall_score=8,
        is_approved=True,
        general_feedback="Good",
    )

    return MockLLMAdapter(responses={
        "CharacterBible": bible,
        "EpisodeOutline": outline,
        "DialogueDraft": dialogue,
        "CriticFeedback": critic,
        "PageSpec": _make_page(),
    })


class TestPipelineState:
    def test_state_order(self):
        order = PipelineOrchestrator._STATE_ORDER
        assert order[0] == PipelineState.INIT
        assert order[-1] == PipelineState.COMPLETED
        assert PipelineState.CHARACTER_BIBLE in order
        assert PipelineState.IMAGE_GENERATION in order


class TestEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self):
        bus = EventBus()
        received = []

        async def handler(event: PipelineEvent):
            received.append(event)

        bus.subscribe(handler)

        from uuid import uuid4
        event = PipelineEvent(
            event_type=EventType.STEP_STARTED,
            pipeline_run_id=uuid4(),
            step_name="test",
        )
        await bus.emit(event)

        assert len(received) == 1
        assert received[0].event_type == EventType.STEP_STARTED

    @pytest.mark.asyncio
    async def test_subscribe_to_filtered(self):
        bus = EventBus()
        received = []

        async def handler(event: PipelineEvent):
            received.append(event)

        bus.subscribe_to(EventType.STEP_COMPLETED, handler)

        from uuid import uuid4
        run_id = uuid4()

        await bus.emit(PipelineEvent(
            event_type=EventType.STEP_STARTED,
            pipeline_run_id=run_id,
        ))
        await bus.emit(PipelineEvent(
            event_type=EventType.STEP_COMPLETED,
            pipeline_run_id=run_id,
        ))

        assert len(received) == 1
        assert received[0].event_type == EventType.STEP_COMPLETED


class TestPipelineOrchestrator:
    @pytest.mark.asyncio
    async def test_full_pipeline_run(
        self, sample_character_bible, sample_episode_outline,
    ):
        llm = _build_mock_llm(sample_character_bible, sample_episode_outline)
        img = MockImageAdapter()
        bus = EventBus()

        events: list[PipelineEvent] = []

        async def collect(event: PipelineEvent):
            events.append(event)

        bus.subscribe(collect)

        with tempfile.TemporaryDirectory() as tmp:
            orchestrator = PipelineOrchestrator(
                llm=llm,
                image_adapter=img,
                event_bus=bus,
                output_dir=Path(tmp),
            )

            request = PipelineRequest(
                premise="A test manga",
                target_pages=1,
                output_dir=tmp,
            )

            project = await orchestrator.run(request)

        assert project is not None
        assert project.title
        assert len(project.episodes) == 1

        event_types = [e.event_type for e in events]
        assert EventType.PIPELINE_STARTED in event_types
        assert EventType.PIPELINE_COMPLETED in event_types
        assert EventType.STEP_STARTED in event_types
        assert EventType.STEP_COMPLETED in event_types

    @pytest.mark.asyncio
    async def test_emits_pipeline_failed_on_error(self):
        class FailingLLM(MockLLMAdapter):
            async def generate_structured_response(self, *args, **kwargs):
                raise RuntimeError("Intentional test failure")

        llm = FailingLLM()
        img = MockImageAdapter()
        bus = EventBus()

        events: list[PipelineEvent] = []

        async def collect(event: PipelineEvent):
            events.append(event)

        bus.subscribe(collect)

        with tempfile.TemporaryDirectory() as tmp:
            orchestrator = PipelineOrchestrator(
                llm=llm,
                image_adapter=img,
                event_bus=bus,
                output_dir=Path(tmp),
            )

            with pytest.raises(RuntimeError):
                await orchestrator.run(PipelineRequest(
                    premise="Fail test",
                    target_pages=1,
                    output_dir=tmp,
                ))

        event_types = [e.event_type for e in events]
        assert EventType.PIPELINE_FAILED in event_types
