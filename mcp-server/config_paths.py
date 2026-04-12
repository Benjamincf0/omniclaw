"""Where Omniclaw reads/writes shared env (settings UI, launcher, orchestrator /reload)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def user_config_file() -> Path:
    """
    Writable env file path.

    Frozen: user data dir — the .app bundle is often read-only under /Applications.
    Dev: repository root .env (unchanged from historical MCP settings behavior).
    """
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            base = Path.home() / "Library/Application Support/Omniclaw"
        elif sys.platform == "win32":
            roaming = os.environ.get("APPDATA", "").strip()
            if not roaming:
                roaming = str(Path.home() / "AppData" / "Roaming")
            base = Path(roaming) / "Omniclaw"
        else:
            xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
            base = Path(xdg) / "omniclaw" if xdg else Path.home() / ".config" / "omniclaw"
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return base / "omniclaw.env"

    return Path(__file__).resolve().parent.parent / ".env"
