from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from adapters import ImageAdapterError, create_image_adapter
from agents.prompt_director_agent import PromptDirectorAgent
from cli.image_paths import OUTPUT_ROOT, build_internal_image_url, to_project_relative_path
from config import Config
from models.schemas import CharacterBible, PanelSpec, StylePack

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class LockConstraintsPayload(BaseModel):
    lock_characters: bool = True
    lock_style: bool = True
    lock_composition: bool = False
    lock_dialogue: bool = False


class RerenderPanelPayload(BaseModel):
    panel: PanelSpec
    page_id: str
    style_pack: StylePack
    character_bible: CharacterBible
    lock_constraints: LockConstraintsPayload


class RerenderPanelResult(BaseModel):
    image_url: str
    model_used: str
    generation_params: dict[str, Any]
    generated_at: str


def _build_lock_clauses(payload: RerenderPanelPayload, base_style_suffix: str) -> list[str]:
    panel = payload.panel
    locks = payload.lock_constraints
    clauses: list[str] = []

    if locks.lock_characters and panel.characters:
        character_lines = []
        for character_id in panel.characters:
            character = payload.character_bible.get_by_id(character_id)
            if character:
                character_lines.append(f"{character.name}: {character.visual_description}")
        if character_lines:
            clauses.append(
                "Keep the same character identities and design cues: "
                + "; ".join(character_lines)
            )

    if locks.lock_style and base_style_suffix:
        clauses.append(f"Keep the established style direction: {base_style_suffix}")

    if locks.lock_composition:
        shot_type = panel.shot_type.value.replace("_", " ")
        camera_angle = panel.camera_angle.value.replace("_", " ")
        clauses.append(
            f"Keep the composition close to a {shot_type} framed at a {camera_angle} angle"
        )

    if locks.lock_dialogue and panel.dialogue:
        ordered_dialogue = sorted(panel.dialogue, key=lambda line: line.reading_order)
        dialogue_text = " | ".join(line.text for line in ordered_dialogue if line.text.strip())
        if dialogue_text:
            clauses.append(f"Keep the dialogue and story beat readable: {dialogue_text}")

    if clauses:
        clauses.append(
            "Treat these as best-effort constraints while improving the panel render quality"
        )

    return clauses


def _resolve_reference_images(panel: PanelSpec) -> list[str]:
    local_image_path = panel.render_output.generation_params.get("local_image_path")

    if not isinstance(local_image_path, str) or not local_image_path.strip():
        return []

    image_path = Path(local_image_path)
    if not image_path.is_absolute():
      image_path = PROJECT_ROOT / image_path

    return [str(image_path)] if image_path.exists() else []


async def _rerender_panel(payload: RerenderPanelPayload) -> RerenderPanelResult:
    Config.validate()

    director = PromptDirectorAgent()
    prompt_plan = director.synthesize(
        panel=payload.panel,
        style_pack=payload.style_pack,
        character_bible=payload.character_bible,
    )

    prompt_sections = [prompt_plan.final_prompt]
    prompt_sections.extend(_build_lock_clauses(payload, prompt_plan.style_suffix))
    final_prompt = "\n\n".join(section for section in prompt_sections if section)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = (
        OUTPUT_ROOT
        / "rerenders"
        / payload.page_id
        / str(payload.panel.panel_id)
        / f"{timestamp}.png"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    adapter = create_image_adapter()
    result = await adapter.generate_panel_image(
        prompt=final_prompt,
        style_pack=payload.style_pack,
        reference_images=_resolve_reference_images(payload.panel),
        draft_mode=True,
        aspect_ratio="2:3",
    )

    output_path.write_bytes(result.image_bytes)
    image_url = build_internal_image_url(output_path)
    if not image_url:
        raise ImageAdapterError(f"Could not build an internal image URL for {output_path}")

    generation_params = {
        **result.generation_params,
        "local_image_path": to_project_relative_path(output_path),
        "source_page_id": payload.page_id,
        "source_panel_id": str(payload.panel.panel_id),
        "lock_constraints": payload.lock_constraints.model_dump(),
        "reference_prompt": final_prompt,
    }

    return RerenderPanelResult(
        image_url=image_url,
        model_used=result.model_used,
        generation_params=generation_params,
        generated_at=result.generated_at.isoformat().replace("+00:00", "Z"),
    )


def main() -> None:
    raw_payload = sys.stdin.read()
    payload = RerenderPanelPayload.model_validate_json(raw_payload)
    result = asyncio.run(_rerender_panel(payload))
    sys.stdout.write(result.model_dump_json())


if __name__ == "__main__":
    main()
