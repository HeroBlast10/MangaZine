"""Security regression tests for the FastAPI boundary."""

from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from config import Config
from server.main import (
    _generation_request_times,
    _resolve_under_output,
    enforce_generation_rate_limit,
    require_api_key,
)
from server.schemas import RerenderPanelRequest


def test_output_paths_must_stay_inside_the_configured_root(
    monkeypatch,
):
    output_root = Path.cwd() / ".test-output-root"
    monkeypatch.setattr(Config, "OUTPUT_DIR", output_root)

    assert _resolve_under_output("output/run/project_final.json") == (
        output_root / "run" / "project_final.json"
    ).resolve()

    with pytest.raises(HTTPException) as exc_info:
        _resolve_under_output("../secrets.env")
    assert exc_info.value.status_code == 403


def test_absolute_output_paths_are_rejected(monkeypatch):
    output_root = Path.cwd() / ".test-output-root"
    monkeypatch.setattr(Config, "OUTPUT_DIR", output_root)

    with pytest.raises(HTTPException) as exc_info:
        _resolve_under_output(str((output_root / "project.json").resolve()))
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_api_key_is_required_and_compared(monkeypatch):
    monkeypatch.setattr(Config, "API_KEY", "")
    with pytest.raises(HTTPException) as exc_info:
        await require_api_key(None)
    assert exc_info.value.status_code == 503

    monkeypatch.setattr(Config, "API_KEY", "test-secret")
    with pytest.raises(HTTPException) as exc_info:
        await require_api_key("wrong-secret")
    assert exc_info.value.status_code == 401

    assert await require_api_key("test-secret") is None


@pytest.mark.asyncio
async def test_generation_requests_are_rate_limited(monkeypatch):
    monkeypatch.setattr(Config, "MAX_GENERATION_REQUESTS_PER_MINUTE", 1)
    _generation_request_times.clear()
    try:
        assert await enforce_generation_rate_limit() is None
        with pytest.raises(HTTPException) as exc_info:
            await enforce_generation_rate_limit()
        assert exc_info.value.status_code == 429
        assert int(exc_info.value.headers["Retry-After"]) >= 1
    finally:
        _generation_request_times.clear()


def test_rerender_page_id_cannot_be_a_path():
    with pytest.raises(ValidationError):
        RerenderPanelRequest(
            panel={},
            page_id="../../outside",
            style_pack={},
            character_bible={},
        )
