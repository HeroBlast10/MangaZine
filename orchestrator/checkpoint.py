"""
MangaZine — Checkpoint persistence for pipeline state.

Saves and restores intermediate pipeline artefacts so that a failed or
interrupted run can be resumed from the last successful step.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


@dataclass
class CheckpointManager:
    """
    Manages checkpoint files for a single pipeline run.

    Each step's output is serialised to ``<checkpoints_dir>/<step_name>.json``.
    On resume, the manager loads the latest checkpoint and reports which step
    to start from.
    """

    checkpoints_dir: Path
    _saved_steps: dict[str, Path] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def save(self, step_name: str, data: BaseModel | dict | list) -> Path:
        path = self.checkpoints_dir / f"{step_name}.json"
        if isinstance(data, BaseModel):
            payload = data.model_dump_json(indent=2)
        elif isinstance(data, list):
            payload = json.dumps(
                [
                    item.model_dump() if isinstance(item, BaseModel) else item
                    for item in data
                ],
                indent=2,
                default=str,
            )
        else:
            payload = json.dumps(data, indent=2, default=str)

        path.write_text(payload, encoding="utf-8")
        self._saved_steps[step_name] = path
        logger.debug("Checkpoint saved: %s -> %s", step_name, path)
        return path

    def load(self, step_name: str) -> dict[str, Any] | list | None:
        path = self.checkpoints_dir / f"{step_name}.json"
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            return json.loads(raw)
        except Exception:
            logger.warning("Failed to load checkpoint %s", path, exc_info=True)
            return None

    def has_checkpoint(self, step_name: str) -> bool:
        return (self.checkpoints_dir / f"{step_name}.json").exists()

    def list_checkpoints(self) -> list[str]:
        return sorted(
            p.stem
            for p in self.checkpoints_dir.glob("*.json")
        )
