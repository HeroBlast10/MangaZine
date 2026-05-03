"""
Shared test fixtures for MangaZine.

Provides mock LLM/Image adapters that return deterministic data,
allowing agent logic and orchestrator control flow to be tested
without calling real APIs.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Type, TypeVar
from uuid import uuid4

import pytest
from pydantic import BaseModel

from adapters.base import (
    BaseImageAdapter,
    BaseLLMAdapter,
    GeneratedImageResult,
)
from models.schemas import (
    CameraAngle,
    CharacterBible,
    CharacterProfile,
    DialogueLine,
    EpisodeOutline,
    LayoutTemplate,
    PageSpec,
    PanelSpec,
    SceneOutline,
    ShotType,
    StylePack,
)

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Mock LLM adapter
# ---------------------------------------------------------------------------


class MockLLMAdapter(BaseLLMAdapter):
    """
    Deterministic mock LLM adapter for testing.

    Accepts a ``responses`` dict mapping Pydantic class names to pre-built
    instances.  Calls to ``generate_structured_response`` return the
    matching fixture.  If no match is found, raises ``ValueError``.
    """

    def __init__(self, responses: dict[str, BaseModel] | None = None) -> None:
        self.responses = responses or {}
        self.call_log: list[dict] = []

    async def generate_structured_response(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ) -> T:
        self.call_log.append({
            "prompt": prompt[:200],
            "schema": response_schema.__name__,
            "temperature": temperature,
        })
        key = response_schema.__name__
        if key in self.responses:
            return self.responses[key]  # type: ignore[return-value]
        raise ValueError(f"MockLLMAdapter has no response for schema: {key}")

    async def generate_raw(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ) -> str:
        self.call_log.append({"prompt": prompt[:200], "schema": "raw"})
        return "mock raw response"


# ---------------------------------------------------------------------------
# Mock image adapter
# ---------------------------------------------------------------------------

_1X1_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


class MockImageAdapter(BaseImageAdapter):
    """Returns a 1x1 PNG for every request."""

    def __init__(self) -> None:
        self.call_log: list[dict] = []

    async def generate_panel_image(
        self,
        prompt: str,
        style_pack: StylePack,
        reference_images: list[str] | None = None,
        draft_mode: bool = True,
        aspect_ratio: str = "1:1",
    ) -> GeneratedImageResult:
        self.call_log.append({"prompt": prompt[:200], "draft": draft_mode})
        return GeneratedImageResult(
            image_bytes=_1X1_PNG,
            model_used="mock-model",
            generation_params={"mock": True},
        )

    async def generate_batch_images(
        self,
        prompts: list[str],
        style_pack: StylePack,
        reference_images: list[str] | None = None,
        draft_mode: bool = True,
    ) -> list[GeneratedImageResult]:
        return [
            await self.generate_panel_image(p, style_pack, reference_images, draft_mode)
            for p in prompts
        ]


# ---------------------------------------------------------------------------
# Reusable fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_character_bible() -> CharacterBible:
    return CharacterBible(characters=[
        CharacterProfile(
            name="Kai Tanaka",
            core_traits=["determined", "reckless", "loyal"],
            visual_description="Tall young man with spiky black hair, red headband, wearing a torn black jacket over a white t-shirt.",
            role="protagonist",
            age_range="17",
        ),
        CharacterProfile(
            name="Yuki Hoshino",
            core_traits=["intelligent", "calm", "mysterious"],
            visual_description="Slender woman with long silver hair, piercing blue eyes, wearing a dark blue coat and glasses.",
            role="antagonist",
            age_range="25",
        ),
        CharacterProfile(
            name="Old Man Chen",
            core_traits=["wise", "humorous"],
            visual_description="Short elderly man with a white beard, bald head, wearing traditional Chinese robes.",
            role="supporting",
            age_range="70",
        ),
    ])


@pytest.fixture
def sample_style_pack() -> StylePack:
    return StylePack(
        name="Shonen Bold",
        line_weight=0.60,
        contrast=0.75,
        screentone_density=0.35,
        panel_regularity=0.65,
        speed_line_intensity=0.65,
        background_detail=0.50,
        color_palette=["#0d0d0d", "#f2f2f2"],
        tone_keywords=["dynamic", "energetic", "shonen action manga"],
    )


@pytest.fixture
def sample_panel(sample_character_bible) -> PanelSpec:
    char_id = sample_character_bible.characters[0].character_id
    return PanelSpec(
        panel_index=0,
        shot_type=ShotType.MEDIUM_SHOT,
        camera_angle=CameraAngle.EYE_LEVEL,
        characters=[char_id],
        setting_description="A dimly lit alley in Neo-Tokyo.",
        action_description="Kai clenches his fist and stares ahead.",
        dialogue=[
            DialogueLine(
                character_id=char_id,
                text="I won't back down!",
                balloon_type="speech",
                reading_order=0,
            ),
        ],
        prompt_plan="Medium shot of a determined young man in a dark alley.",
    )


@pytest.fixture
def sample_episode_outline(sample_character_bible) -> EpisodeOutline:
    char_ids = [c.character_id for c in sample_character_bible.characters[:2]]
    return EpisodeOutline(
        episode_number=1,
        title="The First Encounter",
        logline="A reckless youth stumbles into a conspiracy bigger than he imagined.",
        scenes=[
            SceneOutline(
                title="Alley Chase",
                summary="Kai is pursued through dark alleys by mysterious agents.",
                location="Neo-Tokyo backstreets",
                characters_present=char_ids,
                emotional_beat="hook",
                page_range=(1, 2),
            ),
        ],
        target_page_count=4,
    )


@pytest.fixture
def mock_llm() -> MockLLMAdapter:
    return MockLLMAdapter()


@pytest.fixture
def mock_image() -> MockImageAdapter:
    return MockImageAdapter()
