"""
Adapter Factory
Creates LLM and Image adapters based on configuration.
"""

from __future__ import annotations

from adapters.base import BaseLLMAdapter, BaseImageAdapter
from config import Config, LLMProvider, ImageProvider


def create_llm_adapter(
    provider: LLMProvider | None = None,
    **kwargs,
) -> BaseLLMAdapter:
    """
    Create an LLM adapter based on provider selection.
    
    Parameters
    ----------
    provider : LLMProvider | None
        Override Config.LLM_PROVIDER if specified.
    **kwargs
        Additional arguments passed to adapter constructor.
    
    Returns
    -------
    BaseLLMAdapter
        Configured LLM adapter instance.
    """
    provider = provider or Config.LLM_PROVIDER
    
    if provider == LLMProvider.GEMINI:
        from adapters.gemini_llm import GeminiLLMAdapter
        return GeminiLLMAdapter(**kwargs)
    
    elif provider == LLMProvider.OPENAI:
        from adapters.openai_llm import OpenAILLMAdapter
        return OpenAILLMAdapter(**kwargs)
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def create_image_adapter(
    provider: ImageProvider | None = None,
    **kwargs,
) -> BaseImageAdapter:
    """
    Create an image adapter based on provider selection.
    
    Parameters
    ----------
    provider : ImageProvider | None
        Override Config.IMAGE_PROVIDER if specified.
    **kwargs
        Additional arguments passed to adapter constructor.
    
    Returns
    -------
    BaseImageAdapter
        Configured image adapter instance.
    """
    provider = provider or Config.IMAGE_PROVIDER
    
    if provider == ImageProvider.GEMINI:
        from adapters.gemini_image import GeminiImageAdapter
        return GeminiImageAdapter(**kwargs)
    
    elif provider == ImageProvider.OPENAI:
        from adapters.openai_image import OpenAIImageAdapter
        return OpenAIImageAdapter(**kwargs)
    
    elif provider == ImageProvider.SEEDREAM:
        from adapters.seedream_image import SeedreamImageAdapter
        return SeedreamImageAdapter(**kwargs)
    
    else:
        raise ValueError(f"Unsupported image provider: {provider}")
