"""
MangaZine — Agent message protocol.

Defines the structured message format that agents use to communicate
through the pipeline.  Every inter-agent payload is wrapped in an
``AgentMessage`` for traceability, causal linking, and audit logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    """
    Structured message exchanged between pipeline agents.

    Attributes
    ----------
    message_id : UUID
        Unique identifier for this message.
    trace_id : UUID
        Shared trace identifier linking all messages in one pipeline run.
    parent_message_id : UUID | None
        The message that caused this one (causal chain).
    source_agent : str
        Name of the agent that produced this message.
    target_agent : str
        Name of the agent that should consume this message.
    message_type : str
        Semantic category of the message.
    payload : dict
        Arbitrary structured data carried by this message.
    timestamp : datetime
        UTC creation time.
    """

    message_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    parent_message_id: UUID | None = None
    source_agent: str
    target_agent: str
    message_type: Literal[
        "request",
        "response",
        "feedback",
        "revision",
        "error",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    model_config = {"frozen": True}


class MessageLog:
    """
    Append-only log of ``AgentMessage`` objects for a single pipeline run.

    Useful for post-hoc analysis, debugging, and audit trails.
    """

    def __init__(self, trace_id: UUID | None = None) -> None:
        self.trace_id = trace_id or uuid4()
        self._messages: list[AgentMessage] = []

    def record(self, msg: AgentMessage) -> None:
        self._messages.append(msg)

    def create_message(
        self,
        source: str,
        target: str,
        msg_type: Literal["request", "response", "feedback", "revision", "error"],
        payload: dict[str, Any] | None = None,
        parent_id: UUID | None = None,
    ) -> AgentMessage:
        msg = AgentMessage(
            trace_id=self.trace_id,
            parent_message_id=parent_id,
            source_agent=source,
            target_agent=target,
            message_type=msg_type,
            payload=payload or {},
        )
        self.record(msg)
        return msg

    @property
    def messages(self) -> list[AgentMessage]:
        return list(self._messages)

    def filter_by_agent(self, agent_name: str) -> list[AgentMessage]:
        return [
            m for m in self._messages
            if m.source_agent == agent_name or m.target_agent == agent_name
        ]

    def to_dicts(self) -> list[dict]:
        return [m.model_dump(mode="json") for m in self._messages]
