"""
Authenticated HTTP client for Omnivox.

Checks auth.txt upfront: if missing or expired, launches the Playwright
browser login *before* making any real request.
"""

import httpx
from auth_manager import (
    LOGIN_PAGE_PATTERNS,
    MfaCodeProvider,
    authenticate,
    load_auth,
    validate_auth,
)

OMNIVOX_BASE = "https://johnabbott.omnivox.ca"


def _is_auth_failure(response: httpx.Response) -> bool:
    if response.status_code in (401, 403):
        return True
    location = response.headers.get("location", "").lower()
    if any(pat.lower() in location for pat in LOGIN_PAGE_PATTERNS):
        return True
    body = response.text.lower()
    return any(pat.lower() in body for pat in LOGIN_PAGE_PATTERNS)


async def ensure_authenticated(
    mfa_code_provider: MfaCodeProvider | None = None,
) -> str:
    """
    Return valid cookies.  Checks auth.txt -> validates with a test request ->
    launches Playwright browser login if missing or expired.
    """
    cookies = load_auth()
    if cookies and await validate_auth(cookies):
        return cookies

    return await authenticate(mfa_code_provider=mfa_code_provider)


async def omnivox_request(
    path: str,
    method: str = "GET",
    *,
    mfa_code_provider: MfaCodeProvider | None = None,
    **kwargs,
) -> httpx.Response:
    """
    Make an authenticated request to Omnivox.

    If the response indicates an auth failure (401/403 or redirect to login),
    opens a browser popup for the user to re-login, then retries once.
    """
    url = f"{OMNIVOX_BASE}{path}"
    cookies_str = await ensure_authenticated(mfa_code_provider=mfa_code_provider)
    if not cookies_str:
        raise RuntimeError("Authentication failed — no cookies obtained")

    headers = kwargs.pop("headers", {})
    headers["Cookie"] = cookies_str

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method, url, headers=headers, follow_redirects=False, **kwargs
        )

        if _is_auth_failure(resp):
            cookies_str = await authenticate(target_url=url, mfa_code_provider=mfa_code_provider)
            if not cookies_str:
                raise RuntimeError("Re-authentication failed")
            headers["Cookie"] = cookies_str
            resp = await client.request(
                method, url, headers=headers, follow_redirects=False, **kwargs
            )

    return resp
