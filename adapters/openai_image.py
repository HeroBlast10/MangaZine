"""
OpenAI Image Adapter
Wraps OpenAI DALL-E API for manga panel image generation.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Type, TypeVar

from openai import AsyncOpenAI

from adapters.base import BaseImageAdapter, ImageAdapterError
from models.schemas import StylePack

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


class OpenAIImageAdapter(BaseImageAdapter):
    """
    OpenAI DALL-E implementation of BaseImageAdapter.
    
    Uses DALL-E 3 for high-quality manga panel generation.
    Note: DALL-E doesn't support reference images natively.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        from config import Config
        
        resolved_key = api_key or Config.OPENAI_API_KEY
        if not resolved_key:
            raise ImageAdapterError(
                "OpenAI API key not found. "
                "Set OPENAI_API_KEY in .env or pass api_key parameter."
            )
        
        self._model = model or Config.OPENAI_IMAGE_MODEL
        self._client = AsyncOpenAI(api_key=resolved_key)

    async def generate_panel_image(
        self,
        prompt: str,
        style_pack: StylePack,
        reference_images: list[str] | None = None,
        draft_mode: bool = True,
        aspect_ratio: str = "1:1",
    ) -> bytes:
        full_prompt = self._build_prompt(prompt, style_pack)
        
        if reference_images:
            logger.warning(
                "DALL-E does not support reference images. "
                "Reference images will be ignored."
            )
        
        size = self._map_aspect_ratio(aspect_ratio)
        quality = "standard" if draft_mode else "hd"

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._client.images.generate(
                    model=self._model,
                    prompt=full_prompt,
                    size=size,
                    quality=quality,
                    response_format="b64_json",
                    n=1,
                )
                
                if not response.data or not response.data[0].b64_json:
                    raise ImageAdapterError("No image data in response")
                
                return base64.b64decode(response.data[0].b64_json)

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
        style_desc = []
        
        if style_pack.line_weight:
            style_desc.append(f"{style_pack.line_weight} line weight")
        
        if style_pack.color_scheme:
            style_desc.append(f"{style_pack.color_scheme} colors")
        
        if style_pack.rendering_technique:
            style_desc.append(style_pack.rendering_technique)
        
        style_str = ", ".join(style_desc) if style_desc else "manga style"
        
        full_prompt = f"{panel_desc}. Style: {style_str}, clean manga panel art."
        
        if style_pack.forbidden_elements:
            forbidden = ", ".join(style_pack.forbidden_elements)
            full_prompt += f" Avoid: {forbidden}."
        
        return full_prompt[:1000]

    @staticmethod
    def _map_aspect_ratio(aspect_ratio: str) -> str:
        """Map aspect ratio to DALL-E size format."""
        mapping = {
            "1:1": "1024x1024",
            "16:9": "1792x1024",
            "9:16": "1024x1792",
            "3:4": "1024x1536",
            "4:3": "1536x1024",
        }
        return mapping.get(aspect_ratio, "1024x1024")
