"""
Tests for StoryboarderAgent — verifies visual rhythm check logic.

The deterministic ``_check_visual_rhythm`` function and the
LLM-driven revision loop are tested separately.
"""

import pytest

from agents.storyboarder_agent import (
    MAX_WIDE_SHOTS_PER_PAGE,
    StoryboarderAgent,
    StoryboarderOutput,
    VisualRhythmReport,
    _check_visual_rhythm,
)
from agents.writer_agent import DialogueDraft, WriterAgentOutput
from models.schemas import (
    CameraAngle,
    CharacterBible,
    EpisodeOutline,
    PageSpec,
    PanelSpec,
    ShotType,
)
from tests.conftest import MockLLMAdapter


def _make_page_with_shots(shot_types: list[ShotType]) -> PageSpec:
    panels = [
        PanelSpec(
            panel_index=i,
            shot_type=st,
            camera_angle=CameraAngle.EYE_LEVEL,
            setting_description="Test",
            action_description="Test",
        )
        for i, st in enumerate(shot_types)
    ]
    return PageSpec(page_number=1, panels=panels)


class TestCheckVisualRhythm:
    def test_approved_when_one_wide_shot(self):
        page = _make_page_with_shots([
            ShotType.CLOSE_UP,
            ShotType.WIDE_SHOT,
            ShotType.MEDIUM_SHOT,
            ShotType.CLOSE_UP,
        ])
        report = _check_visual_rhythm(page)
        assert report.is_approved
        assert report.wide_shot_count == 1

    def test_approved_when_no_wide_shots(self):
        page = _make_page_with_shots([
            ShotType.CLOSE_UP,
            ShotType.MEDIUM_SHOT,
            ShotType.MEDIUM_CLOSE_UP,
        ])
        report = _check_visual_rhythm(page)
        assert report.is_approved
        assert report.wide_shot_count == 0

    def test_rejected_when_two_wide_shots(self):
        page = _make_page_with_shots([
            ShotType.WIDE_SHOT,
            ShotType.EXTREME_WIDE,
            ShotType.MEDIUM_SHOT,
        ])
        report = _check_visual_rhythm(page)
        assert not report.is_approved
        assert report.wide_shot_count == 2
        assert len(report.issues) == 1

    def test_rejected_when_three_wide_shots(self):
        page = _make_page_with_shots([
            ShotType.WIDE_SHOT,
            ShotType.EXTREME_WIDE,
            ShotType.WIDE_SHOT,
            ShotType.MEDIUM_SHOT,
        ])
        report = _check_visual_rhythm(page)
        assert not report.is_approved
        assert report.wide_shot_count == 3
        assert len(report.issues) == 2

    def test_issues_suggest_closer_shots(self):
        page = _make_page_with_shots([
            ShotType.WIDE_SHOT,
            ShotType.EXTREME_WIDE,
            ShotType.MEDIUM_SHOT,
        ])
        report = _check_visual_rhythm(page)
        assert not report.is_approved
        for issue in report.issues:
            assert issue.suggested_shot_type != "wide_shot"
            assert issue.suggested_shot_type != "extreme_wide"

    def test_custom_max_wide(self):
        page = _make_page_with_shots([
            ShotType.WIDE_SHOT,
            ShotType.EXTREME_WIDE,
            ShotType.MEDIUM_SHOT,
        ])
        report = _check_visual_rhythm(page, max_wide=2)
        assert report.is_approved


class TestStoryboarderAgent:
    @pytest.mark.asyncio
    async def test_run_returns_output(
        self, sample_character_bible, sample_episode_outline
    ):
        mock_page = _make_page_with_shots([
            ShotType.CLOSE_UP,
            ShotType.MEDIUM_SHOT,
            ShotType.WIDE_SHOT,
            ShotType.CLOSE_UP,
        ])

        llm = MockLLMAdapter(responses={"PageSpec": mock_page})
        agent = StoryboarderAgent(llm=llm)

        writer_output = WriterAgentOutput(
            character_bible=sample_character_bible,
            episode_outline=sample_episode_outline,
            dialogue_draft=DialogueDraft(episode_title="Test"),
            critic_rounds_taken=0,
            final_critic_score=8,
        )

        output = await agent.run(writer_output, page_number=1, panel_count=4)

        assert isinstance(output, StoryboarderOutput)
        assert output.page is not None
        assert output.rhythm_check_rounds == 0
