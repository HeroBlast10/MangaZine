/**
 * MangaZine TypeScript domain types.
 * Mirror of models/schemas.py — kept in sync manually.
 * All `*_id` fields are UUID strings on the wire.
 */

// ---------------------------------------------------------------------------
// Enumerations
// ---------------------------------------------------------------------------

export type ShotType =
  | 'extreme_close_up'
  | 'close_up'
  | 'medium_close_up'
  | 'medium_shot'
  | 'medium_wide'
  | 'wide_shot'
  | 'extreme_wide'
  | 'over_the_shoulder'
  | 'pov'
  | 'insert';

export type CameraAngle =
  | 'eye_level'
  | 'low_angle'
  | 'high_angle'
  | 'birds_eye'
  | 'worms_eye'
  | 'dutch_angle'
  | 'overhead'
  | 'canted';

export type LayoutType =
  | 'uniform_grid'
  | 'asymmetric'
  | 'splash'
  | 'double_splash'
  | 'free_form'
  | 'tier_stack';

export type LayoutTemplate =
  | 'splash_full'
  | 'panels_2_vertical'
  | 'panels_2_horizontal'
  | 'panels_3_vertical'
  | 'panels_3_top_split'
  | 'panels_3_bottom_split'
  | 'panels_4_grid'
  | 'panels_4_vertical'
  | 'panels_4_l_shape'
  | 'panels_5_cross'
  | 'panels_5_t_shape'
  | 'panels_5_staggered'
  | 'panels_6_grid'
  | 'panels_6_dynamic'
  | 'panels_7_complex'
  | 'panels_8_grid';

export type ProjectStatus =
  | 'draft'
  | 'in_production'
  | 'review'
  | 'completed'
  | 'archived';

export type RenderStatus =
  | 'pending'
  | 'generating'
  | 'draft_ready'
  | 'approved'
  | 'rejected';

// ---------------------------------------------------------------------------
// StylePack
// ---------------------------------------------------------------------------

export interface StylePack {
  style_pack_id: string;
  name: string;
  /** 0 = hairline, 1 = ultra-bold */
  line_weight: number;
  /** 0 = soft tones, 1 = stark black-and-white */
  contrast: number;
  /** 0 = none, 1 = heavy screentone fills */
  screentone_density: number;
  /** 0 = organic/broken borders, 1 = rigid grid */
  panel_regularity: number;
  /** 0 = none, 1 = heavy speed lines */
  speed_line_intensity: number;
  /** 0 = minimal, 1 = highly detailed backgrounds */
  background_detail: number;
  color_palette: string[];
  tone_keywords: string[];
  reference_image_urls: string[];
}

// ---------------------------------------------------------------------------
// CharacterBible
// ---------------------------------------------------------------------------

export interface CharacterProfile {
  character_id: string;
  name: string;
  aliases: string[];
  core_traits: string[];
  visual_description: string;
  age_range?: string;
  role?: string;
  reference_image_urls: string[];
  notes?: string;
}

export interface CharacterBible {
  characters: CharacterProfile[];
}

// ---------------------------------------------------------------------------
// PanelSpec
// ---------------------------------------------------------------------------

export interface DialogueLine {
  character_id?: string;
  text: string;
  /** 'speech' | 'thought' | 'whisper' | 'shout' | 'caption' | 'sfx' */
  balloon_type: string;
  /** Zero-based reading order within the panel */
  reading_order: number;
}

export interface RenderRefs {
  style_pack_id?: string;
  character_ids: string[];
  pose_reference_urls: string[];
  negative_prompt: string;
  seed?: number;
}

export interface RenderOutput {
  status: RenderStatus;
  model_used?: string;
  image_url?: string;
  thumbnail_url?: string;
  generation_params: Record<string, unknown>;
  generated_at?: string;
  reviewer_notes?: string;
}

/**
 * PanelSpec extended with a frontend-only `revision_history` array.
 * The history is populated by `updatePanelImage` before each overwrite,
 * enabling non-destructive iterative re-rendering.
 */
export interface PanelSpec {
  panel_id: string;
  panel_index: number;
  shot_type: ShotType;
  camera_angle: CameraAngle;
  /** Character IDs (UUIDs) from CharacterBible present in this panel */
  characters: string[];
  setting_description: string;
  action_description: string;
  dialogue: DialogueLine[];
  prompt_plan: string;
  render_refs: RenderRefs;
  render_output: RenderOutput;
  is_splash: boolean;
  notes?: string;
  /** Frontend-only: previous RenderOutput snapshots, oldest first */
  revision_history?: RenderOutput[];
}

// ---------------------------------------------------------------------------
// PageSpec
// ---------------------------------------------------------------------------

/** Normalised [0, 1] bounding box for a panel cell in the grid */
export interface GridCell {
  column_start: number;
  column_end: number;
  row_start: number;
  row_end: number;
}

export interface PageLayout {
  layout_type: LayoutType;
  columns: number;
  rows: number;
  gutter_px: number;
  cells: GridCell[];
  bleed: boolean;
}

export interface PageSpec {
  page_id: string;
  page_number: number;
  layout_template?: LayoutTemplate;
  layout: PageLayout;
  panels: PanelSpec[];
  chapter_break: boolean;
  notes?: string;
}

// ---------------------------------------------------------------------------
// EpisodeOutline
// ---------------------------------------------------------------------------

export interface SceneOutline {
  scene_id: string;
  title: string;
  summary: string;
  location: string;
  characters_present: string[];
  emotional_beat: string;
  page_range?: [number, number];
}

export interface EpisodeOutline {
  episode_id: string;
  episode_number: number;
  title: string;
  logline: string;
  scenes: SceneOutline[];
  pages: PageSpec[];
  target_page_count: number;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// ComicProject  (root)
// ---------------------------------------------------------------------------

export interface ComicProject {
  project_id: string;
  title: string;
  subtitle?: string;
  genre: string[];
  status: ProjectStatus;
  style_pack: StylePack;
  character_bible: CharacterBible;
  episodes: EpisodeOutline[];
  target_audience: string;
  language: string;
  author: string;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// API contracts (used by PanelEditorSidebar ↔ /api/rerender-panel)
// ---------------------------------------------------------------------------

export interface LockConstraints {
  /** Preserve character IDs and their visual references */
  lock_characters: boolean;
  /** Preserve style_pack settings */
  lock_style: boolean;
  /** Preserve shot_type and camera_angle */
  lock_composition: boolean;
  /** Preserve dialogue lines verbatim */
  lock_dialogue: boolean;
}

export interface RerenderRequest {
  panel: PanelSpec;
  page_id: string;
  lock_constraints: LockConstraints;
}

export interface RerenderResponse {
  image_url: string;
  model_used: string;
  generation_params: Record<string, unknown>;
}
