from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_SYSTEM_PROMPT = """You are Omniclaw, a lightweight assistant for Omnivox workflows.

You can answer normally, but when the user needs live Omnivox data or actions, use the available MCP tools instead of guessing.

Rules:
- Prefer tool calls for live or account-specific information.
- Do not invent Omnivox data.
- If a tool fails, explain the failure plainly and ask for the smallest useful next step.
- Keep replies concise and directly useful.
"""


@dataclass(slots=True)
class McpServerConfig:
    name: str
    url: str
    bearer_token: str | None = None


@dataclass(slots=True)
class AppConfig:
    host: str
    port: int
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    openai_temperature: float
    mcp_servers: list[McpServerConfig]
    history_limit: int
    max_tool_rounds: int
    system_prompt: str


def _parse_named_mapping(raw: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Expected key=value entry, got: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"Expected non-empty key=value entry, got: {item}")
        pairs[key] = value
    return pairs


def _load_mcp_servers() -> list[McpServerConfig]:
    raw_urls = os.getenv(
        "MCP_SERVER_URLS", "omnivox=http://127.0.0.1:8000/mcp"
    ).strip()
    raw_tokens = os.getenv("MCP_SERVER_AUTH_TOKENS", "").strip()

    urls = _parse_named_mapping(raw_urls)
    tokens = _parse_named_mapping(raw_tokens) if raw_tokens else {}

    servers = [
        McpServerConfig(name=name, url=url, bearer_token=tokens.get(name))
        for name, url in urls.items()
    ]
    if not servers:
        raise ValueError("At least one MCP server must be configured")
    return servers


def load_config() -> AppConfig:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required")
    if not model:
        raise ValueError("OPENAI_MODEL is required")

    return AppConfig(
        host=os.getenv("ORCHESTRATOR_HOST", "127.0.0.1").strip(),
        port=int(os.getenv("ORCHESTRATOR_PORT", "8080")),
        openai_api_key=api_key,
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        .strip()
        .rstrip("/"),
        openai_model=model,
        openai_temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
        mcp_servers=_load_mcp_servers(),
        history_limit=max(4, int(os.getenv("ORCHESTRATOR_HISTORY_LIMIT", "24"))),
        max_tool_rounds=max(1, int(os.getenv("ORCHESTRATOR_MAX_TOOL_ROUNDS", "8"))),
        system_prompt=os.getenv("ORCHESTRATOR_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
    )
