"""
MangaZine — OpenTelemetry tracing integration.

Provides helpers to instrument the pipeline with distributed tracing.
Each pipeline run becomes a trace; each agent step becomes a span.

When the ``opentelemetry`` SDK is not installed, all helpers degrade
gracefully to no-ops so the rest of the codebase never needs to
guard imports.

Usage::

    from orchestrator.tracing import init_tracer, trace_step

    init_tracer("mangazine-pipeline")

    async with trace_step("WriterAgent", "generate_character_bible") as span:
        result = await writer.run(premise)
        span.set_attribute("critic_score", result.final_critic_score)
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any, AsyncIterator, Iterator

logger = logging.getLogger(__name__)

_TRACER_NAME = "mangazine"

# ---------------------------------------------------------------------------
# Try importing OTel; fall back to no-op stubs
# ---------------------------------------------------------------------------

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False


def init_tracer(
    service_name: str = "mangazine-pipeline",
    export_to_console: bool = False,
    otlp_endpoint: str | None = None,
) -> None:
    """
    Initialise the OpenTelemetry TracerProvider.

    Parameters
    ----------
    service_name : str
        Service name reported in spans.
    export_to_console : bool
        If True, spans are printed to stdout (useful for local dev).
    otlp_endpoint : str | None
        If set, spans are exported via OTLP to this endpoint
        (e.g. ``http://localhost:4317`` for a local Jaeger collector).
    """
    if not _HAS_OTEL:
        logger.info("OpenTelemetry SDK not installed — tracing disabled")
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if export_to_console:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except ImportError:
            logger.warning(
                "OTLP exporter requested but opentelemetry-exporter-otlp-proto-grpc "
                "is not installed — skipping."
            )

    trace.set_tracer_provider(provider)
    logger.info("OpenTelemetry tracer initialised (service=%s)", service_name)


def get_tracer():
    """Return the global MangaZine tracer (or a no-op proxy)."""
    if not _HAS_OTEL:
        return _NoOpTracer()
    return trace.get_tracer(_TRACER_NAME)


@contextlib.contextmanager
def trace_step_sync(
    agent_name: str,
    step_name: str,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Synchronous context manager that wraps a block in an OTel span."""
    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"{agent_name}.{step_name}",
        attributes=attributes or {},
    ) as span:
        yield span


@contextlib.asynccontextmanager
async def trace_step(
    agent_name: str,
    step_name: str,
    attributes: dict[str, Any] | None = None,
) -> AsyncIterator[Any]:
    """Async context manager that wraps a block in an OTel span."""
    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"{agent_name}.{step_name}",
        attributes=attributes or {},
    ) as span:
        yield span


# ---------------------------------------------------------------------------
# No-op fallbacks when OTel is not installed
# ---------------------------------------------------------------------------


class _NoOpSpan:
    """Mimics the OTel Span interface with no side effects."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, exc: BaseException) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _NoOpTracer:
    """Mimics the OTel Tracer interface with no side effects."""

    def start_as_current_span(self, name: str, **kwargs) -> _NoOpSpan:
        return _NoOpSpan()

    def start_span(self, name: str, **kwargs) -> _NoOpSpan:
        return _NoOpSpan()
