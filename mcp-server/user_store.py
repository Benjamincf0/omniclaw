"""
Per-user Omnivox cookie store.

Cookies are stored in a JSON file (user_tokens.json) keyed by the user's
Auth0 subject (sub claim).  Each entry is just the raw Omnivox cookie string
in curl -b format.

File layout:
    {
        "auth0|abc123": "TKINTR=...; TKSJACP=...; ...",
        "auth0|def456": "..."
    }

The file is kept on disk so cookies survive server restarts.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

_STORE_FILE = Path(__file__).parent / "user_tokens.json"
_lock = asyncio.Lock()


def _read_store() -> dict[str, str]:
    """Read the store file synchronously (call only while holding the lock)."""
    if _STORE_FILE.exists():
        try:
            return json.loads(_STORE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _write_store(data: dict[str, str]) -> None:
    """Write the store file synchronously (call only while holding the lock)."""
    _STORE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


async def get_omnivox_cookies(user_id: str) -> str | None:
    """Return the stored Omnivox cookie string for *user_id*, or None."""
    async with _lock:
        store = _read_store()
    return store.get(user_id)


async def save_omnivox_cookies(user_id: str, cookies: str) -> None:
    """Persist *cookies* for *user_id* (overwrites any existing entry)."""
    async with _lock:
        store = _read_store()
        store[user_id] = cookies
        _write_store(store)


async def delete_omnivox_cookies(user_id: str) -> bool:
    """Remove the entry for *user_id*.  Returns True if it existed."""
    async with _lock:
        store = _read_store()
        existed = user_id in store
        if existed:
            del store[user_id]
            _write_store(store)
    return existed


async def has_omnivox_cookies(user_id: str) -> bool:
    """Return True if the user has a stored cookie string."""
    async with _lock:
        store = _read_store()
    return bool(store.get(user_id))
