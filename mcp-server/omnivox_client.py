"""
Authenticated HTTP client for Omnivox.

Handles cookie-based auth with automatic re-authentication
when the session expires or is missing.
"""

import httpx
from auth_manager import load_auth, auth_manager, LOGIN_PAGE_PATTERNS

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


async def ensure_authenticated() -> str:
    """Return valid cookies, triggering auto-login if none are stored."""
    cookies = load_auth()
    if cookies:
        return cookies
    return await auth_manager.authenticate()


async def omnivox_request(
    path: str,
    method: str = "GET",
    **kwargs,
) -> httpx.Response:
    """
    Make an authenticated request to Omnivox.

    If the response indicates an auth failure (401/403 or redirect to login),
    re-authenticates automatically then retries once.
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
            cookies_str = await auth_manager.authenticate(target_url=url)
            if not cookies_str:
                raise RuntimeError("Re-authentication failed")
            headers["Cookie"] = cookies_str
            resp = await client.request(
                method, url, headers=headers, follow_redirects=False, **kwargs
            )

    return resp
