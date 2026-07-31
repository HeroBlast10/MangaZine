"""
Integration test: full pipeline run with mock adapters.

Verifies that the entire pipeline (orchestrator -> agents -> adapters)
can execute end-to-end without real API calls.
"""

import re
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


def _make_mock_page(page_num: int = 1, panel_count: int = 4) -> PageSpec:
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
            for i in range(panel_count)
        ],
    )


class _AdaptivePageMockLLM(MockLLMAdapter):
    """Return the exact panel count requested by the storyboard contract."""

    async def generate_structured_response(
        self,
        prompt,
        response_schema,
        *args,
        **kwargs,
    ):
        if response_schema is PageSpec:
            panel_count_match = re.search(r"exactly (\d+) panels", prompt)
            page_number_match = re.search(r"page (\d+)", prompt, flags=re.IGNORECASE)
            assert panel_count_match is not None
            return _make_mock_page(
                page_num=int(page_number_match.group(1)) if page_number_match else 1,
                panel_count=int(panel_count_match.group(1)),
            )
        return await super().generate_structured_response(
            prompt,
            response_schema,
            *args,
            **kwargs,
        )


@pytest.mark.asyncio
async def test_e2e_single_page(sample_character_bible, sample_episode_outline):
    """Full pipeline: 1 page, all agents run, project_final.json written."""

    llm = _AdaptivePageMockLLM(responses={
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

    llm = _AdaptivePageMockLLM(responses={
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
            episode_number=5,
            output_dir=tmp,
        ))

        assert len(project.episodes[0].pages) == 3
        assert project.episodes[0].episode_number == 5
        assert project.episodes[0].target_page_count == 3
        assert [page.page_number for page in project.episodes[0].pages] == [1, 2, 3]

        images_generated = len(img.call_log)
        assert images_generated == sum(
            len(page.panels) for page in project.episodes[0].pages
        )
