"""
Gemini image adapter.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path

from google import genai
from google.genai import types

from adapters.base import BaseImageAdapter, GeneratedImageResult, ImageAdapterError
from models.schemas import StylePack

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0

_MIME_MAP: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class GeminiImageAdapter(BaseImageAdapter):
    """Google Gemini implementation of BaseImageAdapter."""

    def __init__(
        self,
        api_key: str | None = None,
        draft_model: str | None = None,
        final_model: str | None = None,
    ) -> None:
        from config import Config

        resolved_key = api_key or Config.GOOGLE_API_KEY
        if not resolved_key:
            raise ImageAdapterError(
                "Google API key not found. "
                "Set GOOGLE_API_KEY in .env or pass api_key parameter."
            )

        self._client = genai.Client(api_key=resolved_key)
        self._draft_model = draft_model or Config.GEMINI_IMAGE_DRAFT_MODEL
        self._final_model = final_model or Config.GEMINI_IMAGE_FINAL_MODEL

    async def generate_panel_image(
        self,
        prompt: str,
        style_pack: StylePack,
        reference_images: list[str] | None = None,
        draft_mode: bool = True,
        aspect_ratio: str = "1:1",
    ) -> GeneratedImageResult:
        model = self._draft_model if draft_mode else self._final_model
        full_prompt = self._build_prompt(prompt, style_pack, aspect_ratio)
        contents = [types.Part.from_text(text=full_prompt)]

        loaded_references: list[str] = []
        for reference_image in reference_images or []:
            image_part = self._load_image_part(reference_image)
            if image_part is not None:
                contents.append(image_part)
                loaded_references.append(reference_image)

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=[types.Content(role="user", parts=contents)],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                    ),
                )

                image_bytes = self._extract_image_bytes(response)

                return GeneratedImageResult(
                    image_bytes=image_bytes,
                    model_used=model,
                    generation_params={
                        "provider": "gemini",
                        "prompt": full_prompt,
                        "aspect_ratio": aspect_ratio,
                        "draft_mode": draft_mode,
                        "reference_images_used": loaded_references,
                    },
                )

            except ImageAdapterError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY ** attempt
                    logger.warning(
                        "Image generation failed (attempt %d/%d): %s; retrying in %.1fs",
                        attempt,
                        _MAX_RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise ImageAdapterError(
            f"Image generation failed after {_MAX_RETRIES} retries. Last error: {last_exc}"
        ) from last_exc

    async def generate_batch_images(
        self,
        prompts: list[str],
        style_pack: StylePack,
        reference_images: list[str] | None = None,
        draft_mode: bool = True,
    ) -> list[GeneratedImageResult]:
        tasks = [
            self.generate_panel_image(
                prompt=prompt,
                style_pack=style_pack,
                reference_images=reference_images,
                draft_mode=draft_mode,
            )
            for prompt in prompts
        ]
        return await asyncio.gather(*tasks)

    def _build_prompt(self, panel_desc: str, style_pack: StylePack, aspect_ratio: str) -> str:
        style_lines = [
            f"- Line weight: {style_pack.line_weight:.2f}",
            f"- Contrast: {style_pack.contrast:.2f}",
            f"- Screentone density: {style_pack.screentone_density:.2f}",
            f"- Panel regularity: {style_pack.panel_regularity:.2f}",
            f"- Speed line intensity: {style_pack.speed_line_intensity:.2f}",
            f"- Background detail: {style_pack.background_detail:.2f}",
        ]

        if style_pack.color_palette:
            style_lines.append(f"- Color palette: {', '.join(style_pack.color_palette[:6])}")
        if style_pack.tone_keywords:
            style_lines.append(f"- Tone keywords: {', '.join(style_pack.tone_keywords[:8])}")
        if style_pack.reference_image_urls:
            style_lines.append(
                "- Reference URLs: "
                + ", ".join(str(url) for url in style_pack.reference_image_urls[:4])
            )

        return "\n".join(
            [
                "Generate a polished manga panel illustration.",
                f"Target framing: approximately {aspect_ratio}.",
                f"Panel description: {panel_desc.strip()}",
                "Style requirements:",
                *style_lines,
                "Preserve clear silhouettes, expressive ink work, and readable storytelling.",
            ]
        )

    def _load_image_part(self, path_or_url: str):
        if path_or_url.startswith(("http://", "https://")):
            return types.Part.from_uri(file_uri=path_or_url, mime_type="image/jpeg")

        image_path = Path(path_or_url)
        if not image_path.exists():
            logger.warning("Reference image not found: %s", path_or_url)
            return None

        mime_type = _MIME_MAP.get(image_path.suffix.lower(), "image/png")
        try:
            return types.Part.from_bytes(
                data=image_path.read_bytes(),
                mime_type=mime_type,
            )
        except Exception as exc:
            logger.warning("Failed to load reference image %s: %s", path_or_url, exc)
            return None

    @staticmethod
    def _extract_image_bytes(response) -> bytes:
        if not response.candidates:
            raise ImageAdapterError("No response candidates returned")

        for candidate in response.candidates:
            for part in getattr(candidate.content, "parts", []):
                inline_data = getattr(part, "inline_data", None)
                if inline_data and getattr(inline_data, "data", None):
                    raw_data = inline_data.data
                    return raw_data if isinstance(raw_data, bytes) else base64.b64decode(raw_data)

        raise ImageAdapterError("No inline image data found in Gemini response")
