"""
MangaZine Configuration
Centralized configuration for multi-backend adapter selection.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).parent
load_dotenv(_PROJECT_ROOT / ".env")


class LLMProvider(str, Enum):
    """Supported LLM providers for text generation."""
    GEMINI = "gemini"
    OPENAI = "openai"


class ImageProvider(str, Enum):
    """Supported image generation providers."""
    GEMINI = "gemini"
    OPENAI = "openai"
    SEEDREAM = "seedream"


class Config:
    """
    Global configuration for MangaZine adapters.
    
    Environment variables:
    - LLM_PROVIDER: "gemini" (default) or "openai"
    - IMAGE_PROVIDER: "gemini" (default), "openai", or "seedream"
    - GOOGLE_API_KEY: for Gemini
    - OPENAI_API_KEY: for OpenAI
    - SEEDREAM_API_KEY: for Seedream (Bytedance Doubao/豆包)
    """
    
    # LLM Configuration
    LLM_PROVIDER: LLMProvider = LLMProvider(
        os.getenv("LLM_PROVIDER", "gemini")
    )
    
    # Image Configuration
    IMAGE_PROVIDER: ImageProvider = ImageProvider(
        os.getenv("IMAGE_PROVIDER", "gemini")
    )
    
    # API Keys
    GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    SEEDREAM_API_KEY: str | None = os.getenv("SEEDREAM_API_KEY")
    
    # Model names
    GEMINI_TEXT_MODEL: str = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")
    GEMINI_IMAGE_DRAFT_MODEL: str = os.getenv("GEMINI_IMAGE_DRAFT_MODEL", "gemini-3.1-flash-image-preview")
    GEMINI_IMAGE_FINAL_MODEL: str = os.getenv("GEMINI_IMAGE_FINAL_MODEL", "gemini-3-pro-image-preview")
    
    OPENAI_TEXT_MODEL: str = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")
    OPENAI_IMAGE_MODEL: str = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
    
    SEEDREAM_IMAGE_MODEL: str = os.getenv("SEEDREAM_IMAGE_MODEL", "seedream-v1")
    SEEDREAM_BASE_URL: str = os.getenv("SEEDREAM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    
    # Generation parameters
    DEFAULT_TEMPERATURE: float = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
    DEFAULT_MAX_TOKENS: int = int(os.getenv("DEFAULT_MAX_TOKENS", "8192"))
    
    # Output configuration
    OUTPUT_DIR: Path = _PROJECT_ROOT / "output"
    USE_UNIQUE_PROJECT_FOLDERS: bool = os.getenv("USE_UNIQUE_PROJECT_FOLDERS", "true").lower() == "true"
    
    @classmethod
    def validate(cls) -> None:
        """Validate that required API keys are present for selected providers."""
        if cls.LLM_PROVIDER == LLMProvider.GEMINI and not cls.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY required when LLM_PROVIDER=gemini")
        if cls.LLM_PROVIDER == LLMProvider.OPENAI and not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY required when LLM_PROVIDER=openai")
        
        if cls.IMAGE_PROVIDER == ImageProvider.GEMINI and not cls.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY required when IMAGE_PROVIDER=gemini")
        if cls.IMAGE_PROVIDER == ImageProvider.OPENAI and not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY required when IMAGE_PROVIDER=openai")
        if cls.IMAGE_PROVIDER == ImageProvider.SEEDREAM and not cls.SEEDREAM_API_KEY:
            raise ValueError("SEEDREAM_API_KEY required when IMAGE_PROVIDER=seedream")
