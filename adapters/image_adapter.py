"""
MangaZine Image Adapter
Wraps the Google GenAI SDK for manga panel image generation.

Draft mode  → Nano Banana 2   (gemini-3.1-flash-image-preview)
Final mode  → Nano Banana Pro  (gemini-3-pro-image-preview)
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from models.schemas import StylePack

# Load .env file from project root
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

_DRAFT_MODEL = "gemini-3.1-flash-image-preview"   # Nano Banana 2
_FINAL_MODEL = "gemini-3-pro-image-preview"        # Nano Banana Pro
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0  # seconds, doubles each attempt

# MIME type lookup for reference image injection
_MIME_MAP: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class ImageAdapterError(Exception):
    """Raised when the image adapter encounters an unrecoverable error."""


@dataclass
class GeneratedImage:
    """
    Lightweight result container returned by ``generate_panel_image``.

    Attributes
    ----------
    image_bytes:
        Raw image bytes (PNG by default) as returned by the model.
    model_used:
        Exact model identifier that produced the image.
    local_path:
        Path on disk where the image was saved; ``None`` if ``output_path``
        was not provided to the generation call.
    generation_params:
        Full parameter snapshot sent to the image model, preserved for
        deterministic re-generation.
    generated_at:
        UTC timestamp of the generation call.
    """

    image_bytes: bytes
    model_used: str
    local_path: Path | None = None
    generation_params: dict = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Style DNA → prompt helper
# ---------------------------------------------------------------------------


def _style_pack_to_prompt_modifiers(style_dna: StylePack) -> str:
    """
    Translate ``StylePack`` numeric fields (all in [0, 1]) into
    comma-separated natural-language prompt modifiers for the image model.
    """
    parts: list[str] = []

    # Line weight
    if style_dna.line_weight >= 0.7:
        parts.append("ultra-bold ink lines")
    elif style_dna.line_weight <= 0.3:
        parts.append("fine hairline strokes")
    else:
        parts.append("medium-weight ink lines")

    # Contrast
    if style_dna.contrast >= 0.7:
        parts.append("high-contrast black and white")
    elif style_dna.contrast <= 0.3:
        parts.append("soft low-contrast tones")

    # Screentone
    if style_dna.screentone_density >= 0.6:
        parts.append("heavy screentone and halftone fills")
    elif style_dna.screentone_density <= 0.2:
        parts.append("clean flat fills without screentone")

    # Panel borders
    if style_dna.panel_regularity >= 0.8:
        parts.append("rigid geometric panel borders")
    elif style_dna.panel_regularity <= 0.2:
        parts.append("organic broken panel borders")

    # Speed lines
    if style_dna.speed_line_intensity >= 0.6:
        parts.append("dramatic speed lines")

    # Background detail
    if style_dna.background_detail >= 0.7:
        parts.append("highly detailed background rendering")
    elif style_dna.background_detail <= 0.3:
        parts.append("minimal stylised background")

    # Colour palette hint
    if style_dna.color_palette:
        palette_str = ", ".join(style_dna.color_palette[:4])
        parts.append(f"color palette: {palette_str}")

    # Free-form tone keywords injected verbatim
    parts.extend(style_dna.tone_keywords)

    return ", ".join(parts)


def _infer_mime(path: Path) -> str:
    """Map a file extension to a MIME type string."""
    return _MIME_MAP.get(path.suffix.lower(), "image/png")


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------


class ImageAdapter:
    """
    Async adapter for the Google GenAI image generation API.

    Usage::

        adapter = ImageAdapter()
        result = await adapter.generate_panel_image(
            prompt="A neon-lit kitchen, cyberpunk chef raises laser spatula",
            aspect_ratio="2:3",
            style_dna=my_style_pack,
            output_path=Path("output/panel_0.png"),
        )
    """

    def __init__(self, api_key: str | None = None) -> None:
        resolved_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not resolved_key:
            raise ImageAdapterError(
                "Google API key not found. "
                "Set the GOOGLE_API_KEY environment variable or pass api_key=."
            )
        self._client = genai.Client(api_key=resolved_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_panel_image(
        self,
        prompt: str,
        aspect_ratio: str = "2:3",
        style_dna: StylePack | None = None,
        reference_images: list[str] | None = None,
        draft_mode: bool = True,
        output_path: Path | None = None,
    ) -> GeneratedImage:
        """
        Generate a single manga panel image.

        Parameters
        ----------
        prompt:
            Base image-generation prompt for the panel (typically assembled
            from ``PanelSpec.prompt_plan`` + character visual descriptions).
        aspect_ratio:
            Target aspect ratio string, e.g. ``"2:3"``, ``"16:9"``, ``"1:1"``.
            Injected as a natural-language modifier in the prompt because the
            Gemini image API does not accept a structured aspect-ratio field.
        style_dna:
            ``StylePack`` whose numeric fields are translated into prompt
            modifiers via ``_style_pack_to_prompt_modifiers``.
        reference_images:
            Local file paths to inject as multimodal reference context.
            Missing paths are warned about and silently skipped.
        draft_mode:
            ``True``  → Nano Banana 2   (``gemini-3.1-flash-image-preview``)
            ``False`` → Nano Banana Pro  (``gemini-3-pro-image-preview``)
        output_path:
            If provided, the raw image bytes are written to this path.
            Parent directories are created automatically.

        Returns
        -------
        GeneratedImage
            Result container with image bytes, metadata, and optional
            ``local_path``.
        """
        model = _DRAFT_MODEL if draft_mode else _FINAL_MODEL
        enriched_prompt = self._assemble_prompt(prompt, aspect_ratio, style_dna)
        contents = self._build_contents(enriched_prompt, reference_images or [])

        generation_params: dict = {
            "model": model,
            "enriched_prompt": enriched_prompt,
            "aspect_ratio": aspect_ratio,
            "draft_mode": draft_mode,
            "style_pack_name": style_dna.name if style_dna else None,
        }

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                    ),
                )

                image_bytes = self._extract_image_bytes(response)

                saved_path: Path | None = None
                if output_path is not None:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(image_bytes)
                    saved_path = output_path
                    logger.debug("Panel image saved → %s", saved_path)

                return GeneratedImage(
                    image_bytes=image_bytes,
                    model_used=model,
                    local_path=saved_path,
                    generation_params=generation_params,
                )

            except ImageAdapterError:
                raise  # propagate extraction errors immediately

            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY ** attempt
                    logger.warning(
                        "Image generation failed (attempt %d/%d): %s — retrying in %.1fs",
                        attempt,
                        _MAX_RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise ImageAdapterError(
            f"Image generation failed after {_MAX_RETRIES} retries. "
            f"Last error: {last_exc}"
        ) from last_exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _assemble_prompt(
        self,
        base_prompt: str,
        aspect_ratio: str,
        style_dna: StylePack | None,
    ) -> str:
        """
        Combine the base prompt with style DNA modifiers and framing guidance.
        """
        sections: list[str] = [base_prompt.strip()]

        if style_dna:
            modifiers = _style_pack_to_prompt_modifiers(style_dna)
            if modifiers:
                sections.append(f"Art style: {modifiers}.")

        sections.append(
            f"Manga panel, {aspect_ratio} aspect ratio, "
            "black and white comic book illustration, "
            "professional manga line art."
        )
        return "  ".join(sections)

    def _build_contents(
        self,
        prompt: str,
        reference_images: list[str],
    ) -> list:
        """
        Build the ``contents`` list for the API call.

        The prompt text is always the first part; valid local reference image
        files are appended as inline multimodal parts.
        """
        parts: list = [types.Part.from_text(text=prompt)]

        for ref in reference_images:
            ref_path = Path(ref)
            if ref_path.exists() and ref_path.is_file():
                mime = _infer_mime(ref_path)
                parts.append(
                    types.Part.from_bytes(
                        data=ref_path.read_bytes(),
                        mime_type=mime,
                    )
                )
            else:
                logger.warning(
                    "Reference image not found or not a file, skipping: %s", ref
                )

        return [types.Content(role="user", parts=parts)]

    @staticmethod
    def _extract_image_bytes(response) -> bytes:
        """
        Pull the first ``inline_data`` image part from the API response.

        Raises ``ImageAdapterError`` if no image part is found so that the
        retry loop can surface the problem clearly.
        """
        candidates = getattr(response, "candidates", [])
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue
            for part in getattr(content, "parts", []):
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    raw = inline.data
                    # SDK may return bytes or a base64 string
                    if isinstance(raw, (bytes, bytearray)):
                        return bytes(raw)
                    return base64.b64decode(raw)

        finish_reason = "unknown"
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", "unknown")
        raise ImageAdapterError(
            f"No image data found in API response. "
            f"Finish reason: {finish_reason}. "
            "The model may not support image generation or was safety-blocked."
        )
