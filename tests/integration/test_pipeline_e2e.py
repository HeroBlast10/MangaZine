"""
Integration test: full pipeline run with mock adapters.

Verifies that the entire pipeline (orchestrator -> agents -> adapters)
can execute end-to-end without real API calls.
"""

import tempfile
from pathlib import Path

import pytest

from agents.writer_agent import (
    CriticFeedback,
    DialogueDraft,
    DialogueDraftLine,
)
from models.schemas import (
    CameraAngle,
    CharacterBible,
    ComicProject,
    EpisodeOutline,
    PageSpec,
    PanelSpec,
    SceneOutline,
    ShotType,
)
from orchestrator.events import EventBus, EventType, PipelineEvent
from orchestrator.pipeline import PipelineOrchestrator, PipelineRequest
from tests.conftest import MockImageAdapter, MockLLMAdapter


def _make_mock_page(page_num: int = 1) -> PageSpec:
    return PageSpec(
        page_number=page_num,
        panels=[
            PanelSpec(
                panel_index=i,
                shot_type=ShotType.MEDIUM_SHOT,
                camera_angle=CameraAngle.EYE_LEVEL,
                setting_description="A bustling marketplace",
                action_description="Characters interact",
                prompt_plan="Dynamic manga panel of a marketplace scene",
            )
            for i in range(4)
        ],
    )


@pytest.mark.asyncio
async def test_e2e_single_page(sample_character_bible, sample_episode_outline):
    """Full pipeline: 1 page, all agents run, project_final.json written."""

    llm = MockLLMAdapter(responses={
        "CharacterBible": sample_character_bible,
        "EpisodeOutline": sample_episode_outline,
        "DialogueDraft": DialogueDraft(
            episode_title="Test",
            lines=[DialogueDraftLine(
                scene_index=0, beat_index=0,
                character_name="Kai", text="Let's go!",
            )],
        ),
        "CriticFeedback": CriticFeedback(
            overall_score=9, is_approved=True,
            general_feedback="Excellent pacing",
        ),
        "PageSpec": _make_mock_page(),
    })
    img = MockImageAdapter()
    bus = EventBus()

    events: list[PipelineEvent] = []

    async def collect(event: PipelineEvent):
        events.append(event)

    bus.subscribe(collect)

    with tempfile.TemporaryDirectory() as tmp:
        orchestrator = PipelineOrchestrator(
            llm=llm, image_adapter=img, event_bus=bus,
            output_dir=Path(tmp),
        )

        project = await orchestrator.run(PipelineRequest(
            premise="A cyberpunk chef fights food critics",
            target_pages=1,
            output_dir=tmp,
        ))

        assert isinstance(project, ComicProject)
        assert project.title
        assert len(project.episodes) == 1
        assert len(project.episodes[0].pages) == 1

        final_path = Path(tmp) / "project_final.json"
        assert final_path.exists()

        loaded = ComicProject.model_validate_json(final_path.read_text(encoding="utf-8"))
        assert loaded.project_id == project.project_id

    started = [e for e in events if e.event_type == EventType.PIPELINE_STARTED]
    completed = [e for e in events if e.event_type == EventType.PIPELINE_COMPLETED]
    assert len(started) == 1
    assert len(completed) == 1


@pytest.mark.asyncio
async def test_e2e_multi_page(sample_character_bible, sample_episode_outline):
    """Full pipeline: 3 pages, verifies all pages are generated."""

    llm = MockLLMAdapter(responses={
        "CharacterBible": sample_character_bible,
        "EpisodeOutline": sample_episode_outline,
        "DialogueDraft": DialogueDraft(
            episode_title="Test",
            lines=[DialogueDraftLine(
                scene_index=0, beat_index=0,
                character_name="Kai", text="Ready!",
            )],
        ),
        "CriticFeedback": CriticFeedback(
            overall_score=8, is_approved=True,
            general_feedback="Good",
        ),
        "PageSpec": _make_mock_page(),
    })
    img = MockImageAdapter()
    bus = EventBus()

    with tempfile.TemporaryDirectory() as tmp:
        orchestrator = PipelineOrchestrator(
            llm=llm, image_adapter=img, event_bus=bus,
            output_dir=Path(tmp),
        )

        project = await orchestrator.run(PipelineRequest(
            premise="An epic adventure",
            target_pages=3,
            output_dir=tmp,
        ))

        assert len(project.episodes[0].pages) == 3

        images_generated = len(img.call_log)
        assert images_generated == 3 * 4  # 3 pages x 4 panels
