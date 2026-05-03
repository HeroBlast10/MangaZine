"""
Tests for TokenTracker and TrackedLLMAdapter middleware.
"""

import pytest

from adapters.middleware import TokenTracker, TrackedLLMAdapter
from models.schemas import CharacterBible, CharacterProfile
from tests.conftest import MockLLMAdapter


@pytest.fixture
def tracker():
    return TokenTracker()


@pytest.fixture
def sample_bible():
    return CharacterBible(characters=[
        CharacterProfile(
            name="Test",
            core_traits=["brave"],
            visual_description="A test character.",
            role="protagonist",
        ),
    ])


class TestTokenTracker:
    def test_initial_state(self, tracker):
        assert tracker.total_calls == 0
        assert tracker.total_tokens == 0
        assert tracker.total_cost_usd == 0.0

    def test_summary_format(self, tracker):
        s = tracker.summary()
        assert "total_calls" in s
        assert "total_tokens" in s
        assert "total_cost_usd" in s


class TestTrackedLLMAdapter:
    @pytest.mark.asyncio
    async def test_tracks_successful_call(self, tracker, sample_bible):
        inner = MockLLMAdapter(responses={"CharacterBible": sample_bible})
        tracked = TrackedLLMAdapter(
            inner=inner,
            tracker=tracker,
            provider="gemini",
            agent_name="writer",
            step_name="bible",
        )

        result = await tracked.generate_structured_response(
            prompt="Create a character bible",
            response_schema=CharacterBible,
        )

        assert isinstance(result, CharacterBible)
        assert tracker.total_calls == 1
        assert tracker.total_input_tokens > 0
        assert tracker.total_output_tokens > 0
        assert tracker.total_cost_usd > 0

        rec = tracker.records[0]
        assert rec.agent_name == "writer"
        assert rec.step_name == "bible"
        assert rec.success is True

    @pytest.mark.asyncio
    async def test_tracks_failed_call(self, tracker):
        inner = MockLLMAdapter()  # no responses = will raise
        tracked = TrackedLLMAdapter(
            inner=inner,
            tracker=tracker,
            provider="gemini",
        )

        with pytest.raises(ValueError):
            await tracked.generate_structured_response(
                prompt="Test",
                response_schema=CharacterBible,
            )

        assert tracker.total_calls == 1
        rec = tracker.records[0]
        assert rec.success is False
        assert rec.error is not None

    @pytest.mark.asyncio
    async def test_generate_raw(self, tracker):
        inner = MockLLMAdapter()
        tracked = TrackedLLMAdapter(inner=inner, tracker=tracker, provider="gemini")

        result = await tracked.generate_raw(prompt="Hello")
        assert result == "mock raw response"
        assert tracker.total_calls == 1
