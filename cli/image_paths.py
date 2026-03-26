from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "output"


def to_project_relative_path(local_path: Path) -> str:
    resolved_path = local_path.resolve()

    try:
        return resolved_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return local_path.as_posix()


def build_internal_image_url(local_path: Path) -> str | None:
    resolved_path = local_path.resolve()

    try:
        relative_path = resolved_path.relative_to(PROJECT_ROOT)
    except ValueError:
        return None

    if not relative_path.parts or relative_path.parts[0].lower() != "output":
        return None

    return f"/api/project-image?{urlencode({'path': relative_path.as_posix()})}"
