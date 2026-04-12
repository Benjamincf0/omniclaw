from __future__ import annotations

import uvicorn

from .config import load_config


def main() -> None:
    config = load_config()
    uvicorn.run(
        "omniclaw_orchestrator.server:app",
        host=config.host,
        port=config.port,
        reload=False,
    )
