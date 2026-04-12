from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = None
    user_id: str | None = None
    user_name: str | None = None
    provider: str | None = None
    model: str | None = None
    message: str = Field(min_length=1)
    clear_history: bool = False


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, Any]


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    provider: str
    model: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    mcp_servers: list[str]
    default_provider: str
    default_model: str
    available_providers: list[str]
