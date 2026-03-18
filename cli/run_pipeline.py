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

from adapters import ImageAdapter, ImageAdapterError, LLMAdapter, LLMAdapterError
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
Create an EpisodeOutline for Episode 1 of this manga.

Premise: "{premise}"

CharacterBible (the character_id values are already system-assigned — copy them
verbatim into characters_present when referencing characters in scenes):
{bible_json}

Requirements:
- episode_number : 1
- title          : a compelling episode title
- logline        : one gripping sentence describing the central conflict
- scenes         : 1–2 scenes only (this is a 1-page debut episode)
  • For each scene's characters_present, use the EXACT character_id UUID strings
    from the CharacterBible JSON above — do not invent new ones.
- target_page_count : 1
- Do NOT include: episode_id, pages, created_at, updated_at.
"""

_PROMPT_PAGE_SPEC = """\
Break down page 1 of Episode 1 into exactly 4 manga panels.

Premise: "{premise}"

Episode Outline:
{outline_json}

CharacterBible:
{bible_json}

Available character_id → name mapping (use EXACT UUID strings below):
{char_id_list}

Requirements for the PageSpec:
- page_number : 1
- layout.layout_type : "tier_stack"
- panels : exactly 4 PanelSpec objects, panel_index 0–3 in order.

For EACH panel provide:
  • panel_index          : 0, 1, 2, or 3
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


async def run(premise: str, output_dir: Path) -> None:
    """Execute the full single-page MangaZine production pipeline."""

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    checkpoints_dir = output_dir / "checkpoints"

    console.print(
        Panel.fit(
            f"[bold magenta]MangaZine Pipeline[/bold magenta]\n"
            f"[dim]Premise:[/dim]  [italic]{premise}[/italic]",
            border_style="magenta",
            padding=(1, 2),
        )
    )

    # ── Adapters ──────────────────────────────────────────────────────────
    console.print("\n[bold]● Initialising adapters…[/bold]")
    try:
        llm = LLMAdapter()
        img = ImageAdapter()
    except (LLMAdapterError, ImageAdapterError) as exc:
        console.print(f"[bold red]✗ Adapter init failed:[/bold red] {exc}")
        sys.exit(1)

    style_pack = _make_style_pack(premise)
    console.print(f"  [green]✓[/green] Style pack  [cyan]{style_pack.name}[/cyan]")

    # ── Step 1 : CharacterBible ───────────────────────────────────────────
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
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, console=console) as prog:
        t = prog.add_task("[cyan]Step 2/4[/cyan]  Generating EpisodeOutline…", total=None)
        try:
            outline: EpisodeOutline = await llm.generate_structured_response(
                prompt=_PROMPT_EPISODE_OUTLINE.format(
                    premise=premise,
                    bible_json=bible_json,
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
        f"  [green]✓[/green] Episode outline  [dim]({len(outline.scenes)} scene(s))[/dim]  "
        f"«[italic]{outline.title}[/italic]»  "
        f"→ [cyan]checkpoints/02_episode_outline.json[/cyan]"
    )

    # ── Step 3 : PageSpec (4 panels) ──────────────────────────────────────
    char_id_list = "\n".join(
        f"  {c.character_id}  →  {c.name}  ({c.role or 'N/A'})"
        for c in bible.characters
    )

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True, console=console) as prog:
        t = prog.add_task("[cyan]Step 3/4[/cyan]  Expanding page into 4 panels…", total=None)
        try:
            page: PageSpec = await llm.generate_structured_response(
                prompt=_PROMPT_PAGE_SPEC.format(
                    premise=premise,
                    outline_json=outline_json,
                    bible_json=bible_json,
                    char_id_list=char_id_list,
                ),
                response_schema=PageSpec,
                system_instruction=_SYSTEM_COMIC_WRITER,
                temperature=0.70,
            )
        except LLMAdapterError as exc:
            console.print(f"[bold red]✗ PageSpec failed:[/bold red] {exc}")
            sys.exit(1)
        prog.update(t, completed=True)

    page_json = page.model_dump_json(indent=2)
    _save_json(checkpoints_dir / "03_page_spec.json", page_json)
    console.print(
        f"  [green]✓[/green] PageSpec  [dim]({len(page.panels)} panels)[/dim]  "
        f"→ [cyan]checkpoints/03_page_spec.json[/cyan]"
    )
    _show_panel_table(page)

    # ── Step 4 : Render panel images ──────────────────────────────────────
    console.print("\n[bold]● Step 4/4  Rendering panel images (draft mode)…[/bold]")
    images_dir.mkdir(parents=True, exist_ok=True)

    rendered = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as prog:
        render_task = prog.add_task("[cyan]Rendering[/cyan]", total=len(page.panels))

        for panel in page.panels:
            prog.update(
                render_task,
                description=(
                    f"[cyan]Rendering[/cyan] panel {panel.panel_index}  "
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

            image_path = images_dir / f"panel_{panel.panel_index}.png"

            try:
                result = await img.generate_panel_image(
                    prompt=enriched_prompt,
                    aspect_ratio="2:3",
                    style_dna=style_pack,
                    draft_mode=True,
                    output_path=image_path,
                )

                panel.render_output = RenderOutput(
                    status=RenderStatus.DRAFT_READY,
                    model_used=result.model_used,
                    generation_params={
                        **result.generation_params,
                        "local_image_path": str(result.local_path),
                    },
                    generated_at=result.generated_at,
                )
                rendered += 1
                console.print(
                    f"    [green]✓[/green] panel_{panel.panel_index}.png  "
                    f"[dim]({len(result.image_bytes) // 1024} KB)[/dim]"
                )

            except ImageAdapterError as exc:
                panel.render_output.status = RenderStatus.REJECTED
                panel.render_output.reviewer_notes = str(exc)
                console.print(
                    f"    [yellow]⚠[/yellow] Panel {panel.panel_index} render failed "
                    f"[dim](pipeline continues)[/dim]: {exc}"
                )

            prog.advance(render_task)

    # ── Assemble final ComicProject & save ────────────────────────────────
    outline.pages = [page]

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
            f"  [dim]Project JSON  →[/dim]  [cyan]{final_path}[/cyan]\n"
            f"  [dim]Images        →[/dim]  [cyan]{images_dir}/[/cyan]\n"
            f"  [dim]Checkpoints   →[/dim]  [cyan]{checkpoints_dir}/[/cyan]\n\n"
            f"  Panels rendered: "
            f"[{'green' if rendered == len(page.panels) else 'yellow'}]"
            f"{rendered}[/]/{len(page.panels)}",
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
        description="MangaZine: generate a 1-page comic episode from a text premise.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python cli/run_pipeline.py "A cyberpunk chef fights food critics"\n'
            '  python cli/run_pipeline.py "premise" --output-dir ./my_comic\n'
        ),
    )
    parser.add_argument(
        "premise",
        type=str,
        help="Story premise (quoted string).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        metavar="DIR",
        help="Output directory for images, checkpoints, and project JSON (default: ./output).",
    )
    args = parser.parse_args()
    asyncio.run(run(premise=args.premise, output_dir=args.output_dir))


if __name__ == "__main__":
    main()
