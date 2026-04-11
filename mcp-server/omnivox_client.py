"""
Authenticated HTTP client for Omnivox.

Checks auth.txt upfront: if missing or expired, launches the Playwright
browser login *before* making any real request.
"""

import httpx
from auth_manager import load_auth, authenticate, validate_auth, LOGIN_PAGE_PATTERNS

OMNIVOX_BASE = "https://johnabbott.omnivox.ca"


def _is_auth_failure(response: httpx.Response) -> bool:
    if response.status_code in (401, 403):
        return True
    location = response.headers.get("location", "").lower()
    if any(pat.lower() in location for pat in LOGIN_PAGE_PATTERNS):
        return True
    body = response.text.lower()
    return any(pat.lower() in body for pat in LOGIN_PAGE_PATTERNS)


async def ensure_authenticated() -> str:
    """
    Return valid cookies.  Checks auth.txt → validates with a test request →
    launches Playwright browser login if missing or expired.
    """
    cookies = load_auth()
    if cookies and await validate_auth(cookies):
        return cookies

    return await authenticate()


async def omnivox_request(
    path: str,
    method: str = "GET",
    **kwargs,
) -> httpx.Response:
    cookies_str = await ensure_authenticated()
    if not cookies_str:
        raise RuntimeError("Authentication failed — no cookies obtained")

    url = f"{OMNIVOX_BASE}{path}"
    headers = kwargs.pop("headers", {})
    headers["Cookie"] = cookies_str

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method, url, headers=headers, follow_redirects=False, **kwargs
        )

        if _is_auth_failure(resp):
            cookies_str = await authenticate()
            if not cookies_str:
                raise RuntimeError("Re-authentication failed")
            headers["Cookie"] = cookies_str
            resp = await client.request(
                method, url, headers=headers, follow_redirects=False, **kwargs
            )

    return resp
