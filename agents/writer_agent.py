"""
MangaZine — WriterAgent
=======================
Responsibility: narrative generation.

Pipeline:
  premise ──► CharacterBible
           ──► EpisodeOutline (with scene summaries)
           ──► DialogueDraft  (beat-level dialogue per scene)
           ──► CriticReview   (narrative pacing analysis)
           ──► [Revise ×N]    (if critic score < threshold)
           ──► WriterAgentOutput
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from adapters.base import BaseLLMAdapter, LLMAdapterError
from models.schemas import CharacterBible, EpisodeOutline, StylePack

logger = logging.getLogger(__name__)

_MAX_CRITIC_ROUNDS: int = 2
_CRITIC_APPROVAL_THRESHOLD: int = 7  # score ≥ 7 out of 10 = approved

# ---------------------------------------------------------------------------
# Internal data models
# ---------------------------------------------------------------------------


class DialogueDraftLine(BaseModel):
    """A single dialogue beat written at the scene level (pre-panel breakdown)."""

    scene_index: int = Field(
        ...,
        ge=0,
        description="Zero-based index of the scene this line belongs to.",
    )
    beat_index: int = Field(
        ...,
        ge=0,
        description="Reading-order index of this line within its scene.",
    )
    character_name: str = Field(
        ...,
        description="Speaker's canonical name (resolved to a UUID by the Storyboarder).",
    )
    text: str = Field(
        ...,
        description="Verbatim dialogue or narration text.",
    )
    balloon_type: str = Field(
        "speech",
        description="Balloon style: speech | thought | caption | sfx | whisper.",
    )
    delivery_note: str | None = Field(
        None,
        description="Optional acting direction, e.g. 'screaming', 'sotto voce'.",
    )


class DialogueDraft(BaseModel):
    """Scene-level dialogue beats produced by the WriterAgent."""

    episode_title: str = Field(..., description="Episode title.")
    lines: list[DialogueDraftLine] = Field(
        default_factory=list,
        description="All dialogue lines ordered by scene then beat.",
    )
    tone_notes: str = Field(
        "",
        description="Writer's global tone / style direction for this episode.",
    )


class NarrativePacingIssue(BaseModel):
    """A single pacing problem identified by the Critic."""

    scene_index: int = Field(..., description="Zero-based scene index.")
    issue_type: Literal[
        "too_rushed",
        "too_slow",
        "weak_emotional_beat",
        "pacing_mismatch",
        "missing_conflict",
        "tone_inconsistency",
        "under_characterised",
    ] = Field(..., description="Category of pacing issue.")
    description: str = Field(..., description="Precise explanation of the problem.")
    suggestion: str = Field(..., description="Concrete suggestion for improvement.")


class CriticFeedback(BaseModel):
    """Structured narrative-pacing critique returned by the Critic sub-routine."""

    overall_score: int = Field(
        ...,
        ge=1,
        le=10,
        description="Overall narrative quality score (1 = unusable, 10 = excellent).",
    )
    is_approved: bool = Field(
        ...,
        description=f"True when overall_score >= {_CRITIC_APPROVAL_THRESHOLD}.",
    )
    pacing_issues: list[NarrativePacingIssue] = Field(
        default_factory=list,
        description="List of identified pacing problems (empty if approved).",
    )
    general_feedback: str = Field(
        ...,
        description="1-3 sentence summary judgement of the outline.",
    )
    revision_instructions: str = Field(
        "",
        description="Concrete, actionable rewrite directions for the Writer.",
    )


class WriterAgentOutput(BaseModel):
    """Final deliverable from the WriterAgent passed to the StoryboarderAgent."""

    character_bible: CharacterBible = Field(
        ...,
        description="Canonical character roster with UUIDs.",
    )
    episode_outline: EpisodeOutline = Field(
        ...,
        description="Narrative blueprint approved by the Critic.",
    )
    dialogue_draft: DialogueDraft = Field(
        ...,
        description="Beat-level dialogue for every scene.",
    )
    critic_rounds_taken: int = Field(
        0,
        description="Number of revision rounds the Critic triggered.",
    )
    final_critic_score: int = Field(
        0,
        description="Critic's final overall_score (0 if no critic round ran).",
    )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_WRITER = (
    "You are an award-winning manga script writer. "
    "You craft vivid characters, tight narrative pacing, and emotionally resonant scene structures. "
    "You think in terms of visual storytelling: every scene should be translatable into a panel layout. "
    "Do NOT generate UUID / ID fields — they are auto-assigned by the system."
)

_SYSTEM_CRITIC = (
    "You are a ruthless but constructive manga editor. "
    "Your sole responsibility is to assess narrative pacing, emotional rhythm, and structural integrity. "
    "Be specific and actionable. Judge against professional manga standards."
)

_PROMPT_BIBLE = """\
Create a CharacterBible for a manga based on this premise:

"{premise}"

Instructions:
- Include exactly 2 main characters and 1 supporting character (3 total).
- For each character provide:
    • name              — memorable, genre-appropriate
    • core_traits       — list of 3–5 personality keywords
    • visual_description — 2–3 sentences for image generation (appearance, clothing, features)
    • role              — "protagonist" | "antagonist" | "supporting"
    • age_range         — approximate age string, e.g. "24"
- Do NOT include: character_id, aliases, reference_image_urls, notes.
"""

_PROMPT_OUTLINE = """\
Create an EpisodeOutline for Episode 1 of this manga.

Premise: "{premise}"

CharacterBible:
{bible_json}

Instructions:
- episode_number   : 1
- title            : a compelling, genre-fitting title
- logline          : one-sentence hook capturing the core conflict
- scenes           : 2–4 scenes. For each scene:
    • title        : short scene title
    • summary      : 2–3 sentence vivid description of what happens
    • location     : specific named setting
    • emotional_beat : core dramatic function of this scene (e.g. "hook", "rising tension",
                       "confrontation", "reversal", "cliffhanger")
    • characters_present : list of character_id UUIDs from the CharacterBible above
- target_page_count : 8
- Do NOT include: episode_id, pages, created_at, updated_at.
"""

_PROMPT_DIALOGUE = """\
Write a beat-level dialogue draft for this manga episode.

Episode Outline:
{outline_json}

CharacterBible:
{bible_json}

Instructions:
- Write dialogue for EVERY scene in the outline.
- For each DialogueDraftLine:
    • scene_index      : zero-based index matching the scene order above
    • beat_index       : zero-based reading order within the scene
    • character_name   : exact name from CharacterBible (no UUIDs at this stage)
    • text             : punchy, character-voice-appropriate dialogue
    • balloon_type     : "speech" | "thought" | "caption" | "sfx" | "whisper"
    • delivery_note    : optional acting direction (keep very brief)
- Each scene should have 3–6 dialogue beats.
- tone_notes : your overall direction for delivery, e.g. "sardonic, fast-paced, terse"
"""

_PROMPT_CRITIC = """\
Review the following manga episode outline and dialogue draft for narrative pacing.

Premise: "{premise}"

Episode Outline:
{outline_json}

Dialogue Draft:
{dialogue_json}

Evaluate:
1. Is the overall pacing appropriate for the page count ({page_count} pages)?
2. Does each scene have a clear emotional beat that progresses the story?
3. Is the conflict established early enough?
4. Is the character voice consistent in the dialogue?
5. Are there any scenes that are too rushed or dragged out?

Return a CriticFeedback JSON:
- overall_score  : 1–10 integer
- is_approved    : true if score >= {threshold}
- pacing_issues  : list of specific problems (empty list if none)
- general_feedback : 1–3 sentence overall verdict
- revision_instructions : specific rewrite instructions if not approved (empty string if approved)
"""

_PROMPT_REVISE = """\
Revise the manga episode outline and dialogue based on this editorial feedback.

Premise: "{premise}"

Original Episode Outline:
{outline_json}

Original Dialogue Draft:
{dialogue_json}

Critic Feedback (score: {score}/10):
{feedback_json}

Revision Instructions:
{revision_instructions}

Return ONLY a valid JSON object with two keys:
  "episode_outline": {{ ...revised EpisodeOutline... }},
  "dialogue_draft":  {{ ...revised DialogueDraft... }}

Keep the same character_id UUIDs from the CharacterBible. Fix ONLY the issues flagged by the critic.
"""


# ---------------------------------------------------------------------------
# Revision response container
# ---------------------------------------------------------------------------


class _RevisionResponse(BaseModel):
    """Wrapper for the paired revision LLM call."""

    episode_outline: EpisodeOutline
    dialogue_draft: DialogueDraft


# ---------------------------------------------------------------------------
# WriterAgent
# ---------------------------------------------------------------------------


class WriterAgent:
    """
    Narrative generation agent.

    Runs an internal Critic sub-routine after the first draft and iterates
    up to ``MAX_CRITIC_ROUNDS`` times if the score falls below the approval
    threshold (``_CRITIC_APPROVAL_THRESHOLD`` / 10).

    Usage::

        agent = WriterAgent(llm=LLMAdapter())
        output = await agent.run("A cyberpunk chef fights food critics with a laser spatula")
    """

    def __init__(self, llm: BaseLLMAdapter) -> None:
        self._llm = llm

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        premise: str,
        style_pack: StylePack | None = None,  # reserved for future style-aware writing
    ) -> WriterAgentOutput:
        """
        Execute the full writer pipeline for *premise*.

        Returns a ``WriterAgentOutput`` that has passed the Critic's approval
        (or exhausted revision rounds).
        """
        logger.info("[WriterAgent] Starting — premise: %.80s…", premise)

        # Step 1: Character Bible
        logger.info("[WriterAgent] Generating CharacterBible…")
        bible = await self._generate_character_bible(premise)
        logger.info("[WriterAgent] CharacterBible done — %d characters", len(bible.characters))

        # Step 2: Episode Outline
        logger.info("[WriterAgent] Generating EpisodeOutline…")
        outline = await self._generate_episode_outline(premise, bible)
        logger.info("[WriterAgent] EpisodeOutline done — %d scenes", len(outline.scenes))

        # Step 3: Dialogue Draft
        logger.info("[WriterAgent] Generating DialogueDraft…")
        dialogue = await self._generate_dialogue_draft(outline, bible)
        logger.info("[WriterAgent] DialogueDraft done — %d lines", len(dialogue.lines))

        # Step 4: Critic loop
        critic_rounds = 0
        final_score = 0

        for round_num in range(1, _MAX_CRITIC_ROUNDS + 1):
            logger.info("[WriterAgent] Critic review — round %d/%d…", round_num, _MAX_CRITIC_ROUNDS)
            feedback = await self._critic_review(outline, dialogue, premise)
            final_score = feedback.overall_score
            logger.info(
                "[WriterAgent] Critic score: %d/10 — approved: %s",
                feedback.overall_score,
                feedback.is_approved,
            )

            if feedback.is_approved:
                break

            if round_num < _MAX_CRITIC_ROUNDS:
                logger.info("[WriterAgent] Revising based on critic feedback…")
                outline, dialogue = await self._revise(outline, dialogue, feedback, premise)
                critic_rounds += 1
            else:
                logger.warning(
                    "[WriterAgent] Critic threshold not met after %d rounds (score %d/%d). "
                    "Proceeding with best draft.",
                    _MAX_CRITIC_ROUNDS,
                    feedback.overall_score,
                    10,
                )

        logger.info("[WriterAgent] Complete — final critic score: %d/10", final_score)

        return WriterAgentOutput(
            character_bible=bible,
            episode_outline=outline,
            dialogue_draft=dialogue,
            critic_rounds_taken=critic_rounds,
            final_critic_score=final_score,
        )

    # ------------------------------------------------------------------
    # Private generation steps
    # ------------------------------------------------------------------

    async def _generate_character_bible(self, premise: str) -> CharacterBible:
        return await self._llm.generate_structured_response(
            prompt=_PROMPT_BIBLE.format(premise=premise),
            response_schema=CharacterBible,
            system_instruction=_SYSTEM_WRITER,
            temperature=0.80,
        )

    async def _generate_episode_outline(
        self,
        premise: str,
        bible: CharacterBible,
    ) -> EpisodeOutline:
        return await self._llm.generate_structured_response(
            prompt=_PROMPT_OUTLINE.format(
                premise=premise,
                bible_json=bible.model_dump_json(indent=2),
            ),
            response_schema=EpisodeOutline,
            system_instruction=_SYSTEM_WRITER,
            temperature=0.75,
        )

    async def _generate_dialogue_draft(
        self,
        outline: EpisodeOutline,
        bible: CharacterBible,
    ) -> DialogueDraft:
        return await self._llm.generate_structured_response(
            prompt=_PROMPT_DIALOGUE.format(
                outline_json=outline.model_dump_json(indent=2),
                bible_json=bible.model_dump_json(indent=2),
            ),
            response_schema=DialogueDraft,
            system_instruction=_SYSTEM_WRITER,
            temperature=0.85,
        )

    # ------------------------------------------------------------------
    # Critic sub-routine
    # ------------------------------------------------------------------

    async def _critic_review(
        self,
        outline: EpisodeOutline,
        dialogue: DialogueDraft,
        premise: str,
    ) -> CriticFeedback:
        """
        Critic sub-routine: evaluates *outline* + *dialogue* for narrative pacing.

        Returns a ``CriticFeedback`` with a score and actionable revision notes.
        Uses a strict system instruction that puts the LLM in editor mode.
        """
        return await self._llm.generate_structured_response(
            prompt=_PROMPT_CRITIC.format(
                premise=premise,
                outline_json=outline.model_dump_json(indent=2),
                dialogue_json=dialogue.model_dump_json(indent=2),
                page_count=outline.target_page_count,
                threshold=_CRITIC_APPROVAL_THRESHOLD,
            ),
            response_schema=CriticFeedback,
            system_instruction=_SYSTEM_CRITIC,
            temperature=0.40,  # low temperature for consistent, analytical critique
        )

    async def _revise(
        self,
        outline: EpisodeOutline,
        dialogue: DialogueDraft,
        feedback: CriticFeedback,
        premise: str,
    ) -> tuple[EpisodeOutline, DialogueDraft]:
        """
        Apply the Critic's revision instructions to produce an improved draft.

        Returns the revised (outline, dialogue) pair.
        """
        result = await self._llm.generate_structured_response(
            prompt=_PROMPT_REVISE.format(
                premise=premise,
                outline_json=outline.model_dump_json(indent=2),
                dialogue_json=dialogue.model_dump_json(indent=2),
                feedback_json=feedback.model_dump_json(indent=2),
                score=feedback.overall_score,
                revision_instructions=feedback.revision_instructions,
            ),
            response_schema=_RevisionResponse,
            system_instruction=_SYSTEM_WRITER,
            temperature=0.70,
        )
        return result.episode_outline, result.dialogue_draft
