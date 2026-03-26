"""
MangaZine Core Domain Models
All comic elements are structured JSON states via Pydantic V2.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ShotType(str, Enum):
    """Camera framing / shot size for a panel."""

    EXTREME_CLOSE_UP = "extreme_close_up"
    CLOSE_UP = "close_up"
    MEDIUM_CLOSE_UP = "medium_close_up"
    MEDIUM_SHOT = "medium_shot"
    MEDIUM_WIDE = "medium_wide"
    WIDE_SHOT = "wide_shot"
    EXTREME_WIDE = "extreme_wide"
    OVER_THE_SHOULDER = "over_the_shoulder"
    POV = "pov"
    INSERT = "insert"


class CameraAngle(str, Enum):
    """Vertical perspective angle for a panel."""

    EYE_LEVEL = "eye_level"
    LOW_ANGLE = "low_angle"
    HIGH_ANGLE = "high_angle"
    BIRDS_EYE = "birds_eye"
    WORMS_EYE = "worms_eye"
    DUTCH_ANGLE = "dutch_angle"
    OVERHEAD = "overhead"
    CANTED = "canted"


class LayoutType(str, Enum):
    """Page layout grid presets."""

    UNIFORM_GRID = "uniform_grid"
    ASYMMETRIC = "asymmetric"
    SPLASH = "splash"
    DOUBLE_SPLASH = "double_splash"
    FREE_FORM = "free_form"
    TIER_STACK = "tier_stack"


class LayoutTemplate(str, Enum):
    """
    Manga page layout templates with variable panel counts.
    Each template defines a specific CSS grid arrangement.
    """
    
    # 1 panel layouts (splash pages)
    SPLASH_FULL = "splash_full"
    
    # 2 panel layouts
    PANELS_2_VERTICAL = "panels_2_vertical"
    PANELS_2_HORIZONTAL = "panels_2_horizontal"
    
    # 3 panel layouts
    PANELS_3_VERTICAL = "panels_3_vertical"
    PANELS_3_TOP_SPLIT = "panels_3_top_split"
    PANELS_3_BOTTOM_SPLIT = "panels_3_bottom_split"
    
    # 4 panel layouts
    PANELS_4_GRID = "panels_4_grid"
    PANELS_4_VERTICAL = "panels_4_vertical"
    PANELS_4_L_SHAPE = "panels_4_l_shape"
    
    # 5 panel layouts
    PANELS_5_CROSS = "panels_5_cross"
    PANELS_5_T_SHAPE = "panels_5_t_shape"
    PANELS_5_STAGGERED = "panels_5_staggered"
    
    # 6 panel layouts
    PANELS_6_GRID = "panels_6_grid"
    PANELS_6_DYNAMIC = "panels_6_dynamic"
    
    # 7 panel layouts
    PANELS_7_COMPLEX = "panels_7_complex"
    
    # 8 panel layouts
    PANELS_8_GRID = "panels_8_grid"


class ProjectStatus(str, Enum):
    """Overall project lifecycle state."""

    DRAFT = "draft"
    IN_PRODUCTION = "in_production"
    REVIEW = "review"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class RenderStatus(str, Enum):
    """Render job status for an individual panel."""

    PENDING = "pending"
    GENERATING = "generating"
    DRAFT_READY = "draft_ready"
    APPROVED = "approved"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# StylePack
# ---------------------------------------------------------------------------


class StylePack(BaseModel):
    """
    Immutable style DNA that governs the visual language of the entire project.
    All numeric fields are normalised to [0.0, 1.0] unless stated otherwise.
    """

    style_pack_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this style pack.",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Human-readable name, e.g. 'Shonen Bold' or 'Noir Ink'.",
    )
    line_weight: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        0.5,
        description="Stroke thickness scale; 0 = hairline, 1 = ultra-bold.",
    )
    contrast: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        0.7,
        description="Black-to-white contrast intensity across the artwork.",
    )
    screentone_density: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        0.4,
        description="Coverage of screentone / halftone fills (0 = none, 1 = heavy).",
    )
    panel_regularity: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        0.6,
        description="How uniform panel borders are; 0 = organic/broken, 1 = rigid grid.",
    )
    speed_line_intensity: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        0.3,
        description="Prevalence of motion / speed lines in action panels.",
    )
    background_detail: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        0.5,
        description="Level of background rendering detail versus minimalism.",
    )
    color_palette: list[str] = Field(
        default_factory=list,
        description="Ordered list of hex color codes (#RRGGBB) defining the palette.",
    )
    tone_keywords: list[str] = Field(
        default_factory=list,
        description="Descriptive tone words fed to image generation prompts, e.g. ['gritty', 'monochrome'].",
    )
    reference_image_urls: list[HttpUrl] = Field(
        default_factory=list,
        description="URLs to canonical style reference images.",
    )


# ---------------------------------------------------------------------------
# CharacterBible
# ---------------------------------------------------------------------------


class CharacterProfile(BaseModel):
    """A single character's canonical description and visual reference data."""

    character_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this character.",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Full canonical name of the character.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names or nicknames used in the script.",
    )
    core_traits: list[str] = Field(
        ...,
        min_length=1,
        description="Key personality traits that drive behaviour, e.g. ['reckless', 'loyal'].",
    )
    visual_description: str = Field(
        ...,
        min_length=1,
        description="Detailed prose description of appearance fed directly to image prompts.",
    )
    age_range: str | None = Field(
        None,
        description="Approximate age or range, e.g. '17' or '30–35'.",
    )
    role: str | None = Field(
        None,
        description="Narrative role, e.g. 'protagonist', 'antagonist', 'supporting'.",
    )
    reference_image_urls: list[HttpUrl] = Field(
        default_factory=list,
        description="URLs to approved reference sheets / turnaround images.",
    )
    notes: str | None = Field(
        None,
        description="Free-form production notes, continuity flags, or design constraints.",
    )


class CharacterBible(BaseModel):
    """
    The complete roster of characters for a project.
    Acts as the single source of truth for character IDs referenced in panels.
    """

    characters: list[CharacterProfile] = Field(
        default_factory=list,
        description="Ordered list of all character profiles in the project.",
    )

    def get_by_id(self, character_id: UUID) -> CharacterProfile | None:
        """Return the character matching *character_id*, or None if not found."""
        return next((c for c in self.characters if c.character_id == character_id), None)

    def get_by_name(self, name: str) -> CharacterProfile | None:
        """Return the first character whose name or alias matches *name* (case-insensitive)."""
        name_lower = name.lower()
        for c in self.characters:
            if c.name.lower() == name_lower or name_lower in [a.lower() for a in c.aliases]:
                return c
        return None


# ---------------------------------------------------------------------------
# PanelSpec
# ---------------------------------------------------------------------------


class DialogueLine(BaseModel):
    """A single balloon or caption within a panel."""

    character_id: UUID | None = Field(
        None,
        description="Speaker character ID; None for captions or narration boxes.",
    )
    text: str = Field(
        ...,
        description="Verbatim dialogue or caption text.",
    )
    balloon_type: str = Field(
        "speech",
        description="Balloon style: 'speech', 'thought', 'whisper', 'shout', 'caption', 'sfx'.",
    )
    reading_order: int = Field(
        0,
        ge=0,
        description="Zero-based index defining the balloon reading sequence in the panel.",
    )


class RenderRefs(BaseModel):
    """Reference assets and constraints passed to the image generation model."""

    style_pack_id: UUID | None = Field(
        None,
        description="Override style pack; inherits from project if None.",
    )
    character_ids: list[UUID] = Field(
        default_factory=list,
        description="Characters whose visual references must be injected into the prompt.",
    )
    pose_reference_urls: list[HttpUrl] = Field(
        default_factory=list,
        description="URLs to pose or composition reference images.",
    )
    negative_prompt: str = Field(
        "",
        description="Comma-separated terms to exclude from the generated image.",
    )
    seed: int | None = Field(
        None,
        description="RNG seed for deterministic re-generation; None = random.",
    )


class RenderOutput(BaseModel):
    """Artefacts produced after an image generation run."""

    status: RenderStatus = Field(
        RenderStatus.PENDING,
        description="Current render job status.",
    )
    model_used: str | None = Field(
        None,
        description="Exact model identifier used, e.g. 'gemini-3.1-flash-image-preview'.",
    )
    image_url: str | None = Field(
        None,
        description="URL of the rendered panel image. Can be an internal app route.",
    )
    thumbnail_url: str | None = Field(
        None,
        description="URL of a lower-resolution thumbnail for UI previews.",
    )
    generation_params: dict = Field(
        default_factory=dict,
        description="Full parameter snapshot sent to the image model for reproducibility.",
    )
    generated_at: datetime | None = Field(
        None,
        description="UTC timestamp of when the image was generated.",
    )
    reviewer_notes: str | None = Field(
        None,
        description="Human reviewer feedback attached during approval workflow.",
    )


class PanelSpec(BaseModel):
    """
    Atomic unit of a comic page.
    Encapsulates composition intent, dialogue, and the full render lifecycle.
    """

    panel_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this panel.",
    )
    panel_index: int = Field(
        ...,
        ge=0,
        description="Zero-based reading-order position within its parent page.",
    )
    shot_type: ShotType = Field(
        ...,
        description="Camera framing / shot size, e.g. ShotType.CLOSE_UP.",
    )
    camera_angle: CameraAngle = Field(
        CameraAngle.EYE_LEVEL,
        description="Vertical camera perspective angle.",
    )
    characters: list[UUID] = Field(
        default_factory=list,
        description="Character IDs (from CharacterBible) present in this panel.",
    )
    setting_description: str = Field(
        "",
        description="Brief prose description of the environment / background.",
    )
    action_description: str = Field(
        "",
        description="What is physically happening in the panel beyond dialogue.",
    )
    dialogue: list[DialogueLine] = Field(
        default_factory=list,
        description="Ordered list of dialogue balloons and captions in this panel.",
    )
    prompt_plan: str = Field(
        "",
        description="Assembled image-generation prompt (auto-built or manually overridden).",
    )
    render_refs: RenderRefs = Field(
        default_factory=RenderRefs,
        description="Reference assets and constraints for the image model.",
    )
    render_output: RenderOutput = Field(
        default_factory=RenderOutput,
        description="Output artefacts and status from the most recent render run.",
    )
    is_splash: bool = Field(
        False,
        description="True if this panel is a full-page or double-page splash.",
    )
    notes: str | None = Field(
        None,
        description="Director / editor notes that should not affect rendering.",
    )


# ---------------------------------------------------------------------------
# PageSpec
# ---------------------------------------------------------------------------


class GridCell(BaseModel):
    """Bounding box for a single panel slot in a grid layout (normalised 0–1)."""

    column_start: Annotated[float, Field(ge=0.0, le=1.0)]
    column_end: Annotated[float, Field(ge=0.0, le=1.0)]
    row_start: Annotated[float, Field(ge=0.0, le=1.0)]
    row_end: Annotated[float, Field(ge=0.0, le=1.0)]


class PageLayout(BaseModel):
    """Grid and compositional meta-data for a single page."""

    layout_type: LayoutType = Field(
        LayoutType.UNIFORM_GRID,
        description="Preset layout style.",
    )
    columns: int = Field(
        2,
        ge=1,
        description="Number of columns in the base grid.",
    )
    rows: int = Field(
        3,
        ge=1,
        description="Number of rows in the base grid.",
    )
    gutter_px: int = Field(
        8,
        ge=0,
        description="Gutter size between panels in pixels (for export).",
    )
    cells: list[GridCell] = Field(
        default_factory=list,
        description="Explicit cell definitions for asymmetric / free-form layouts.",
    )
    bleed: bool = Field(
        False,
        description="Whether the page uses full-bleed (no outer border/margin).",
    )


class PageSpec(BaseModel):
    """
    A single manga page composed of one or more panels.
    Owns the layout grid and the ordered panel sequence.
    """

    page_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this page.",
    )
    page_number: int = Field(
        ...,
        ge=1,
        description="One-based page number within the episode.",
    )
    layout_template: LayoutTemplate = Field(
        LayoutTemplate.PANELS_4_GRID,
        description="Manga layout template defining panel arrangement.",
    )
    layout: PageLayout = Field(
        default_factory=PageLayout,
        description="Grid and composition metadata for this page.",
    )
    panels: list[PanelSpec] = Field(
        default_factory=list,
        description="Ordered list of panels in reading order.",
    )
    chapter_break: bool = Field(
        False,
        description="True if this page marks the start of a new chapter.",
    )
    notes: str | None = Field(
        None,
        description="Page-level production notes visible to editors.",
    )


# ---------------------------------------------------------------------------
# EpisodeOutline
# ---------------------------------------------------------------------------


class SceneOutline(BaseModel):
    """High-level description of a scene before page/panel breakdown."""

    scene_id: UUID = Field(
        default_factory=uuid4,
        description="Unique scene identifier.",
    )
    title: str = Field(
        ...,
        description="Short scene title used in the outline view.",
    )
    summary: str = Field(
        ...,
        description="1–3 sentence prose summary of what happens in this scene.",
    )
    location: str = Field(
        "",
        description="Primary setting / location name.",
    )
    characters_present: list[UUID] = Field(
        default_factory=list,
        description="Character IDs expected to appear in this scene.",
    )
    emotional_beat: str = Field(
        "",
        description="Core emotional note or dramatic function of the scene.",
    )
    page_range: tuple[int, int] | None = Field(
        None,
        description="Inclusive (start_page, end_page) allocation; None if unassigned.",
    )


class EpisodeOutline(BaseModel):
    """
    Narrative blueprint for a single episode.
    Links the story structure to pages and scenes before full panel breakdown.
    """

    episode_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this episode.",
    )
    episode_number: int = Field(
        ...,
        ge=1,
        description="One-based episode number within its series.",
    )
    title: str = Field(
        ...,
        description="Episode title as it appears in publication.",
    )
    logline: str = Field(
        "",
        description="Single-sentence hook summarising the episode's central conflict.",
    )
    scenes: list[SceneOutline] = Field(
        default_factory=list,
        description="Ordered list of scene outlines comprising the episode.",
    )
    pages: list[PageSpec] = Field(
        default_factory=list,
        description="Fully broken-down pages once script moves past outline stage.",
    )
    target_page_count: int = Field(
        24,
        ge=1,
        description="Target page count for this episode (editorial budget).",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of episode creation.",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of last modification.",
    )


# ---------------------------------------------------------------------------
# ComicProject  (root model)
# ---------------------------------------------------------------------------


class ComicProject(BaseModel):
    """
    Root aggregate model for a MangaZine project.
    This is the single serialisable state object persisted to disk / database.
    Every agent in the pipeline reads from and writes back to this structure.
    """

    project_id: UUID = Field(
        default_factory=uuid4,
        description="Globally unique identifier for the project.",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Official series or one-shot title.",
    )
    subtitle: str | None = Field(
        None,
        description="Optional subtitle or tagline.",
    )
    genre: list[str] = Field(
        default_factory=list,
        description="Genre tags, e.g. ['shonen', 'action', 'sci-fi'].",
    )
    status: ProjectStatus = Field(
        ProjectStatus.DRAFT,
        description="Overall production lifecycle state.",
    )
    style_pack: StylePack = Field(
        ...,
        description="Master style pack governing the visual language of the entire project.",
    )
    character_bible: CharacterBible = Field(
        default_factory=CharacterBible,
        description="Canonical character roster; single source of truth for character IDs.",
    )
    episodes: list[EpisodeOutline] = Field(
        default_factory=list,
        description="Ordered list of episodes / chapters in publication order.",
    )
    target_audience: str = Field(
        "",
        description="Intended demographic, e.g. 'Shonen (12–18 male)'.",
    )
    language: str = Field(
        "en",
        description="Primary language of the script (ISO 639-1 code).",
    )
    author: str = Field(
        "",
        description="Primary author or studio name.",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of project creation.",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of last modification to any part of the project.",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Arbitrary key-value store for custom pipeline metadata.",
    )
