"""
Tests for WriterAgent — verifies Critic loop control flow.

Uses MockLLMAdapter to inject deterministic responses, then asserts
that the agent follows the correct branching logic (approve, revise,
exhaust retries).
"""

import pytest

from agents.writer_agent import (
    CriticFeedback,
    DialogueDraft,
    DialogueDraftLine,
    WriterAgent,
    WriterAgentOutput,
    _RevisionResponse,
)
from models.schemas import CharacterBible, EpisodeOutline, SceneOutline
from tests.conftest import MockLLMAdapter


def _make_critic_feedback(score: int, approved: bool) -> CriticFeedback:
    return CriticFeedback(
        overall_score=score,
        is_approved=approved,
        pacing_issues=[],
        general_feedback="Test feedback",
        revision_instructions="" if approved else "Fix pacing",
    )


def _make_dialogue_draft() -> DialogueDraft:
    return DialogueDraft(
        episode_title="Test Episode",
        lines=[
            DialogueDraftLine(
                scene_index=0,
                beat_index=0,
                character_name="Kai",
                text="Test dialogue",
            )
        ],
    )


@pytest.fixture
def approved_llm(sample_character_bible, sample_episode_outline):
    """LLM that returns approved quality on first critic review."""
    return MockLLMAdapter(responses={
        "CharacterBible": sample_character_bible,
        "EpisodeOutline": sample_episode_outline,
        "DialogueDraft": _make_dialogue_draft(),
        "CriticFeedback": _make_critic_feedback(8, True),
    })


@pytest.fixture
def needs_revision_llm(sample_character_bible, sample_episode_outline):
    """LLM that fails critic, then passes on revision."""
    class RevisionMockLLM(MockLLMAdapter):
        def __init__(self):
            super().__init__(responses={
                "CharacterBible": sample_character_bible,
                "EpisodeOutline": sample_episode_outline,
                "DialogueDraft": _make_dialogue_draft(),
                "_RevisionResponse": _RevisionResponse(
                    episode_outline=sample_episode_outline,
                    dialogue_draft=_make_dialogue_draft(),
                ),
            })
            self._critic_call_count = 0

        async def generate_structured_response(self, prompt, response_schema, **kwargs):
            if response_schema.__name__ == "CriticFeedback":
                self._critic_call_count += 1
                if self._critic_call_count == 1:
                    return _make_critic_feedback(4, False)
                return _make_critic_feedback(8, True)
            return await super().generate_structured_response(prompt, response_schema, **kwargs)

    return RevisionMockLLM()


class TestWriterAgentApproved:
    @pytest.mark.asyncio
    async def test_approved_first_round(self, approved_llm):
        agent = WriterAgent(llm=approved_llm)
        output = await agent.run("A hero fights evil")

        assert isinstance(output, WriterAgentOutput)
        assert output.final_critic_score >= 7
        assert output.character_bible is not None
        assert output.episode_outline is not None
        assert output.dialogue_draft is not None

    @pytest.mark.asyncio
    async def test_no_revision_rounds_when_approved(self, approved_llm):
        agent = WriterAgent(llm=approved_llm)
        output = await agent.run("A hero fights evil")
        assert output.critic_rounds_taken == 0


class TestWriterAgentRevision:
    @pytest.mark.asyncio
    async def test_revision_on_low_score(self, needs_revision_llm):
        agent = WriterAgent(llm=needs_revision_llm)
        output = await agent.run("A hero fights evil")

        assert output.critic_rounds_taken == 1
        assert output.final_critic_score >= 7

    @pytest.mark.asyncio
    async def test_exhausts_retries(self, sample_character_bible, sample_episode_outline):
        class AlwaysFailLLM(MockLLMAdapter):
            def __init__(self):
                super().__init__(responses={
                    "CharacterBible": sample_character_bible,
                    "EpisodeOutline": sample_episode_outline,
                    "DialogueDraft": _make_dialogue_draft(),
                    "_RevisionResponse": _RevisionResponse(
                        episode_outline=sample_episode_outline,
                        dialogue_draft=_make_dialogue_draft(),
                    ),
                })

            async def generate_structured_response(self, prompt, response_schema, **kwargs):
                if response_schema.__name__ == "CriticFeedback":
                    return _make_critic_feedback(3, False)
                return await super().generate_structured_response(prompt, response_schema, **kwargs)

        agent = WriterAgent(llm=AlwaysFailLLM())
        output = await agent.run("A hero fights evil")

        assert output.final_critic_score < 7
