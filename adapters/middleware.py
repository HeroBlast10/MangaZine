"""
MangaZine — Adapter middleware: token tracking, cost estimation, and logging.

``TrackedLLMAdapter`` wraps any ``BaseLLMAdapter`` to transparently record
token usage, latency, and estimated cost for every LLM call.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Type, TypeVar

from pydantic import BaseModel

from adapters.base import BaseLLMAdapter

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Rough per-1K-token pricing (USD).  Update as models change.
_COST_PER_1K_INPUT: dict[str, float] = {
    "gemini": 0.00125,
    "openai": 0.005,
}
_COST_PER_1K_OUTPUT: dict[str, float] = {
    "gemini": 0.005,
    "openai": 0.015,
}


@dataclass
class LLMCallRecord:
    """A single tracked LLM invocation."""

    call_id: int
    agent_name: str
    step_name: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    estimated_cost_usd: float
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    success: bool = True
    error: str | None = None


class TokenTracker:
    """
    Accumulates token usage and cost across multiple LLM calls.

    Attach one ``TokenTracker`` per pipeline run and query it at the end
    for aggregate statistics.
    """

    def __init__(self) -> None:
        self._records: list[LLMCallRecord] = []
        self._call_counter: int = 0

    def record(self, rec: LLMCallRecord) -> None:
        self._records.append(rec)

    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self._records)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self._records)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost_usd(self) -> float:
        return sum(r.estimated_cost_usd for r in self._records)

    @property
    def total_calls(self) -> int:
        return len(self._records)

    @property
    def total_latency_ms(self) -> float:
        return sum(r.latency_ms for r in self._records)

    @property
    def records(self) -> list[LLMCallRecord]:
        return list(self._records)

    def next_call_id(self) -> int:
        self._call_counter += 1
        return self._call_counter

    def summary(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_latency_ms": round(self.total_latency_ms, 1),
        }


def _estimate_tokens(text: str) -> int:
    """Rough word-count-based token estimate (1 token ≈ 0.75 words for English)."""
    return max(1, int(len(text.split()) / 0.75))


def _estimate_cost(
    input_tokens: int,
    output_tokens: int,
    provider: str,
) -> float:
    in_rate = _COST_PER_1K_INPUT.get(provider, 0.003)
    out_rate = _COST_PER_1K_OUTPUT.get(provider, 0.01)
    return (input_tokens / 1000) * in_rate + (output_tokens / 1000) * out_rate


class TrackedLLMAdapter(BaseLLMAdapter):
    """
    Decorator adapter that wraps a ``BaseLLMAdapter`` to track usage.

    Usage::

        tracker = TokenTracker()
        tracked_llm = TrackedLLMAdapter(real_llm, tracker, provider="gemini")
        result = await tracked_llm.generate_structured_response(...)
        print(tracker.summary())
    """

    def __init__(
        self,
        inner: BaseLLMAdapter,
        tracker: TokenTracker,
        provider: str = "gemini",
        agent_name: str = "unknown",
        step_name: str = "unknown",
    ) -> None:
        self._inner = inner
        self._tracker = tracker
        self._provider = provider
        self.agent_name = agent_name
        self.step_name = step_name

    async def generate_structured_response(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ) -> T:
        call_id = self._tracker.next_call_id()
        input_tokens = _estimate_tokens(prompt + (system_instruction or ""))
        t0 = time.monotonic()

        try:
            result = await self._inner.generate_structured_response(
                prompt=prompt,
                response_schema=response_schema,
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            elapsed = (time.monotonic() - t0) * 1000

            if isinstance(result, BaseModel):
                output_text = result.model_dump_json()
            else:
                output_text = str(result)
            output_tokens = _estimate_tokens(output_text)
            cost = _estimate_cost(input_tokens, output_tokens, self._provider)

            self._tracker.record(LLMCallRecord(
                call_id=call_id,
                agent_name=self.agent_name,
                step_name=self.step_name,
                model=self._provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=round(elapsed, 1),
                estimated_cost_usd=cost,
            ))
            logger.debug(
                "LLM call #%d (%s/%s): %d in + %d out tokens, %.0f ms, $%.4f",
                call_id, self.agent_name, self.step_name,
                input_tokens, output_tokens, elapsed, cost,
            )
            return result

        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            self._tracker.record(LLMCallRecord(
                call_id=call_id,
                agent_name=self.agent_name,
                step_name=self.step_name,
                model=self._provider,
                input_tokens=input_tokens,
                output_tokens=0,
                latency_ms=round(elapsed, 1),
                estimated_cost_usd=0.0,
                success=False,
                error=str(exc),
            ))
            raise

    async def generate_raw(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ) -> str:
        call_id = self._tracker.next_call_id()
        input_tokens = _estimate_tokens(prompt + (system_instruction or ""))
        t0 = time.monotonic()

        try:
            result = await self._inner.generate_raw(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            elapsed = (time.monotonic() - t0) * 1000
            output_tokens = _estimate_tokens(result)
            cost = _estimate_cost(input_tokens, output_tokens, self._provider)

            self._tracker.record(LLMCallRecord(
                call_id=call_id,
                agent_name=self.agent_name,
                step_name=self.step_name,
                model=self._provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=round(elapsed, 1),
                estimated_cost_usd=cost,
            ))
            return result

        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            self._tracker.record(LLMCallRecord(
                call_id=call_id,
                agent_name=self.agent_name,
                step_name=self.step_name,
                model=self._provider,
                input_tokens=input_tokens,
                output_tokens=0,
                latency_ms=round(elapsed, 1),
                estimated_cost_usd=0.0,
                success=False,
                error=str(exc),
            ))
            raise
