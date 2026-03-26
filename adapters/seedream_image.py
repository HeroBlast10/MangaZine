"""
Seedream image adapter.
"""

from __future__ import annotations

import asyncio
import base64
import logging

from openai import AsyncOpenAI

from adapters.base import BaseImageAdapter, GeneratedImageResult, ImageAdapterError
from models.schemas import StylePack

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


class SeedreamImageAdapter(BaseImageAdapter):
    """ByteDance Seedream implementation of BaseImageAdapter."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        from config import Config

        resolved_key = api_key or Config.SEEDREAM_API_KEY
        if not resolved_key:
            raise ImageAdapterError(
                "Seedream API key not found. "
                "Set SEEDREAM_API_KEY in .env or pass api_key parameter."
            )

        self._model = model or Config.SEEDREAM_IMAGE_MODEL
        self._base_url = base_url or Config.SEEDREAM_BASE_URL
        self._client = AsyncOpenAI(
            api_key=resolved_key,
            base_url=self._base_url,
        )

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

        if reference_images:
            logger.warning(
                "Seedream reference image support is not implemented. "
                "Reference images will be ignored."
            )

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._client.images.generate(
                    model=self._model,
                    prompt=full_prompt,
                    size=size,
                    response_format="b64_json",
                    n=1,
                )

                if not response.data or not response.data[0].b64_json:
                    raise ImageAdapterError("No image data in response")

                return GeneratedImageResult(
                    image_bytes=base64.b64decode(response.data[0].b64_json),
                    model_used=self._model,
                    generation_params={
                        "provider": "seedream",
                        "prompt": full_prompt,
                        "aspect_ratio": aspect_ratio,
                        "size": size,
                        "base_url": self._base_url,
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
        style_bits = [
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

        return (
            f"{panel_desc.strip()}\n\n"
            f"Create a professional manga panel with an approximate {aspect_ratio} framing. "
            f"Style cues: {', '.join(style_bits)}."
        )

    @staticmethod
    def _map_aspect_ratio(aspect_ratio: str) -> str:
        mapping = {
            "1:1": "1024x1024",
            "16:9": "1792x1024",
            "9:16": "1024x1792",
            "2:3": "1024x1536",
            "3:4": "1024x1536",
            "3:2": "1536x1024",
            "4:3": "1536x1024",
        }
        return mapping.get(aspect_ratio, "1024x1024")
