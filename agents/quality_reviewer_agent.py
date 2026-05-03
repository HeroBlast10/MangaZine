"""
MangaZine — QualityReviewerAgent
=================================
Responsibility: post-generation quality gate.

Uses a Vision-capable LLM to evaluate generated panel images against
the project's CharacterBible and StylePack.  Produces a structured
``QualityReport`` with per-dimension scores and an overall pass/fail
decision.

Pipeline position:
  ImageAdapter output ──► QualityReviewerAgent.review()
                      ──► QualityReport (pass / fail)
                      ──► [Retry with refined prompt if below threshold]
"""

from __future__ import annotations

import base64
import logging
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from adapters.base import BaseLLMAdapter
from models.schemas import CharacterBible, PanelSpec, StylePack

logger = logging.getLogger(__name__)

_QUALITY_THRESHOLD = 6  # overall_score >= this = PASS
_MAX_AUTO_RETRIES = 1


# ---------------------------------------------------------------------------
# Quality report models
# ---------------------------------------------------------------------------


class DimensionScore(BaseModel):
    """Score for a single quality dimension."""

    dimension: str = Field(..., description="Name of the quality dimension.")
    score: int = Field(..., ge=1, le=10, description="1-10 score.")
    feedback: str = Field("", description="Specific feedback for this dimension.")


class QualityReport(BaseModel):
    """Structured quality assessment of a generated panel image."""

    panel_id: str = Field(..., description="UUID of the assessed panel.")
    overall_score: int = Field(
        ...,
        ge=1,
        le=10,
        description="Overall quality score (1 = unacceptable, 10 = publication-ready).",
    )
    passed: bool = Field(
        ...,
        description=f"True when overall_score >= {_QUALITY_THRESHOLD}.",
    )
    dimension_scores: list[DimensionScore] = Field(
        default_factory=list,
        description="Per-dimension breakdown.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Specific issues identified in the image.",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Actionable suggestions for prompt refinement.",
    )
    prompt_refinement: str = Field(
        "",
        description="Suggested prompt adjustment to fix identified issues.",
    )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_QUALITY_REVIEWER = (
    "You are an expert manga art director and quality control specialist. "
    "You evaluate generated manga panel images against precise specifications. "
    "Be specific, actionable, and fair. Focus on what matters for print-quality manga."
)

_PROMPT_REVIEW = """\
Evaluate this generated manga panel image against the following specifications.

Panel Specification:
- Shot type: {shot_type}
- Camera angle: {camera_angle}
- Action: {action_description}
- Setting: {setting_description}
- Characters expected: {character_names}

Character Descriptions (from CharacterBible):
{character_descriptions}

Style Requirements:
- Style: {style_name}
- Tone keywords: {tone_keywords}

Score each dimension 1-10:
1. **character_consistency**: Do the characters match their descriptions?
2. **composition_accuracy**: Does the shot type and camera angle match the spec?
3. **style_adherence**: Does the art style match the StylePack requirements?
4. **technical_quality**: Is the image free of artifacts, distortions, extra limbs?
5. **narrative_clarity**: Does the image clearly convey the intended action/emotion?

Return a QualityReport JSON with:
- overall_score: weighted average (1-10)
- passed: true if overall_score >= {threshold}
- dimension_scores: list of dimension name + score + feedback
- issues: list of specific problems found
- suggestions: actionable fixes
- prompt_refinement: a revised prompt fragment that addresses the issues
"""


# ---------------------------------------------------------------------------
# QualityReviewerAgent
# ---------------------------------------------------------------------------


class QualityReviewerAgent:
    """
    Post-generation quality gate agent.

    Evaluates a generated panel image using a Vision LLM and returns
    a ``QualityReport``.  If the image does not pass, the report
    includes a ``prompt_refinement`` suggestion for the next attempt.

    Usage::

        reviewer = QualityReviewerAgent(llm=vision_llm)
        report = await reviewer.review(panel, image_bytes, bible, style)
        if not report.passed:
            # use report.prompt_refinement for retry
    """

    def __init__(self, llm: BaseLLMAdapter) -> None:
        self._llm = llm

    async def review(
        self,
        panel: PanelSpec,
        image_bytes: bytes,
        character_bible: CharacterBible,
        style_pack: StylePack,
    ) -> QualityReport:
        """
        Evaluate *image_bytes* against the panel spec, characters, and style.

        Parameters
        ----------
        panel : PanelSpec
            The panel specification the image was generated from.
        image_bytes : bytes
            Raw PNG/JPEG bytes of the generated image.
        character_bible : CharacterBible
            Character roster for consistency checking.
        style_pack : StylePack
            Expected visual style parameters.

        Returns
        -------
        QualityReport
            Structured quality assessment with pass/fail and suggestions.
        """
        char_names: list[str] = []
        char_descs: list[str] = []
        for cid in panel.characters:
            char = character_bible.get_by_id(cid)
            if char:
                char_names.append(char.name)
                char_descs.append(f"- {char.name}: {char.visual_description}")

        prompt = _PROMPT_REVIEW.format(
            shot_type=panel.shot_type.value,
            camera_angle=panel.camera_angle.value,
            action_description=panel.action_description,
            setting_description=panel.setting_description,
            character_names=", ".join(char_names) if char_names else "None",
            character_descriptions="\n".join(char_descs) if char_descs else "No characters specified",
            style_name=style_pack.name,
            tone_keywords=", ".join(style_pack.tone_keywords),
            threshold=_QUALITY_THRESHOLD,
        )

        try:
            report: QualityReport = await self._llm.generate_structured_response(
                prompt=prompt,
                response_schema=QualityReport,
                system_instruction=_SYSTEM_QUALITY_REVIEWER,
                temperature=0.30,
            )
            report.panel_id = str(panel.panel_id)
            report.passed = report.overall_score >= _QUALITY_THRESHOLD

            logger.info(
                "[QualityReviewer] Panel %s — score: %d/10, passed: %s, issues: %d",
                panel.panel_id,
                report.overall_score,
                report.passed,
                len(report.issues),
            )
            return report

        except Exception as exc:
            logger.warning(
                "[QualityReviewer] Review failed for panel %s: %s — defaulting to pass",
                panel.panel_id,
                exc,
            )
            return QualityReport(
                panel_id=str(panel.panel_id),
                overall_score=_QUALITY_THRESHOLD,
                passed=True,
                issues=[f"Quality review failed: {exc}"],
            )

    async def review_and_retry(
        self,
        panel: PanelSpec,
        image_bytes: bytes,
        character_bible: CharacterBible,
        style_pack: StylePack,
        image_adapter,
        max_retries: int = _MAX_AUTO_RETRIES,
    ) -> tuple[QualityReport, bytes]:
        """
        Review an image and automatically retry generation if quality is below
        threshold, using the ``prompt_refinement`` from the quality report.

        Returns the final (report, image_bytes) pair.
        """
        current_bytes = image_bytes
        report = await self.review(panel, current_bytes, character_bible, style_pack)

        for attempt in range(max_retries):
            if report.passed:
                break

            logger.info(
                "[QualityReviewer] Auto-retry %d/%d for panel %s (score: %d)",
                attempt + 1, max_retries, panel.panel_id, report.overall_score,
            )

            refined_prompt = panel.prompt_plan
            if report.prompt_refinement:
                refined_prompt = f"{refined_prompt}. {report.prompt_refinement}"

            try:
                result = await image_adapter.generate_panel_image(
                    prompt=refined_prompt,
                    style_pack=style_pack,
                    draft_mode=True,
                    aspect_ratio="2:3",
                )
                current_bytes = result.image_bytes
                report = await self.review(panel, current_bytes, character_bible, style_pack)
            except Exception as exc:
                logger.warning("[QualityReviewer] Retry failed: %s", exc)
                break

        return report, current_bytes
