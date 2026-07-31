"""Tests for the vision-backed quality gate."""

import pytest

from agents.quality_reviewer_agent import QualityReport, QualityReviewerAgent
from tests.conftest import MockImageAdapter, MockLLMAdapter


@pytest.mark.asyncio
async def test_review_sends_the_generated_image(
    sample_character_bible,
    sample_panel,
    sample_style_pack,
):
    llm = MockLLMAdapter(
        responses={
            "QualityReport": QualityReport(
                panel_id="placeholder",
                overall_score=8,
                passed=True,
            )
        }
    )
    reviewer = QualityReviewerAgent(llm)

    report = await reviewer.review(
        sample_panel,
        b"real-image-bytes",
        sample_character_bible,
        sample_style_pack,
    )

    assert report.passed
    assert report.review_succeeded
    assert llm.call_log[-1]["has_image"] is True
    assert report.panel_id == str(sample_panel.panel_id)


@pytest.mark.asyncio
async def test_unavailable_vision_service_fails_closed_without_regeneration(
    sample_character_bible,
    sample_panel,
    sample_style_pack,
):
    reviewer = QualityReviewerAgent(MockLLMAdapter())
    image_adapter = MockImageAdapter()

    report, image_bytes = await reviewer.review_and_retry(
        sample_panel,
        b"original-image",
        sample_character_bible,
        sample_style_pack,
        image_adapter,
    )

    assert report.passed is False
    assert report.review_succeeded is False
    assert image_bytes == b"original-image"
    assert image_adapter.call_log == []
