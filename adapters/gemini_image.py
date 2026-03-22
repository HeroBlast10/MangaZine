"""
Gemini Image Adapter
Wraps the Google GenAI SDK for manga panel image generation.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from adapters.base import BaseImageAdapter, ImageAdapterError
from models.schemas import StylePack

_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

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
    """
    Google Gemini implementation of BaseImageAdapter.
    
    Uses Gemini Flash for draft mode and Gemini Pro for final mode.
    """

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
    ) -> bytes:
        model = self._draft_model if draft_mode else self._final_model
        full_prompt = self._build_prompt(prompt, style_pack)
        
        contents = []
        if reference_images:
            for img_path in reference_images:
                img_part = self._load_image_part(img_path)
                if img_part:
                    contents.append(img_part)
        
        contents.append(full_prompt)
        
        config = types.GenerateContentConfig(
            temperature=0.9,
            response_modalities=["image"],
        )

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                
                if not response.candidates or not response.candidates[0].content.parts:
                    raise ImageAdapterError("No image data in response")
                
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        return base64.b64decode(part.inline_data.data)
                
                raise ImageAdapterError("No inline_data found in response parts")

            except ImageAdapterError:
                raise

            except Exception as exc:
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
            f"Image generation failed after {_MAX_RETRIES} retries. Last error: {last_exc}"
        ) from last_exc

    async def generate_batch_images(
        self,
        prompts: list[str],
        style_pack: StylePack,
        reference_images: list[str] | None = None,
        draft_mode: bool = True,
    ) -> list[bytes]:
        tasks = [
            self.generate_panel_image(p, style_pack, reference_images, draft_mode)
            for p in prompts
        ]
        return await asyncio.gather(*tasks)

    def _build_prompt(self, panel_desc: str, style_pack: StylePack) -> str:
        lines = [
            "Generate a manga panel image with the following specifications:",
            "",
            f"Panel description: {panel_desc}",
            "",
            "Style requirements:",
            f"- Line weight: {style_pack.line_weight}",
            f"- Color scheme: {style_pack.color_scheme}",
            f"- Rendering technique: {style_pack.rendering_technique}",
        ]
        
        if style_pack.composition_rules:
            lines.append(f"- Composition: {', '.join(style_pack.composition_rules)}")
        
        if style_pack.forbidden_elements:
            lines.append(f"- Avoid: {', '.join(style_pack.forbidden_elements)}")
        
        lines.extend([
            "",
            "Output a clean manga panel suitable for comic publication.",
        ])
        
        return "\n".join(lines)

    def _load_image_part(self, path_or_url: str):
        if path_or_url.startswith(("http://", "https://")):
            return types.Part.from_uri(file_uri=path_or_url, mime_type="image/jpeg")
        
        img_path = Path(path_or_url)
        if not img_path.exists():
            logger.warning(f"Reference image not found: {path_or_url}")
            return None
        
        mime_type = _MIME_MAP.get(img_path.suffix.lower(), "image/jpeg")
        try:
            with open(img_path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
            return types.Part.from_bytes(data=data, mime_type=mime_type)
        except Exception as exc:
            logger.warning(f"Failed to load reference image {path_or_url}: {exc}")
            return None
