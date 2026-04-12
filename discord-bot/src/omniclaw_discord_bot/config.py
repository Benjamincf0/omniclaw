from __future__ import annotations

import os
from dataclasses import dataclass


def _parse_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int_set(name: str) -> set[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return set()
    values: set[int] = set()
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        values.add(int(item))
    return values


@dataclass(slots=True)
class DiscordBotConfig:
    token: str
    orchestrator_url: str
    require_mention: bool
    allow_dms: bool
    auto_reply_channel_ids: set[int]
    command_guild_ids: set[int]
    reply_char_limit: int
    http_timeout_seconds: float


def load_config() -> DiscordBotConfig:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN is required")

    return DiscordBotConfig(
        token=token,
        orchestrator_url=os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8080")
        .strip()
        .rstrip("/"),
        require_mention=_parse_bool("DISCORD_REQUIRE_MENTION", True),
        allow_dms=_parse_bool("DISCORD_ALLOW_DMS", True),
        auto_reply_channel_ids=_parse_int_set("DISCORD_CHANNEL_IDS"),
        command_guild_ids=_parse_int_set("DISCORD_COMMAND_GUILD_IDS"),
        reply_char_limit=max(200, int(os.getenv("DISCORD_REPLY_CHAR_LIMIT", "1900"))),
        http_timeout_seconds=float(os.getenv("DISCORD_HTTP_TIMEOUT_SECONDS", "90")),
    )
