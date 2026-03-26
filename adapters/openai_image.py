"""
OpenAI image adapter.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

from openai import AsyncOpenAI

from adapters.base import BaseImageAdapter, GeneratedImageResult, ImageAdapterError
from models.schemas import StylePack

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


class OpenAIImageAdapter(BaseImageAdapter):
    """OpenAI DALL-E implementation of BaseImageAdapter."""

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
    ) -> GeneratedImageResult:
        full_prompt = self._build_prompt(prompt, style_pack, aspect_ratio)
        size = self._map_aspect_ratio(aspect_ratio)
        quality = "standard" if draft_mode else "hd"

        if reference_images:
            logger.warning(
                "DALL-E does not support reference images. "
                "Reference images will be ignored."
            )

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

                return GeneratedImageResult(
                    image_bytes=base64.b64decode(response.data[0].b64_json),
                    model_used=self._model,
                    generation_params={
                        "provider": "openai",
                        "prompt": full_prompt,
                        "aspect_ratio": aspect_ratio,
                        "size": size,
                        "quality": quality,
                        "reference_images_supplied": len(reference_images or []),
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
        style_bits: list[str] = [
            f"line weight {style_pack.line_weight:.2f}",
            f"contrast {style_pack.contrast:.2f}",
            f"screentone density {style_pack.screentone_density:.2f}",
            f"panel regularity {style_pack.panel_regularity:.2f}",
            f"speed line intensity {style_pack.speed_line_intensity:.2f}",
            f"background detail {style_pack.background_detail:.2f}",
        ]

        if style_pack.color_palette:
            style_bits.append(f"palette {' '.join(style_pack.color_palette[:6])}")
        if style_pack.tone_keywords:
            style_bits.append(f"tone {'; '.join(style_pack.tone_keywords[:8])}")
        if style_pack.reference_image_urls:
            style_bits.append(
                f"style references {', '.join(str(url) for url in style_pack.reference_image_urls[:4])}"
            )

        return (
            f"{panel_desc.strip()}\n\n"
            f"Keep a tall manga panel composition with an approximate {aspect_ratio} aspect ratio. "
            f"Style cues: {', '.join(style_bits)}. "
            "Professional manga illustration, crisp inks, readable storytelling."
        )[:2000]

    @staticmethod
    def _map_aspect_ratio(aspect_ratio: str) -> str:
        portrait_ratios = {"9:16", "2:3", "3:4"}
        landscape_ratios = {"16:9", "3:2", "4:3"}

        if aspect_ratio in portrait_ratios:
            return "1024x1792"
        if aspect_ratio in landscape_ratios:
            return "1792x1024"
        return "1024x1024"
