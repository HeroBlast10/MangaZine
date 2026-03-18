"""
MangaZine — StoryboarderAgent
==============================
Responsibility: pacing, layout, and visual rhythm.

Pipeline:
  WriterAgentOutput ──► PageSpec (panels with shot types, dialogue, prompt_plans)
                    ──► VisualRhythmCheck  (deterministic — no LLM)
                    ──► [Revise ×N]        (if wide_shot count exceeds threshold)
                    ──► StoryboarderOutput

Visual Rhythm Constraint
------------------------
A single page MUST NOT contain more than ``MAX_WIDE_SHOTS_PER_PAGE`` panels
whose ``shot_type`` is ``wide_shot`` or ``extreme_wide``.  Violating this
flattens visual tension; the agent auto-corrects by requesting closer framings.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from adapters.llm_adapter import LLMAdapter
from agents.writer_agent import DialogueDraft, WriterAgentOutput
from models.schemas import (
    CameraAngle,
    CharacterBible,
    EpisodeOutline,
    PageSpec,
    ShotType,
)

logger = logging.getLogger(__name__)

MAX_WIDE_SHOTS_PER_PAGE: int = 1
_MAX_RHYTHM_RETRIES: int = 2

# ---------------------------------------------------------------------------
# Internal data models
# ---------------------------------------------------------------------------


class ShotRhythmIssue(BaseModel):
    """A single visual-rhythm violation on a page."""

    panel_index: int = Field(..., description="Zero-based panel index that violates the rule.")
    current_shot_type: str = Field(..., description="The problematic shot type string.")
    suggested_shot_type: str = Field(
        ...,
        description="Recommended replacement shot type for better visual rhythm.",
    )
    reason: str = Field(..., description="Explanation of why this change improves the page.")


class VisualRhythmReport(BaseModel):
    """Result of the deterministic visual-rhythm validation pass."""

    is_approved: bool = Field(..., description="True when the page passes all rhythm checks.")
    wide_shot_count: int = Field(..., description="Total wide_shot + extreme_wide panels found.")
    issues: list[ShotRhythmIssue] = Field(
        default_factory=list,
        description="Specific panels that need reframing.",
    )
    revision_instructions: str = Field(
        "",
        description="Human-readable rewrite instructions passed back to the LLM.",
    )


class StoryboarderOutput(BaseModel):
    """Final deliverable from the StoryboarderAgent."""

    page: PageSpec = Field(..., description="Fully broken-down page with panels.")
    rhythm_check_rounds: int = Field(
        0,
        description="Number of visual-rhythm correction rounds required.",
    )
    final_rhythm_report: VisualRhythmReport | None = Field(
        None,
        description="The last VisualRhythmReport produced (None if first pass passed).",
    )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_STORYBOARDER = (
    "You are a master manga storyboarder and visual pacing specialist. "
    "You think in shots, cuts, and reading rhythms. "
    "You understand that visual variety is not optional — a page of identical framings is dead on the page. "
    f"CRITICAL RULE: You NEVER place more than {MAX_WIDE_SHOTS_PER_PAGE} wide_shot or "
    "extreme_wide panel on a single page. "
    "Vary shot sizes: mix ECU, CU, MS, and WS to create cinematic tension and visual flow. "
    "Do NOT generate UUID / ID fields — they are auto-assigned by the system."
)

_PROMPT_STORYBOARD = """\
Break down page {page_number} of this manga episode into exactly {panel_count} panels.

Episode Outline:
{outline_json}

Dialogue Draft (use these lines; distribute them across appropriate panels):
{dialogue_json}

Character ID → Name mapping (use EXACT UUID strings in panel.characters and dialogue.character_id):
{char_id_list}

Requirements for the PageSpec:
- page_number   : {page_number}
- layout.layout_type : "{layout_type}"
- panels        : exactly {panel_count} PanelSpec objects, panel_index 0–{max_index}

For EACH panel:
  • panel_index          : sequential, starting at 0
  • shot_type            : one of [{shot_type_list}]
                           — VARY THEM. Do not repeat the same shot type more than twice.
                           — Use at most {max_wide} wide_shot or extreme_wide on this whole page.
  • camera_angle         : one of [{angle_list}]
  • characters           : list of character_id UUID strings from the mapping above
  • setting_description  : vivid one-sentence environment description
  • action_description   : what physically happens in this panel
  • dialogue             : 0–2 DialogueLine objects drawn from the Dialogue Draft
      – text          : exact text from the draft (may be trimmed for space)
      – balloon_type  : matching balloon_type from draft
      – reading_order : 0-indexed within the panel
      – character_id  : EXACT UUID string of the speaker
  • prompt_plan          : detailed self-contained image-generation prompt for this panel

- Do NOT include: page_id, panel_id, render_refs, render_output.
"""

_PROMPT_RHYTHM_REVISION = """\
Your previous PageSpec for page {page_number} had {wide_count} wide/extreme-wide shot(s),
exceeding the maximum of {max_wide}.

Visual Rhythm Issues:
{issues_json}

Revision Instructions:
{revision_instructions}

Original PageSpec:
{page_json}

Character ID → Name mapping:
{char_id_list}

Please produce a corrected PageSpec that:
1. Changes ONLY the flagged panels to the suggested shot types.
2. Keeps all other panels, dialogue, and prompt_plans unchanged.
3. Obeys the rule: at most {max_wide} wide_shot or extreme_wide per page.
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WIDE_SHOT_TYPES: frozenset[ShotType] = frozenset(
    {ShotType.WIDE_SHOT, ShotType.EXTREME_WIDE}
)

_CLOSER_ALTERNATIVES: list[str] = [
    ShotType.MEDIUM_SHOT.value,
    ShotType.MEDIUM_CLOSE_UP.value,
    ShotType.CLOSE_UP.value,
    ShotType.OVER_THE_SHOULDER.value,
]


def _check_visual_rhythm(
    page: PageSpec,
    max_wide: int = MAX_WIDE_SHOTS_PER_PAGE,
) -> VisualRhythmReport:
    """
    Deterministic visual-rhythm validation — no LLM involved.

    Counts ``wide_shot`` and ``extreme_wide`` panels on *page*.
    If the count exceeds *max_wide*, returns a ``VisualRhythmReport``
    with ``is_approved=False`` and per-panel correction suggestions.
    """
    wide_panels = [p for p in page.panels if p.shot_type in _WIDE_SHOT_TYPES]
    wide_count = len(wide_panels)

    if wide_count <= max_wide:
        return VisualRhythmReport(is_approved=True, wide_shot_count=wide_count)

    # Build per-panel issues for the excess wide shots (keep the first one)
    issues: list[ShotRhythmIssue] = []
    for panel in wide_panels[max_wide:]:
        # Suggest a closer alternative that isn't already heavily used on this page
        used_types = {p.shot_type.value for p in page.panels}
        suggestion = next(
            (s for s in _CLOSER_ALTERNATIVES if s not in used_types),
            ShotType.MEDIUM_SHOT.value,
        )
        issues.append(
            ShotRhythmIssue(
                panel_index=panel.panel_index,
                current_shot_type=panel.shot_type.value,
                suggested_shot_type=suggestion,
                reason=(
                    f"Page already has {wide_count} wide/extreme-wide shots "
                    f"(max {max_wide}). Switching to '{suggestion}' adds "
                    "close-up tension and breaks the visual monotony."
                ),
            )
        )

    problem_indices = [i.panel_index for i in issues]
    revision_instructions = (
        f"Page {page.page_number} has {wide_count} wide/extreme-wide shots, "
        f"but the maximum is {max_wide}. "
        f"Change panel(s) {problem_indices} to closer framings "
        f"({', '.join(i.suggested_shot_type for i in issues)}) "
        "to restore visual rhythm. Keep all other panel content identical."
    )

    return VisualRhythmReport(
        is_approved=False,
        wide_shot_count=wide_count,
        issues=issues,
        revision_instructions=revision_instructions,
    )


def _build_char_id_list(bible: CharacterBible) -> str:
    return "\n".join(
        f"  {c.character_id}  →  {c.name}  ({c.role or 'N/A'})"
        for c in bible.characters
    )


def _shot_type_list() -> str:
    return ", ".join(s.value for s in ShotType)


def _angle_list() -> str:
    return ", ".join(a.value for a in CameraAngle)


# ---------------------------------------------------------------------------
# StoryboarderAgent
# ---------------------------------------------------------------------------


class StoryboarderAgent:
    """
    Visual pacing and layout agent.

    Takes the ``WriterAgentOutput`` and converts the narrative into
    ``PageSpec`` objects with precise panel breakdowns, shot types,
    and dialogue assignments.

    The built-in ``_check_visual_rhythm`` validator enforces that no
    single page exceeds ``MAX_WIDE_SHOTS_PER_PAGE`` wide / extreme-wide
    panels.  When violated, the agent re-prompts the LLM with explicit
    correction instructions (up to ``_MAX_RHYTHM_RETRIES`` times).

    Usage::

        agent = StoryboarderAgent(llm=LLMAdapter())
        output = await agent.run(writer_output, page_number=1, panel_count=4)
    """

    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        writer_output: WriterAgentOutput,
        page_number: int = 1,
        panel_count: int = 4,
        layout_type: str = "tier_stack",
    ) -> StoryboarderOutput:
        """
        Produce a ``StoryboarderOutput`` for *page_number*.

        Parameters
        ----------
        writer_output:
            The full output from ``WriterAgent.run()``.
        page_number:
            One-based page number to storyboard.
        panel_count:
            Target number of panels for this page (4–6 recommended).
        layout_type:
            CSS grid layout preset (see ``LayoutType`` enum).
        """
        logger.info(
            "[StoryboarderAgent] Starting — page %d, %d panels, layout: %s",
            page_number,
            panel_count,
            layout_type,
        )

        bible = writer_output.character_bible
        outline = writer_output.episode_outline
        dialogue = writer_output.dialogue_draft
        char_id_list = _build_char_id_list(bible)

        # Step 1: Initial storyboard
        page = await self._generate_page(
            outline=outline,
            dialogue=dialogue,
            char_id_list=char_id_list,
            page_number=page_number,
            panel_count=panel_count,
            layout_type=layout_type,
        )
        logger.info(
            "[StoryboarderAgent] Initial storyboard done — %d panels generated",
            len(page.panels),
        )

        # Step 2: Visual rhythm correction loop
        rhythm_report: VisualRhythmReport | None = None
        rhythm_rounds = 0

        for attempt in range(1, _MAX_RHYTHM_RETRIES + 1):
            report = _check_visual_rhythm(page)
            logger.info(
                "[StoryboarderAgent] Rhythm check (attempt %d) — wide shots: %d — approved: %s",
                attempt,
                report.wide_shot_count,
                report.is_approved,
            )

            if report.is_approved:
                break

            rhythm_report = report
            rhythm_rounds += 1

            if attempt < _MAX_RHYTHM_RETRIES:
                logger.info(
                    "[StoryboarderAgent] Rhythm violation — revising %d panel(s)…",
                    len(report.issues),
                )
                page = await self._revise_rhythm(
                    page=page,
                    report=report,
                    char_id_list=char_id_list,
                )
            else:
                logger.warning(
                    "[StoryboarderAgent] Rhythm constraint still violated after %d retries "
                    "(wide shots: %d). Proceeding with best draft.",
                    _MAX_RHYTHM_RETRIES,
                    report.wide_shot_count,
                )

        logger.info(
            "[StoryboarderAgent] Complete — %d panel(s), %d rhythm correction round(s).",
            len(page.panels),
            rhythm_rounds,
        )

        return StoryboarderOutput(
            page=page,
            rhythm_check_rounds=rhythm_rounds,
            final_rhythm_report=rhythm_report,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _generate_page(
        self,
        outline: EpisodeOutline,
        dialogue: DialogueDraft,
        char_id_list: str,
        page_number: int,
        panel_count: int,
        layout_type: str,
    ) -> PageSpec:
        return await self._llm.generate_structured_response(
            prompt=_PROMPT_STORYBOARD.format(
                page_number=page_number,
                panel_count=panel_count,
                outline_json=outline.model_dump_json(indent=2),
                dialogue_json=dialogue.model_dump_json(indent=2),
                char_id_list=char_id_list,
                layout_type=layout_type,
                max_index=panel_count - 1,
                shot_type_list=_shot_type_list(),
                angle_list=_angle_list(),
                max_wide=MAX_WIDE_SHOTS_PER_PAGE,
            ),
            response_schema=PageSpec,
            system_instruction=_SYSTEM_STORYBOARDER,
            temperature=0.65,
        )

    async def _revise_rhythm(
        self,
        page: PageSpec,
        report: VisualRhythmReport,
        char_id_list: str,
    ) -> PageSpec:
        return await self._llm.generate_structured_response(
            prompt=_PROMPT_RHYTHM_REVISION.format(
                page_number=page.page_number,
                wide_count=report.wide_shot_count,
                max_wide=MAX_WIDE_SHOTS_PER_PAGE,
                issues_json=report.model_dump_json(indent=2),
                revision_instructions=report.revision_instructions,
                page_json=page.model_dump_json(indent=2),
                char_id_list=char_id_list,
            ),
            response_schema=PageSpec,
            system_instruction=_SYSTEM_STORYBOARDER,
            temperature=0.50,  # low temperature for surgical corrections
        )
