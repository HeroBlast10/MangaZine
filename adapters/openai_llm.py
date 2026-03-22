"""
OpenAI LLM Adapter
Wraps OpenAI API for structured text generation using function calling.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from adapters.base import BaseLLMAdapter, LLMAdapterError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_DEFAULT_TEMPERATURE = 0.7
_DEFAULT_MAX_TOKENS = 8192
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


class OpenAILLMAdapter(BaseLLMAdapter):
    """
    OpenAI implementation of BaseLLMAdapter.
    
    Uses function calling to enforce structured output conforming to Pydantic schemas.
    Compatible with OpenAI API and compatible endpoints (e.g., DeepSeek, Qwen).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        from config import Config
        
        resolved_key = api_key or Config.OPENAI_API_KEY
        if not resolved_key:
            raise LLMAdapterError(
                "OpenAI API key not found. "
                "Set OPENAI_API_KEY in .env or pass api_key parameter."
            )
        
        self._model = model or Config.OPENAI_TEXT_MODEL
        self._client = AsyncOpenAI(
            api_key=resolved_key,
            base_url=base_url,
        )

    async def generate_structured_response(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: str | None = None,
        temperature: float = _DEFAULT_TEMPERATURE,
        max_output_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> T:
        schema = response_schema.model_json_schema()
        
        function_def = {
            "name": "generate_response",
            "description": f"Generate structured response as {response_schema.__name__}",
            "parameters": schema,
        }
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    functions=[function_def],
                    function_call={"name": "generate_response"},
                    temperature=temperature,
                    max_tokens=max_output_tokens,
                )
                
                if not response.choices or not response.choices[0].message.function_call:
                    raise LLMAdapterError("No function call in response")
                
                func_args = response.choices[0].message.function_call.arguments
                return response_schema.model_validate_json(func_args)

            except (ValidationError, LLMAdapterError) as exc:
                raise LLMAdapterError(f"Validation failed: {exc}") from exc

            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY ** attempt
                    logger.warning(
                        "LLM call failed (attempt %d/%d): %s — retrying in %.1fs",
                        attempt,
                        _MAX_RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise LLMAdapterError(
            f"LLM call failed after {_MAX_RETRIES} retries. Last error: {last_exc}"
        ) from last_exc

    async def generate_raw(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = _DEFAULT_TEMPERATURE,
        max_output_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_output_tokens,
            )
            
            if not response.choices or not response.choices[0].message.content:
                raise LLMAdapterError("No content in response")
            
            return response.choices[0].message.content
            
        except Exception as exc:
            raise LLMAdapterError(f"Raw LLM call failed: {exc}") from exc
