"""Writable paths for env file, auth, and Playwright (bundle dir is read-only when frozen)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _frozen_user_data_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Omniclaw"
    if sys.platform == "win32":
        roaming = os.environ.get("APPDATA", "").strip()
        if not roaming:
            roaming = str(Path.home() / "AppData" / "Roaming")
        return Path(roaming) / "Omniclaw"
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    return Path(xdg) / "omniclaw" if xdg else Path.home() / ".config" / "omniclaw"


def playwright_browsers_dir() -> Path:
    """
    Playwright browser downloads (Chromium). Same path is used by the macOS
    postinstall script so the installer and the frozen app agree.
    """
    return user_data_dir() / "ms-playwright"


def user_data_dir() -> Path:
    """
    Writable directory for auth files, Playwright profile, omniclaw.env (frozen), etc.

    Frozen: Application Support (or OS equivalent). Dev: mcp-server/ next to this module.
    """
    if getattr(sys, "frozen", False):
        base = _frozen_user_data_root()
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return base
    return Path(__file__).resolve().parent


def user_config_file() -> Path:
    """
    Shared env file for settings UI, launcher, orchestrator /reload.

    Frozen: under user_data_dir(). Dev: repository root .env.
    """
    if getattr(sys, "frozen", False):
        return user_data_dir() / "omniclaw.env"
    return Path(__file__).resolve().parent.parent / ".env"
