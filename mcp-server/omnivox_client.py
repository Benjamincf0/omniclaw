"""
Authenticated HTTP client for Omnivox.

Two modes:
  - Legacy (single-user): uses auth.txt via load_auth() / authenticate().
  - Multi-tenant: takes an explicit user_id and reads cookies from user_store.

Both modes automatically detect auth failures and trigger re-login via a
headless browser popup, then retry the request once.
"""

from __future__ import annotations

import httpx
from auth_manager import (
    authenticate,
    authenticate_for_user,
    load_auth,
    LOGIN_PAGE_PATTERNS,
)
from user_store import get_omnivox_cookies, save_omnivox_cookies

OMNIVOX_BASE = "https://johnabbott.omnivox.ca"


def _is_auth_failure(response: httpx.Response) -> bool:
    """Detect if a response indicates the session has expired or is invalid."""
    if response.status_code in (401, 403):
        return True
    if response.status_code in (301, 302, 303, 307, 308):
        location = response.headers.get("location", "")
        if any(pat.lower() in location.lower() for pat in LOGIN_PAGE_PATTERNS):
            return True
    return False


# ── Legacy single-user helpers (kept for backward-compat with test files) ─────


async def ensure_authenticated() -> str:
    """Return valid cookies for the legacy single-user flow (auth.txt)."""
    cookies = load_auth()
    if cookies:
        return cookies
    return await authenticate()


async def omnivox_request(
    path: str,
    method: str = "GET",
    **kwargs,
) -> httpx.Response:
    """
    Make an authenticated request to Omnivox (legacy single-user mode).

    If the response indicates an auth failure (401/403 or redirect to login),
    opens a browser popup for the user to re-login, then retries once.
    """
    url = f"{OMNIVOX_BASE}{path}"
    cookies_str = await ensure_authenticated()
    if not cookies_str:
        raise RuntimeError("Authentication failed — no cookies obtained")

    headers = kwargs.pop("headers", {})
    headers["Cookie"] = cookies_str

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method, url, headers=headers, follow_redirects=False, **kwargs
        )

        if _is_auth_failure(resp):
            cookies_str = await authenticate(target_url=url)
            if not cookies_str:
                raise RuntimeError("Re-authentication failed")
            headers["Cookie"] = cookies_str
            resp = await client.request(
                method, url, headers=headers, follow_redirects=False, **kwargs
            )

    return resp


# ── Multi-tenant per-user request ─────────────────────────────────────────────


async def omnivox_request_for_user(
    user_id: str,
    path: str,
    method: str = "GET",
    **kwargs,
) -> httpx.Response:
    """
    Make an authenticated Omnivox request on behalf of *user_id*.

    Looks up that user's cookies from user_store.  If none are stored, raises
    PermissionError telling the caller to link the account first.

    On auth failure, triggers a new browser login for that user and retries once.
    """
    url = f"{OMNIVOX_BASE}{path}"
    cookies_str = await get_omnivox_cookies(user_id)

    if not cookies_str:
        raise PermissionError(
            f"No Omnivox session found for user '{user_id}'. "
            "Please visit /link-omnivox to connect your Omnivox account."
        )

    headers = kwargs.pop("headers", {})
    headers["Cookie"] = cookies_str

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method, url, headers=headers, follow_redirects=False, **kwargs
        )

        if _is_auth_failure(resp):
            # Session expired — re-authenticate and save the new cookies.
            new_cookies = await authenticate_for_user(user_id, target_url=url)
            if not new_cookies:
                raise PermissionError(
                    f"Re-authentication failed for user '{user_id}'. "
                    "Please visit /link-omnivox to reconnect your Omnivox account."
                )
            headers["Cookie"] = new_cookies
            resp = await client.request(
                method, url, headers=headers, follow_redirects=False, **kwargs
            )

    return resp
