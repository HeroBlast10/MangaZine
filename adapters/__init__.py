"""MangaZine adapter layer — re-exports for convenient top-level imports."""

from adapters.base import (
    BaseLLMAdapter,
    BaseImageAdapter,
    AdapterError,
    LLMAdapterError,
    ImageAdapterError,
)
from adapters.factory import create_llm_adapter, create_image_adapter

# Legacy exports for backward compatibility
from adapters.gemini_llm import GeminiLLMAdapter as LLMAdapter
from adapters.gemini_image import GeminiImageAdapter as ImageAdapter

__all__ = [
    # Factory functions (recommended)
    "create_llm_adapter",
    "create_image_adapter",
    # Base classes
    "BaseLLMAdapter",
    "BaseImageAdapter",
    # Errors
    "AdapterError",
    "LLMAdapterError",
    "ImageAdapterError",
    # Legacy (for backward compatibility)
    "LLMAdapter",
    "ImageAdapter",
]
