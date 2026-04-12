from __future__ import annotations

from .app import run_app
from .config import load_config


def main() -> None:
    config = load_config()
    run_app(config)
