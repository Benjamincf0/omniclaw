from __future__ import annotations

import getpass
import os
import socket
import uuid
from dataclasses import dataclass


def _default_user_name() -> str:
    return getpass.getuser().strip() or "terminal-user"


def _default_session_id(user_name: str) -> str:
    host = socket.gethostname().strip() or "localhost"
    return f"tui:{host}:{user_name}:{uuid.uuid4().hex[:8]}"


@dataclass(slots=True)
class TuiConfig:
    orchestrator_url: str
    session_id: str
    user_id: str
    user_name: str
    provider: str | None
    model: str | None
    http_timeout_seconds: float


def load_config() -> TuiConfig:
    user_name = os.getenv("TUI_USER_NAME", "").strip() or _default_user_name()
    user_id = os.getenv("TUI_USER_ID", "").strip() or user_name
    session_id = os.getenv("TUI_SESSION_ID", "").strip() or _default_session_id(user_name)
    provider = os.getenv("TUI_PROVIDER", "").strip() or None
    model = os.getenv("TUI_MODEL", "").strip() or None

    return TuiConfig(
        orchestrator_url=os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8080")
        .strip()
        .rstrip("/"),
        session_id=session_id,
        user_id=user_id,
        user_name=user_name,
        provider=provider,
        model=model,
        http_timeout_seconds=float(os.getenv("TUI_HTTP_TIMEOUT_SECONDS", "90")),
    )
