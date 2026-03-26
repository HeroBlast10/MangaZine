#!/usr/bin/env python3
"""
MangaZine CLI — End-to-end comic production pipeline.

Usage:
    python cli/run_pipeline.py "A cyberpunk chef fights food critics with a laser spatula"
    python cli/run_pipeline.py "premise" --output-dir ./my_comic
    python -m cli.run_pipeline "premise"
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is importable regardless of invocation style
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

from adapters import create_llm_adapter, create_image_adapter, LLMAdapterError, ImageAdapterError
from cli.image_paths import build_internal_image_url, to_project_relative_path
from config import Config
from models.schemas import (
    CharacterBible,
    ComicProject,
    EpisodeOutline,
    PageSpec,
    ProjectStatus,
    RenderOutput,
    RenderStatus,
    StylePack,
)

console = Console()
logging.basicConfig(level=logging.WARNING)  # suppress SDK verbose noise; rich handles pipeline logs

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_COMIC_WRITER = (
    "You are an expert manga script writer and comic book director. "
    "You produce precisely structured, vivid, and cinematically aware descriptions. "
    "IMPORTANT: Do not generate any UUID / ID fields — they are auto-assigned by the system."
)

_PROMPT_CHARACTER_BIBLE = """\
Create a CharacterBible for a manga with the following premise:

"{premise}"

Requirements:
- Include exactly 2 main characters and 1 supporting character (3 total).
- For each character provide:
    • name         — a unique, memorable name fitting the genre
    • core_traits  — a list of 3–5 personality keywords
    • visual_description — 2–3 sentences of precise appearance detail suitable
                           as direct input to an image generation model
                           (include clothing, hair, distinctive features, build)
    • role         — exactly one of: "protagonist", "antagonist", "supporting"
    • age_range    — approximate age as a string, e.g. "28" or "30-35"
- Do NOT include: character_id, aliases, reference_image_urls, notes.
"""

_PROMPT_EPISODE_OUTLINE = """\
Create an EpisodeOutline for Episode {episode_number} of this manga.

Premise: "{premise}"

CharacterBible (the character_id values are already system-assigned — copy them
verbatim into characters_present when referencing characters in scenes):
{bible_json}

{story_memory}

Requirements:
- episode_number : {episode_number}
- title          : a compelling episode title
- logline        : one gripping sentence describing the central conflict
- scenes         : {scene_count} scenes for this {target_pages}-page episode
  • For each scene's characters_present, use the EXACT character_id UUID strings
    from the CharacterBible JSON above — do not invent new ones.
  • Distribute scenes across pages: assign page_range tuples like (1, 3) or (4, 5)
- target_page_count : {target_pages}
- Do NOT include: episode_id, pages, created_at, updated_at.
"""

_PROMPT_PAGE_SPEC = """\
Break down page {page_number} of Episode {episode_number} into {panel_count} manga panels.

Premise: "{premise}"

Scene context for this page:
{scene_context}

CharacterBible:
{bible_json}

Available character_id → name mapping (use EXACT UUID strings below):
{char_id_list}

Requirements for the PageSpec:
- page_number : {page_number}
- layout_template : "{layout_template}"
- panels : exactly {panel_count} PanelSpec objects, panel_index 0–{max_panel_index} in order.

For EACH panel provide:
  • panel_index          : sequential from 0
  • shot_type            : one of [extreme_close_up, close_up, medium_close_up,
                           medium_shot, medium_wide, wide_shot, extreme_wide,
                           over_the_shoulder, pov, insert]
                           — vary them for cinematic pacing
  • camera_angle         : one of [eye_level, low_angle, high_angle, birds_eye,
                           worms_eye, dutch_angle, overhead, canted]
  • characters           : list of character_id UUID strings (from the mapping above)
  • setting_description  : vivid one-sentence environment description
  • action_description   : what physically happens in this panel
  • dialogue             : 1–2 DialogueLine objects per panel
      - text          : spoken or narration text
      - balloon_type  : "speech", "thought", "caption", or "sfx"
      - reading_order : 0-indexed sequence within the panel
      - character_id  : EXACT UUID string of the speaker (omit only for captions)
  • prompt_plan          : a self-contained, detailed image-generation prompt
                           for this panel (lighting, mood, composition, action)

- Do NOT include: page_id, panel_id, render_refs, render_output.
"""

# ---------------------------------------------------------------------------
# StylePack factory
# ---------------------------------------------------------------------------


def _make_style_pack(premise: str) -> StylePack:
    """Derive a sensible StylePack from a rough genre read of the premise."""
    p = premise.lower()
    if any(w in p for w in ("cyber", "neon", "laser", "robot", "sci-fi", "scifi")):
        return StylePack(
            name="Cyberpunk Ink",
            line_weight=0.65,
            contrast=0.85,
            screentone_density=0.40,
            panel_regularity=0.50,
            speed_line_intensity=0.55,
            background_detail=0.65,
            color_palette=["#0d0d0d", "#f2f2f2", "#00eaff", "#ff2d55"],
            tone_keywords=["neon noir", "cinematic", "high contrast manga", "gritty"],
        )
    if any(w in p for w in ("horror", "dark", "shadow", "ghost", "demon", "fear")):
        return StylePack(
            name="Manga Noir",
            line_weight=0.70,
            contrast=0.90,
            screentone_density=0.55,
            panel_regularity=0.45,
            speed_line_intensity=0.30,
            background_detail=0.70,
            color_palette=["#080808", "#ebebeb"],
            tone_keywords=["dark atmosphere", "heavy shadows", "horror manga"],
        )
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


# ---------------------------------------------------------------------------
# Checkpoint / IO helpers
# ---------------------------------------------------------------------------


def _save_json(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


# ---------------------------------------------------------------------------
# Rich display helpers
# ---------------------------------------------------------------------------


def _show_character_table(bible: CharacterBible) -> None:
    tbl = Table(title="Character Bible", box=box.ROUNDED, highlight=True)
    tbl.add_column("Name", style="bold cyan", no_wrap=True)
    tbl.add_column("Role", style="magenta")
    tbl.add_column("Age", justify="center")
    tbl.add_column("Traits")
    tbl.add_column("Visual (preview)")

    for c in bible.characters:
        tbl.add_row(
            c.name,
            c.role or "—",
            c.age_range or "—",
            ", ".join(c.core_traits[:4]),
            (c.visual_description[:70] + "…")
            if len(c.visual_description) > 70
            else c.visual_description,
        )
    console.print(tbl)


def _show_panel_table(page: PageSpec) -> None:
    tbl = Table(
        title=f"Page {page.page_number} — Panel Breakdown",
        box=box.SIMPLE_HEAVY,
    )
    tbl.add_column("#", justify="center", style="bold yellow")
    tbl.add_column("Shot Type", style="cyan")
    tbl.add_column("Angle", style="green")
    tbl.add_column("Action")
    tbl.add_column("Lines", justify="center")

    for p in page.panels:
        action = p.action_description
        tbl.add_row(
            str(p.panel_index),
            p.shot_type.value,
            p.camera_angle.value,
            (action[:60] + "…") if len(action) > 60 else action,
            str(len(p.dialogue)),
        )
    console.print(tbl)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


async def run(
    premise: str,
    output_dir: Path,
    target_pages: int = 1,
    continue_from: Path | None = None,
    episode_number: int = 1,
) -> None:
    """Execute the multi-page MangaZine production pipeline."""
    
    from models.layouts import get_panel_count, suggest_layout_for_scene, LayoutTemplate

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    checkpoints_dir = output_dir / "checkpoints"
    
    # Load previous project if continuing
    previous_project: ComicProject | None = None
    if continue_from and continue_from.exists():
        try:
            previous_project = ComicProject.model_validate_json(continue_from.read_text())
            episode_number = len(previous_project.episodes) + 1
            console.print(f"[dim]Continuing from {continue_from} (Episode {episode_number})[/dim]")
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not load {continue_from}: {exc}[/yellow]")

    console.print(
        Panel.fit(
            f"[bold magenta]MangaZine Pipeline[/bold magenta]\n"
            f"[dim]Premise:[/dim]  [italic]{premise}[/italic]\n"
            f"[dim]Episode:[/dim]  {episode_number}  |  [dim]Pages:[/dim]  {target_pages}",
            border_style="magenta",
            padding=(1, 2),
        )
    )

    # ── Adapters ──────────────────────────────────────────────────────────
    console.print(f"\n[bold]● Initialising adapters…[/bold] [dim]({Config.LLM_PROVIDER.value} + {Config.IMAGE_PROVIDER.value})[/dim]")
    try:
        Config.validate()
        llm = create_llm_adapter()
        img = create_image_adapter()
    except (LLMAdapterError, ImageAdapterError) as exc:
        console.print(f"[bold red]✗ Adapter init failed:[/bold red] {exc}")
        sys.exit(1)

    # Reuse style_pack from previous project or create new
    if previous_project:
        style_pack = previous_project.style_pack
        console.print(f"  [green]✓[/green] Style pack  [cyan]{style_pack.name}[/cyan] [dim](inherited)[/dim]")
    else:
        style_pack = _make_style_pack(premise)
        console.print(f"  [green]✓[/green] Style pack  [cyan]{style_pack.name}[/cyan]")

    # ── Step 1 : CharacterBible ───────────────────────────────────────────
    # Reuse from previous project if continuing
    if previous_project:
        bible = previous_project.character_bible
        bible_json = bible.model_dump_json(indent=2)
        _save_json(checkpoints_dir / "01_character_bible.json", bible_json)
        console.print(
            f"  [green]✓[/green] CharacterBible  [dim]({len(bible.characters)} characters)[/dim]  "
            f"[dim](inherited from previous episode)[/dim]"
        )
    else:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, console=console) as prog:
            t = prog.add_task("[cyan]Step 1/4[/cyan]  Generating CharacterBible…", total=None)
            try:
                bible: CharacterBible = await llm.generate_structured_response(
                    prompt=_PROMPT_CHARACTER_BIBLE.format(premise=premise),
                    response_schema=CharacterBible,
                    system_instruction=_SYSTEM_COMIC_WRITER,
                    temperature=0.80,
                )
            except LLMAdapterError as exc:
                console.print(f"[bold red]✗ CharacterBible failed:[/bold red] {exc}")
                sys.exit(1)
            prog.update(t, completed=True)

        bible_json = bible.model_dump_json(indent=2)
        _save_json(checkpoints_dir / "01_character_bible.json", bible_json)
        console.print(
            f"  [green]✓[/green] CharacterBible  [dim]({len(bible.characters)} characters)[/dim]  "
            f"→ [cyan]checkpoints/01_character_bible.json[/cyan]"
        )
        _show_character_table(bible)

    # ── Step 2 : EpisodeOutline ───────────────────────────────────────────
    # Build story memory from previous episodes
    story_memory = ""
    if previous_project and previous_project.episodes:
        memory_parts = ["Previous episode summaries for continuity:"]
        for ep in previous_project.episodes[-3:]:  # Last 3 episodes max
            memory_parts.append(f"- Episode {ep.episode_number} «{ep.title}»: {ep.logline}")
        story_memory = "\n".join(memory_parts)
    
    # Calculate scene count based on page count (roughly 1-2 scenes per 3-4 pages)
    scene_count = max(1, min(target_pages // 3 + 1, 6))
    
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, console=console) as prog:
        t = prog.add_task(f"[cyan]Step 2/4[/cyan]  Generating EpisodeOutline ({target_pages} pages)…", total=None)
        try:
            outline: EpisodeOutline = await llm.generate_structured_response(
                prompt=_PROMPT_EPISODE_OUTLINE.format(
                    premise=premise,
                    bible_json=bible_json,
                    episode_number=episode_number,
                    target_pages=target_pages,
                    scene_count=scene_count,
                    story_memory=story_memory,
                ),
                response_schema=EpisodeOutline,
                system_instruction=_SYSTEM_COMIC_WRITER,
                temperature=0.75,
            )
        except LLMAdapterError as exc:
            console.print(f"[bold red]✗ EpisodeOutline failed:[/bold red] {exc}")
            sys.exit(1)
        prog.update(t, completed=True)

    outline_json = outline.model_dump_json(indent=2)
    _save_json(checkpoints_dir / "02_episode_outline.json", outline_json)
    console.print(
        f"  [green]✓[/green] Episode outline  [dim]({len(outline.scenes)} scene(s), {target_pages} pages)[/dim]  "
        f"«[italic]{outline.title}[/italic]»  "
        f"→ [cyan]checkpoints/02_episode_outline.json[/cyan]"
    )

    # ── Step 3 : Generate PageSpecs for all pages ──────────────────────────
    char_id_list = "\n".join(
        f"  {c.character_id}  →  {c.name}  ({c.role or 'N/A'})"
        for c in bible.characters
    )
    
    # Determine layout templates for each page
    import random
    layout_options = [
        (LayoutTemplate.PANELS_4_GRID, 4),
        (LayoutTemplate.PANELS_5_STAGGERED, 5),
        (LayoutTemplate.PANELS_6_GRID, 6),
        (LayoutTemplate.PANELS_3_VERTICAL, 3),
        (LayoutTemplate.PANELS_4_L_SHAPE, 4),
    ]
    
    pages: list[PageSpec] = []
    total_panels = 0
    
    console.print(f"\n[bold]● Step 3/4  Generating {target_pages} page(s)…[/bold]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as prog:
        page_task = prog.add_task("[cyan]Generating pages[/cyan]", total=target_pages)
        
        for page_num in range(1, target_pages + 1):
            # Select layout template (vary for visual interest)
            if page_num == 1:
                # First page: splash or dramatic opening
                layout_template = LayoutTemplate.PANELS_4_GRID
                panel_count = 4
            elif page_num == target_pages:
                # Last page: climactic or cliffhanger
                layout_template = LayoutTemplate.PANELS_5_STAGGERED
                panel_count = 5
            else:
                # Middle pages: varied layouts
                layout_template, panel_count = random.choice(layout_options)
            
            # Find relevant scene for this page
            scene_context = "General episode context"
            for scene in outline.scenes:
                if scene.page_range:
                    start, end = scene.page_range
                    if start <= page_num <= end:
                        scene_context = f"Scene: {scene.title}\nSummary: {scene.summary}\nLocation: {scene.location}\nEmotional beat: {scene.emotional_beat}"
                        break
            
            prog.update(page_task, description=f"[cyan]Page {page_num}/{target_pages}[/cyan] ({panel_count} panels)")
            
            try:
                page: PageSpec = await llm.generate_structured_response(
                    prompt=_PROMPT_PAGE_SPEC.format(
                        premise=premise,
                        scene_context=scene_context,
                        bible_json=bible_json,
                        char_id_list=char_id_list,
                        page_number=page_num,
                        episode_number=episode_number,
                        layout_template=layout_template.value,
                        panel_count=panel_count,
                        max_panel_index=panel_count - 1,
                    ),
                    response_schema=PageSpec,
                    system_instruction=_SYSTEM_COMIC_WRITER,
                    temperature=0.70,
                )
                pages.append(page)
                total_panels += len(page.panels)
                
            except LLMAdapterError as exc:
                console.print(f"[bold red]✗ Page {page_num} failed:[/bold red] {exc}")
                # Continue with remaining pages
            
            prog.advance(page_task)
    
    # Save all pages
    pages_data = [p.model_dump() for p in pages]
    _save_json(checkpoints_dir / "03_page_specs.json", json.dumps(pages_data, indent=2, default=str))
    console.print(
        f"  [green]✓[/green] PageSpecs  [dim]({len(pages)} pages, {total_panels} panels)[/dim]  "
        f"→ [cyan]checkpoints/03_page_specs.json[/cyan]"
    )
    
    # Show panel table for first page
    if pages:
        _show_panel_table(pages[0])

    # ── Step 4 : Render panel images for all pages ─────────────────────────
    console.print(f"\n[bold]● Step 4/4  Rendering {total_panels} panel images (draft mode)…[/bold]")
    images_dir.mkdir(parents=True, exist_ok=True)

    rendered = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as prog:
        render_task = prog.add_task("[cyan]Rendering[/cyan]", total=total_panels)

        for page in pages:
            page_dir = images_dir / f"page_{page.page_number:02d}"
            page_dir.mkdir(parents=True, exist_ok=True)
            
            for panel in page.panels:
                prog.update(
                    render_task,
                    description=(
                        f"[cyan]Page {page.page_number}[/cyan] panel {panel.panel_index}  "
                        f"[dim]({panel.shot_type.value} / {panel.camera_angle.value})[/dim]"
                    ),
                )

                # Build enriched prompt = prompt_plan + character visual descriptions
                char_visuals: list[str] = []
                for cid in panel.characters:
                    char = bible.get_by_id(cid)
                    if char:
                        char_visuals.append(f"{char.name}: {char.visual_description}")

                enriched_prompt = panel.prompt_plan
                if char_visuals:
                    enriched_prompt += "  Characters in frame — " + "; ".join(char_visuals)

                image_path = page_dir / f"panel_{panel.panel_index}.png"

                try:
                    image_result = await img.generate_panel_image(
                        prompt=enriched_prompt,
                        style_pack=style_pack,
                        draft_mode=True,
                        aspect_ratio="2:3",
                    )
                    
                    # Save image to disk
                    image_path.write_bytes(image_result.image_bytes)
                    internal_image_url = build_internal_image_url(image_path)

                    panel.render_output = RenderOutput(
                        status=RenderStatus.DRAFT_READY,
                        model_used=image_result.model_used,
                        image_url=internal_image_url,
                        generation_params={
                            **image_result.generation_params,
                            "local_image_path": to_project_relative_path(image_path),
                        },
                        generated_at=image_result.generated_at,
                    )
                    rendered += 1
                    console.print(
                        f"    [green]✓[/green] page_{page.page_number:02d}/panel_{panel.panel_index}.png  "
                        f"[dim]({len(image_result.image_bytes) // 1024} KB)[/dim]"
                    )

                except ImageAdapterError as exc:
                    panel.render_output.status = RenderStatus.REJECTED
                    panel.render_output.reviewer_notes = str(exc)
                    console.print(
                        f"    [yellow]⚠[/yellow] Page {page.page_number} Panel {panel.panel_index} render failed "
                        f"[dim](pipeline continues)[/dim]: {exc}"
                    )

                prog.advance(render_task)

    # ── Assemble final ComicProject & save ────────────────────────────────
    outline.pages = pages

    # If continuing from previous project, append to existing episodes
    if previous_project:
        project = previous_project
        project.episodes.append(outline)
        project.updated_at = datetime.utcnow()
    else:
        project = ComicProject(
            title=outline.title,
            subtitle=premise[:120],
            genre=["action"],
            status=ProjectStatus.IN_PRODUCTION,
            style_pack=style_pack,
            character_bible=bible,
            episodes=[outline],
            author="MangaZine Pipeline",
        )

    final_path = output_dir / "project_final.json"
    final_json = project.model_dump_json(indent=2)
    _save_json(final_path, final_json)

    # ── Summary ───────────────────────────────────────────────────────────
    console.print(
        Panel.fit(
            "[bold green]✓ Pipeline complete![/bold green]\n\n"
            f"  [dim]Episode:[/dim]       {episode_number}\n"
            f"  [dim]Pages:[/dim]         {len(pages)}\n"
            f"  [dim]Project JSON  →[/dim]  [cyan]{final_path}[/cyan]\n"
            f"  [dim]Images        →[/dim]  [cyan]{images_dir}/[/cyan]\n"
            f"  [dim]Checkpoints   →[/dim]  [cyan]{checkpoints_dir}/[/cyan]\n\n"
            f"  Panels rendered: "
            f"[{'green' if rendered == total_panels else 'yellow'}]"
            f"{rendered}[/]/{total_panels}",
            border_style="green",
            padding=(1, 2),
        )
    )

    # Pretty-print a state preview
    preview = json.dumps(json.loads(final_json)["character_bible"], indent=2)
    if len(preview) > 900:
        preview = preview[:900] + "\n  …"
    console.print(
        Panel(
            Syntax(preview, "json", theme="monokai", word_wrap=True),
            title="[dim]state preview — character_bible[/dim]",
            border_style="dim",
        )
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run_pipeline",
        description="MangaZine: generate multi-page manga episodes from a text premise.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python cli/run_pipeline.py "A cyberpunk chef fights food critics"\n'
            '  python cli/run_pipeline.py "premise" --pages 15\n'
            '  python cli/run_pipeline.py "Episode 2 premise" --continue-from ./output/ep1/project_final.json\n'
        ),
    )
    parser.add_argument(
        "premise",
        type=str,
        help="Story premise (quoted string).",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        metavar="N",
        help="Number of pages to generate (default: 1, max: 20).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Output directory (default: auto-generated timestamp folder in ./output/).",
    )
    parser.add_argument(
        "--continue-from",
        type=Path,
        default=None,
        metavar="PROJECT_JSON",
        help="Continue from a previous project (reuse CharacterBible and StylePack).",
    )
    parser.add_argument(
        "--episode",
        type=int,
        default=1,
        metavar="N",
        help="Episode number (default: 1, auto-increments when using --continue-from).",
    )
    args = parser.parse_args()
    
    # Validate pages
    args.pages = max(1, min(20, args.pages))
    
    # Create unique project folder if not specified
    if args.output_dir is None and Config.USE_UNIQUE_PROJECT_FOLDERS:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize premise for folder name
        safe_premise = "".join(c if c.isalnum() or c in " _-" else "_" for c in args.premise[:30])
        safe_premise = safe_premise.strip().replace(" ", "_")
        folder_name = f"{timestamp}_{safe_premise}"
        args.output_dir = Config.OUTPUT_DIR / folder_name
    elif args.output_dir is None:
        args.output_dir = Config.OUTPUT_DIR
    
    asyncio.run(run(
        premise=args.premise,
        output_dir=args.output_dir,
        target_pages=args.pages,
        continue_from=args.continue_from,
        episode_number=args.episode,
    ))


if __name__ == "__main__":
    main()
