"""
Tests for PromptDirectorAgent — fully deterministic, 100% testable.

The PromptDirectorAgent requires NO LLM: it's a pure function that
combines PanelSpec + StylePack + CharacterBible into a prompt string.
"""

import pytest

from agents.prompt_director_agent import PromptDirectorAgent, PromptPlan
from models.schemas import (
    CameraAngle,
    CharacterBible,
    PanelSpec,
    ShotType,
    StylePack,
)


@pytest.fixture
def director():
    return PromptDirectorAgent()


class TestSynthesize:
    def test_returns_prompt_plan(self, director, sample_panel, sample_style_pack, sample_character_bible):
        plan = director.synthesize(sample_panel, sample_style_pack, sample_character_bible)
        assert isinstance(plan, PromptPlan)
        assert plan.panel_id == str(sample_panel.panel_id)
        assert plan.shot_type == sample_panel.shot_type.value
        assert plan.camera_angle == sample_panel.camera_angle.value

    def test_contains_character_injection(self, director, sample_panel, sample_style_pack, sample_character_bible):
        plan = director.synthesize(sample_panel, sample_style_pack, sample_character_bible)
        assert len(plan.character_injections) == 1
        assert "Kai Tanaka" in plan.character_injections[0]

    def test_final_prompt_not_empty(self, director, sample_panel, sample_style_pack, sample_character_bible):
        plan = director.synthesize(sample_panel, sample_style_pack, sample_character_bible)
        assert len(plan.final_prompt) > 50

    def test_style_suffix_contains_tone_keywords(self, director, sample_panel, sample_style_pack, sample_character_bible):
        plan = director.synthesize(sample_panel, sample_style_pack, sample_character_bible)
        assert "dynamic" in plan.style_suffix
        assert "energetic" in plan.style_suffix

    def test_estimated_token_count_positive(self, director, sample_panel, sample_style_pack, sample_character_bible):
        plan = director.synthesize(sample_panel, sample_style_pack, sample_character_bible)
        assert plan.estimated_token_count > 0

    def test_no_characters_in_panel(self, director, sample_style_pack, sample_character_bible):
        panel = PanelSpec(
            panel_index=0,
            shot_type=ShotType.WIDE_SHOT,
            camera_angle=CameraAngle.BIRDS_EYE,
            characters=[],
            setting_description="A vast ocean under stormy skies.",
            action_description="Waves crash against the rocky shore.",
            prompt_plan="Wide establishing shot of a stormy ocean.",
        )
        plan = director.synthesize(panel, sample_style_pack, sample_character_bible)
        assert len(plan.character_injections) == 0
        assert "stormy" in plan.final_prompt.lower() or "ocean" in plan.final_prompt.lower()

    def test_shot_type_in_final_prompt(self, director, sample_panel, sample_style_pack, sample_character_bible):
        plan = director.synthesize(sample_panel, sample_style_pack, sample_character_bible)
        assert "medium shot" in plan.final_prompt.lower()

    def test_camera_angle_in_final_prompt(self, director, sample_panel, sample_style_pack, sample_character_bible):
        plan = director.synthesize(sample_panel, sample_style_pack, sample_character_bible)
        assert "eye-level" in plan.final_prompt.lower()


class TestBatchSynthesize:
    def test_returns_list(self, director, sample_panel, sample_style_pack, sample_character_bible):
        panels = [sample_panel, sample_panel]
        plans = director.batch_synthesize(panels, sample_style_pack, sample_character_bible)
        assert len(plans) == 2
        assert all(isinstance(p, PromptPlan) for p in plans)

    def test_empty_list(self, director, sample_style_pack, sample_character_bible):
        plans = director.batch_synthesize([], sample_style_pack, sample_character_bible)
        assert plans == []


class TestStyleSuffix:
    def test_high_contrast_style(self, director, sample_panel, sample_character_bible):
        style = StylePack(
            name="Noir",
            line_weight=0.80,
            contrast=0.95,
            screentone_density=0.70,
            panel_regularity=0.20,
            speed_line_intensity=0.70,
            background_detail=0.80,
            tone_keywords=["dark", "moody"],
        )
        plan = director.synthesize(sample_panel, style, sample_character_bible)
        assert "high contrast" in plan.style_suffix.lower()
        assert "bold" in plan.style_suffix.lower()

    def test_minimal_style(self, director, sample_panel, sample_character_bible):
        style = StylePack(
            name="Minimal",
            line_weight=0.20,
            contrast=0.20,
            screentone_density=0.05,
            panel_regularity=0.50,
            speed_line_intensity=0.10,
            background_detail=0.15,
            tone_keywords=["clean"],
        )
        plan = director.synthesize(sample_panel, style, sample_character_bible)
        assert "hairline" in plan.style_suffix.lower() or "fine" in plan.style_suffix.lower()
