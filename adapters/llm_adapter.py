"""
MangaZine LLM Adapter — backward-compatibility shim.

This module formerly contained a standalone Gemini LLM implementation.
All logic now lives in ``adapters.gemini_llm.GeminiLLMAdapter`` (which
extends ``adapters.base.BaseLLMAdapter``).

Any code doing ``from adapters.llm_adapter import LLMAdapter`` will
transparently receive ``GeminiLLMAdapter``, and ``LLMAdapterError``
comes from the shared ``adapters.base`` module.
"""

from adapters.base import BaseLLMAdapter, LLMAdapterError  # noqa: F401
from adapters.gemini_llm import GeminiLLMAdapter as LLMAdapter  # noqa: F401

__all__ = ["LLMAdapter", "LLMAdapterError", "BaseLLMAdapter"]
