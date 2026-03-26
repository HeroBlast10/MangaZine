"""
Base adapter interfaces for MangaZine.
Defines abstract interfaces that all LLM and Image providers must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Type, TypeVar

from pydantic import BaseModel

from models.schemas import StylePack

T = TypeVar("T", bound=BaseModel)


@dataclass
class GeneratedImageResult:
    """Container for image bytes plus reproducibility metadata."""

    image_bytes: bytes
    model_used: str
    generation_params: dict[str, object] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseLLMAdapter(ABC):
    """
    Abstract base class for LLM adapters.
    
    All text generation providers (Gemini, OpenAI, etc.) must implement
    this interface to ensure consistent behavior across the pipeline.
    """
    
    @abstractmethod
    async def generate_structured_response(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ) -> T:
        """
        Generate a structured response constrained by a Pydantic schema.
        
        Parameters
        ----------
        prompt : str
            User-facing prompt text.
        response_schema : Type[T]
            Pydantic V2 model class to constrain the response.
        system_instruction : str | None
            Optional system-level instruction.
        temperature : float
            Sampling temperature (0 = deterministic, 1 = creative).
        max_output_tokens : int
            Maximum tokens in the response.
        
        Returns
        -------
        T
            Validated instance of response_schema.
        
        Raises
        ------
        LLMAdapterError
            If generation fails after retries or validation fails.
        """
        pass
    
    @abstractmethod
    async def generate_raw(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ) -> str:
        """
        Generate a raw text response with no schema constraint.
        
        Parameters
        ----------
        prompt : str
            User-facing prompt text.
        system_instruction : str | None
            Optional system-level instruction.
        temperature : float
            Sampling temperature.
        max_output_tokens : int
            Maximum tokens in the response.
        
        Returns
        -------
        str
            Raw text response.
        
        Raises
        ------
        LLMAdapterError
            If generation fails.
        """
        pass


class BaseImageAdapter(ABC):
    """
    Abstract base class for image generation adapters.
    
    All image providers (Gemini, DALL-E, Seedream, etc.) must implement
    this interface for panel image generation.
    """
    
    @abstractmethod
    async def generate_panel_image(
        self,
        prompt: str,
        style_pack: StylePack,
        reference_images: list[str] | None = None,
        draft_mode: bool = True,
        aspect_ratio: str = "1:1",
    ) -> GeneratedImageResult:
        """
        Generate a manga panel image from a text prompt.
        
        Parameters
        ----------
        prompt : str
            Panel description (action, setting, characters, etc.).
        style_pack : StylePack
            Visual style parameters (line weight, color scheme, etc.).
        reference_images : list[str] | None
            Optional list of reference image URLs or local paths.
        draft_mode : bool
            If True, use faster/cheaper model. If False, use high-quality model.
        aspect_ratio : str
            Image aspect ratio (e.g., "1:1", "16:9", "3:4").
        
        Returns
        -------
        GeneratedImageResult
            Image bytes plus model metadata.
        
        Raises
        ------
        ImageAdapterError
            If image generation fails after retries.
        """
        pass
    
    @abstractmethod
    async def generate_batch_images(
        self,
        prompts: list[str],
        style_pack: StylePack,
        reference_images: list[str] | None = None,
        draft_mode: bool = True,
    ) -> list[GeneratedImageResult]:
        """
        Generate multiple panel images in parallel.
        
        Default implementation calls generate_panel_image() sequentially.
        Providers with native batch support should override this.
        
        Parameters
        ----------
        prompts : list[str]
            List of panel descriptions.
        style_pack : StylePack
            Shared visual style for all panels.
        reference_images : list[str] | None
            Optional reference images.
        draft_mode : bool
            Draft vs. final quality mode.
        
        Returns
        -------
        list[GeneratedImageResult]
            List of image results.
        """
        pass


class AdapterError(Exception):
    """Base exception for adapter errors."""
    pass


class LLMAdapterError(AdapterError):
    """Raised when LLM adapter encounters an unrecoverable error."""
    pass


class ImageAdapterError(AdapterError):
    """Raised when image adapter encounters an unrecoverable error."""
    pass
