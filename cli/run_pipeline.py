#!/usr/bin/env python3
"""
MangaZine CLI — End-to-end comic production pipeline.

Now delegates to the PipelineOrchestrator (state-machine-based),
which calls WriterAgent, StoryboarderAgent, and PromptDirectorAgent
in sequence.

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
from config import Config
from orchestrator.events import EventBus, EventType, PipelineEvent
from orchestrator.pipeline import PipelineOrchestrator, PipelineRequest, PipelineState

console = Console()
logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Rich display helpers
# ---------------------------------------------------------------------------


def _show_character_table(bible) -> None:
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


# ---------------------------------------------------------------------------
# CLI event handler (renders Rich output from pipeline events)
# ---------------------------------------------------------------------------


class CLIEventRenderer:
    """Subscribes to EventBus and renders Rich output in the terminal."""

    def __init__(self) -> None:
        self._step_count = 0

    async def handle(self, event: PipelineEvent) -> None:
        etype = event.event_type
        payload = event.payload

        if etype == EventType.PIPELINE_STARTED:
            console.print(
                Panel.fit(
                    f"[bold magenta]MangaZine Pipeline[/bold magenta]\n"
                    f"[dim]Premise:[/dim]  [italic]{payload.get('premise', '')}[/italic]\n"
                    f"[dim]Episode:[/dim]  {payload.get('episode_number', 1)}  |  "
                    f"[dim]Pages:[/dim]  {payload.get('target_pages', 1)}",
                    border_style="magenta",
                    padding=(1, 2),
                )
            )

        elif etype == EventType.STEP_STARTED:
            self._step_count += 1
            step = event.step_name.replace("_", " ").title()
            console.print(f"\n[bold]● Step {self._step_count}[/bold]  [cyan]{step}[/cyan]…")

        elif etype == EventType.STEP_COMPLETED:
            elapsed = payload.get("elapsed_ms", 0)
            console.print(f"  [green]✓[/green] {event.step_name} [dim]({elapsed:.0f} ms)[/dim]")

        elif etype == EventType.STEP_FAILED:
            console.print(f"  [red]✗[/red] {event.step_name} — {payload.get('error', '')}")

        elif etype == EventType.CRITIC_REVIEW:
            rounds = payload.get("critic_rounds", 0)
            score = payload.get("final_score", 0)
            console.print(
                f"    [dim]Critic:[/dim] {rounds} revision round(s), "
                f"final score [{'green' if score >= 7 else 'yellow'}]{score}/10[/]"
            )

        elif etype == EventType.RHYTHM_CHECK:
            console.print(
                f"    [dim]Page {payload.get('page_number')}:[/dim] "
                f"{payload.get('panel_count')} panels, "
                f"{payload.get('rhythm_rounds', 0)} rhythm correction(s)"
            )

        elif etype == EventType.IMAGE_GENERATED:
            console.print(
                f"    [green]✓[/green] page_{payload['page']:02d}/panel_{payload['panel']}.png  "
                f"[dim]({payload.get('size_kb', 0)} KB)  "
                f"[{payload.get('rendered', 0)}/{payload.get('total', 0)}][/dim]"
            )

        elif etype == EventType.IMAGE_FAILED:
            console.print(
                f"    [yellow]⚠[/yellow] Page {payload.get('page')} "
                f"Panel {payload.get('panel')} failed [dim](pipeline continues)[/dim]"
            )

        elif etype == EventType.PIPELINE_COMPLETED:
            console.print(
                Panel.fit(
                    "[bold green]✓ Pipeline complete![/bold green]",
                    border_style="green",
                    padding=(1, 2),
                )
            )

        elif etype == EventType.PIPELINE_FAILED:
            console.print(
                Panel.fit(
                    f"[bold red]✗ Pipeline failed[/bold red]\n"
                    f"  {payload.get('error', 'Unknown error')}",
                    border_style="red",
                    padding=(1, 2),
                )
            )


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


async def run(
    premise: str,
    output_dir: Path,
    target_pages: int = 1,
    continue_from: Path | None = None,
    episode_number: int = 1,
) -> None:
    """Execute the multi-page MangaZine production pipeline via orchestrator."""

    # ── Adapters ──
    console.print(f"\n[bold]● Initialising adapters…[/bold] [dim]({Config.LLM_PROVIDER.value} + {Config.IMAGE_PROVIDER.value})[/dim]")
    try:
        Config.validate()
        llm = create_llm_adapter()
        img = create_image_adapter()
    except (LLMAdapterError, ImageAdapterError, ValueError) as exc:
        console.print(f"[bold red]✗ Adapter init failed:[/bold red] {exc}")
        sys.exit(1)
    console.print(f"  [green]✓[/green] Adapters ready")

    # ── Event bus + renderer ──
    event_bus = EventBus()
    renderer = CLIEventRenderer()
    event_bus.subscribe(renderer.handle)

    # ── Orchestrator ──
    orchestrator = PipelineOrchestrator(
        llm=llm,
        image_adapter=img,
        event_bus=event_bus,
        output_dir=output_dir,
    )

    request = PipelineRequest(
        premise=premise,
        target_pages=target_pages,
        episode_number=episode_number,
        continue_from=str(continue_from) if continue_from else None,
        output_dir=str(output_dir),
    )

    project = await orchestrator.run(request)

    # ── Summary ──
    if project and project.character_bible:
        _show_character_table(project.character_bible)

    console.print(
        f"\n  [dim]Project JSON  →[/dim]  [cyan]{output_dir / 'project_final.json'}[/cyan]"
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

    args.pages = max(1, min(20, args.pages))

    if args.output_dir is None and Config.USE_UNIQUE_PROJECT_FOLDERS:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
