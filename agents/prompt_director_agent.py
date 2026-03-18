"""
MangaZine — PromptDirectorAgent
================================
Responsibility: synthesising the definitive image-generation prompt for a panel.

This agent is intentionally **deterministic** — it requires no LLM call.
All rules are encoded as pure functions that combine structured data from
PanelSpec + StylePack + CharacterBible into a reproducible prompt string.

Output model: ``PromptPlan``
  A finalised prompt ready to be sent to Nano Banana 2
  (gemini-3.1-flash-image-preview).

Design principles
-----------------
1. Character injection FIRST — visual descriptions from CharacterBible are
   the highest-priority tokens; they define what must appear in the frame.
2. Cinematic direction SECOND — shot type + camera angle set the composition.
3. Action + setting THIRD — the narrative action grounds the composition.
4. Style suffix LAST — StylePack keywords condition the rendering aesthetic.
5. Negative prompt appended separately — passed to the model as a separate
   field, not embedded in the positive prompt.
"""

from __future__ import annotations

import logging
from uuid import UUID

from pydantic import BaseModel, Field

from models.schemas import (
    CameraAngle,
    CharacterBible,
    CharacterProfile,
    PanelSpec,
    ShotType,
    StylePack,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shot type → cinematographic direction
# ---------------------------------------------------------------------------

_SHOT_DIRECTIONS: dict[ShotType, str] = {
    ShotType.EXTREME_CLOSE_UP: (
        "extreme close-up shot — tight on face or detail, "
        "fills the entire frame, pores and textures visible"
    ),
    ShotType.CLOSE_UP: (
        "close-up shot — face or key object centered, "
        "chin to top of head framing"
    ),
    ShotType.MEDIUM_CLOSE_UP: (
        "medium close-up shot — chest-to-top-of-head framing, "
        "character expression dominant"
    ),
    ShotType.MEDIUM_SHOT: (
        "medium shot — waist-up framing, "
        "character and immediate environment balanced"
    ),
    ShotType.MEDIUM_WIDE: (
        "medium wide shot — full figure with clear environmental context"
    ),
    ShotType.WIDE_SHOT: (
        "wide establishing shot — characters small relative to environment, "
        "full location readable"
    ),
    ShotType.EXTREME_WIDE: (
        "extreme wide shot — characters tiny specks in vast environment, "
        "scale and isolation emphasised"
    ),
    ShotType.OVER_THE_SHOULDER: (
        "over-the-shoulder shot — foreground character's back occupies "
        "one-third of frame, subject visible beyond"
    ),
    ShotType.POV: (
        "point-of-view shot — first-person perspective, "
        "as if viewer is the character's eyes"
    ),
    ShotType.INSERT: (
        "insert cut-in shot — tight detail close-up, "
        "isolating a single object or action"
    ),
}

# ---------------------------------------------------------------------------
# Camera angle → angle descriptor
# ---------------------------------------------------------------------------

_ANGLE_DIRECTIONS: dict[CameraAngle, str] = {
    CameraAngle.EYE_LEVEL: "eye-level camera angle, neutral perspective",
    CameraAngle.LOW_ANGLE: (
        "low angle — camera below subject looking up, "
        "subject appears powerful and dominant"
    ),
    CameraAngle.HIGH_ANGLE: (
        "high angle — camera above subject looking down, "
        "subject appears vulnerable or surveyed"
    ),
    CameraAngle.BIRDS_EYE: (
        "bird's-eye view — directly overhead, "
        "top-down orthographic-style composition"
    ),
    CameraAngle.WORMS_EYE: (
        "worm's-eye view — extreme upward angle from ground level, "
        "dramatic foreshortening"
    ),
    CameraAngle.DUTCH_ANGLE: (
        "Dutch tilt — horizon line is diagonal, "
        "psychological tension, unease, or disorientation"
    ),
    CameraAngle.OVERHEAD: (
        "overhead shot — camera directly above, "
        "looking straight down at the action"
    ),
    CameraAngle.CANTED: (
        "canted angle — camera slightly rotated off-axis, "
        "subtle visual tension"
    ),
}

# ---------------------------------------------------------------------------
# StylePack → prompt suffix builder
# ---------------------------------------------------------------------------


def _build_style_suffix(style_pack: StylePack) -> str:
    """
    Convert ``StylePack`` numeric fields (all [0, 1]) and ``tone_keywords``
    into a comma-separated style suffix string.

    The resulting tags are appended at the END of the positive prompt so they
    condition the model's aesthetic without overriding the composition intent.
    """
    tags: list[str] = []

    # Line weight
    if style_pack.line_weight >= 0.75:
        tags.append("ultra-thick bold ink lines")
    elif style_pack.line_weight >= 0.55:
        tags.append("thick clean ink lines")
    elif style_pack.line_weight >= 0.35:
        tags.append("medium-weight ink lines")
    else:
        tags.append("fine hairline ink strokes")

    # Contrast
    if style_pack.contrast >= 0.75:
        tags.append("high contrast black and white")
    elif style_pack.contrast >= 0.50:
        tags.append("strong tonal contrast")
    elif style_pack.contrast >= 0.30:
        tags.append("moderate tonal range")
    else:
        tags.append("soft low-contrast tones")

    # Screentone density
    if style_pack.screentone_density >= 0.65:
        tags.append("heavy screentone and halftone fills")
    elif style_pack.screentone_density >= 0.35:
        tags.append("subtle screentone shading")
    elif style_pack.screentone_density > 0.0:
        tags.append("minimal screentone accents")

    # Panel border regularity (affects perceived style)
    if style_pack.panel_regularity <= 0.25:
        tags.append("organic broken panel borders")
    elif style_pack.panel_regularity >= 0.85:
        tags.append("rigid geometric panel borders")

    # Speed lines
    if style_pack.speed_line_intensity >= 0.65:
        tags.append("dramatic radiating speed lines")
    elif style_pack.speed_line_intensity >= 0.40:
        tags.append("subtle speed line accents")

    # Background detail
    if style_pack.background_detail >= 0.70:
        tags.append("highly detailed background rendering")
    elif style_pack.background_detail <= 0.25:
        tags.append("minimal stylised background, focus on characters")

    # Free-form tone keywords injected verbatim (highest specificity)
    tags.extend(style_pack.tone_keywords)

    # Invariant manga identity tag
    tags.append("manga panel illustration, professional comic book art")

    return ", ".join(tags)


# ---------------------------------------------------------------------------
# PromptPlan output model
# ---------------------------------------------------------------------------


class PromptPlan(BaseModel):
    """
    The definitive, ready-to-send image-generation prompt for a single panel.

    All fields are populated by ``PromptDirectorAgent.synthesize`` deterministically.
    """

    panel_id: str = Field(..., description="UUID of the source PanelSpec.")
    shot_type: str = Field(..., description="Shot type string for traceability.")
    camera_angle: str = Field(..., description="Camera angle string for traceability.")
    character_injections: list[str] = Field(
        default_factory=list,
        description=(
            "One entry per character present in the panel. "
            "Format: '{name}: {visual_description}'"
        ),
    )
    style_suffix: str = Field(
        ...,
        description="Comma-separated style tags derived from the StylePack.",
    )
    final_prompt: str = Field(
        ...,
        description=(
            "The complete, self-contained positive prompt ready to send "
            "to Nano Banana 2 (gemini-3.1-flash-image-preview)."
        ),
    )
    negative_prompt: str = Field(
        "",
        description=(
            "Negative prompt sourced from PanelSpec.render_refs.negative_prompt. "
            "Passed as a separate field to the image model, not embedded in final_prompt."
        ),
    )
    estimated_token_count: int = Field(
        0,
        description="Rough word-count estimate of final_prompt for budget tracking.",
    )


# ---------------------------------------------------------------------------
# PromptDirectorAgent
# ---------------------------------------------------------------------------


class PromptDirectorAgent:
    """
    Deterministic prompt synthesis agent.

    No LLM is required.  The ``synthesize`` method combines structured data
    from three sources — ``PanelSpec``, ``StylePack``, ``CharacterBible`` —
    following a strict injection order:

    1. **Cinematic direction** (shot type + camera angle)
    2. **Character injections** (visual descriptions from CharacterBible)
    3. **Action** (action_description)
    4. **Setting** (setting_description)
    5. **Panel prompt plan** (the LLM-generated or manually overridden plan)
    6. **Style suffix** (StylePack-derived tags)

    Usage::

        director = PromptDirectorAgent()
        plan = director.synthesize(panel, style_pack, character_bible)
        print(plan.final_prompt)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def synthesize(
        self,
        panel: PanelSpec,
        style_pack: StylePack,
        character_bible: CharacterBible,
    ) -> PromptPlan:
        """
        Build and return a ``PromptPlan`` for *panel*.

        Parameters
        ----------
        panel:
            The ``PanelSpec`` to render.
        style_pack:
            The project's master ``StylePack`` (or a panel-level override).
        character_bible:
            The canonical character roster used to look up visual descriptions.

        Returns
        -------
        PromptPlan
            Ready-to-send prompt with all injections applied.
        """
        # 1. Cinematic direction
        cinematic = self._build_cinematic_direction(panel.shot_type, panel.camera_angle)

        # 2. Character injections
        char_injections, char_block = self._build_character_block(
            panel.characters, character_bible
        )

        # 3. Action + setting
        action_block = self._build_action_block(
            panel.action_description, panel.setting_description
        )

        # 4. Panel-level prompt plan (may be empty on first pass)
        prompt_plan_block = panel.prompt_plan.strip() if panel.prompt_plan else ""

        # 5. Style suffix
        style_suffix = _build_style_suffix(style_pack)

        # 6. Assemble final prompt
        segments: list[str] = []

        if cinematic:
            segments.append(cinematic)
        if char_block:
            segments.append(char_block)
        if action_block:
            segments.append(action_block)
        if prompt_plan_block:
            segments.append(prompt_plan_block)
        if style_suffix:
            segments.append(style_suffix)

        final_prompt = ".  ".join(s.rstrip(".") for s in segments if s)

        # 7. Negative prompt from render_refs
        negative_prompt = panel.render_refs.negative_prompt or ""

        plan = PromptPlan(
            panel_id=str(panel.panel_id),
            shot_type=panel.shot_type.value,
            camera_angle=panel.camera_angle.value,
            character_injections=char_injections,
            style_suffix=style_suffix,
            final_prompt=final_prompt,
            negative_prompt=negative_prompt,
            estimated_token_count=len(final_prompt.split()),
        )

        logger.debug(
            "[PromptDirectorAgent] Panel %s — %d tokens estimated — %d characters injected",
            panel.panel_id,
            plan.estimated_token_count,
            len(char_injections),
        )

        return plan

    def batch_synthesize(
        self,
        panels: list[PanelSpec],
        style_pack: StylePack,
        character_bible: CharacterBible,
    ) -> list[PromptPlan]:
        """
        Convenience method: synthesise ``PromptPlan`` for every panel in *panels*.

        Returns plans in the same order as *panels*.
        """
        return [self.synthesize(p, style_pack, character_bible) for p in panels]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_cinematic_direction(shot_type: ShotType, camera_angle: CameraAngle) -> str:
        """Combine shot type and camera angle into a cinematographic direction clause."""
        shot_dir = _SHOT_DIRECTIONS.get(shot_type, shot_type.value.replace("_", " "))
        angle_dir = _ANGLE_DIRECTIONS.get(camera_angle, camera_angle.value.replace("_", " "))
        return f"{shot_dir}, {angle_dir}"

    @staticmethod
    def _build_character_block(
        character_ids: list[UUID],
        character_bible: CharacterBible,
    ) -> tuple[list[str], str]:
        """
        Look up each character in *character_ids* from *character_bible* and
        build a rich injection block.

        Returns
        -------
        tuple[list[str], str]
            - list of ``"{name}: {visual_description}"`` strings (one per character)
            - single combined block string for prompt injection
        """
        injections: list[str] = []
        missing: list[str] = []

        for cid in character_ids:
            char: CharacterProfile | None = character_bible.get_by_id(cid)
            if char is None:
                missing.append(str(cid))
                logger.warning(
                    "[PromptDirectorAgent] Character UUID %s not found in CharacterBible",
                    cid,
                )
                continue
            injections.append(f"{char.name}: {char.visual_description}")

        if missing:
            logger.warning(
                "[PromptDirectorAgent] %d character(s) not resolved: %s",
                len(missing),
                ", ".join(missing),
            )

        if not injections:
            return [], ""

        if len(injections) == 1:
            block = f"Character in frame — {injections[0]}"
        else:
            lines = "\n".join(f"  • {inj}" for inj in injections)
            block = f"Characters in frame —\n{lines}"

        return injections, block

    @staticmethod
    def _build_action_block(
        action_description: str,
        setting_description: str,
    ) -> str:
        """Merge action and setting into a single compositional narrative clause."""
        parts: list[str] = []
        if action_description.strip():
            parts.append(action_description.strip())
        if setting_description.strip():
            parts.append(f"Setting: {setting_description.strip()}")
        return ".  ".join(parts)
