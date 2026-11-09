"""Contratos de entrada e saída da API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Intent = Literal["greeting", "order_status", "knowledge", "handoff", "unknown"]
Mode = Literal["llm", "offline"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000, examples=["Cadê meu pedido PED-1002?"])
    session_id: str | None = Field(default=None, max_length=64)


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class AgentReply(BaseModel):
    session_id: str
    answer: str
    intent: Intent
    mode: Mode
    sources: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    handed_off: bool = False
    ticket_id: str | None = None
