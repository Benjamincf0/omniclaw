"""
Authenticated HTTP client for Omnivox.

Handles cookie-based auth with automatic re-authentication via browser popup
when the session expires or is missing, while preserving module cookies that
Omnivox sets during redirects and module bootstrap.
"""

from typing import Any

import httpx
from auth_manager import (
    authenticate,
    load_auth,
    load_auth_cookies,
    save_auth_cookies,
)

OMNIVOX_BASE = "https://johnabbott.omnivox.ca"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)
LOGIN_PAGE_PATTERNS = (
    "/login",
    "identification=true",
)


def _is_login_url(url: str) -> bool:
    lower = url.lower()
    return any(pattern in lower for pattern in LOGIN_PAGE_PATTERNS)


def _cookie_jar() -> httpx.Cookies:
    jar = httpx.Cookies()
    for cookie in load_auth_cookies() or []:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        domain = cookie.get("domain")
        path = cookie.get("path") or "/"
        if domain:
            jar.set(name, value, domain=domain, path=path)
        else:
            jar.set(name, value, path=path)
    return jar


def _serialize_cookie_jar(cookies: httpx.Cookies) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for cookie in cookies.jar:
        item: dict[str, Any] = {
            "name": cookie.name,
            "value": cookie.value,
            "path": cookie.path or "/",
        }
        if cookie.domain:
            item["domain"] = cookie.domain
        if cookie.expires is not None:
            item["expires"] = cookie.expires
        if cookie.secure:
            item["secure"] = True
        if cookie.has_nonstandard_attr("HttpOnly"):
            item["httpOnly"] = True
        same_site = cookie.get_nonstandard_attr("SameSite")
        if same_site:
            item["sameSite"] = same_site
        serialized.append(item)
    return serialized


def _looks_like_login_page(response: httpx.Response) -> bool:
    try:
        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type:
            return False
        body = response.text.lower()
    except Exception:
        return False
    return "identification=true" in body or 'name="password"' in body


def _is_auth_failure(response: httpx.Response) -> bool:
    """Detect if a response indicates the session has expired or is invalid."""
    if response.status_code in (401, 403):
        return True
    if _is_login_url(str(response.url)):
        return True
    for hop in response.history:
        location = hop.headers.get("location", "")
        if location and _is_login_url(location):
            return True
    if _looks_like_login_page(response):
        return True
    return False


def _resolve_url(path_or_url: str) -> str:
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return f"{OMNIVOX_BASE}{path_or_url}"


def _default_headers() -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": DEFAULT_USER_AGENT,
    }


async def _request_with_saved_session(
    url: str,
    method: str,
    *,
    follow_redirects: bool,
    headers: dict[str, str],
    **kwargs,
) -> httpx.Response:
    async with httpx.AsyncClient(
        verify=False,
        cookies=_cookie_jar(),
        follow_redirects=follow_redirects,
    ) as client:
        response = await client.request(method, url, headers=headers, **kwargs)
        save_auth_cookies(_serialize_cookie_jar(client.cookies))
        return response


async def ensure_authenticated(target_url: str | None = None) -> str:
    """Return valid cookies, prompting browser login if none are stored."""
    cookies = load_auth()
    if cookies:
        return cookies
    return await authenticate(target_url=target_url)


async def omnivox_request_url(
    path_or_url: str,
    method: str = "GET",
    **kwargs,
) -> httpx.Response:
    """
    Make an authenticated request to Omnivox using a persistent cookie jar.

    Omnivox sets extra cookies while crossing modules. Those `Set-Cookie`
    responses are persisted so later requests behave more like a real browser.
    """
    url = _resolve_url(path_or_url)
    await ensure_authenticated(target_url=url)

    follow_redirects = kwargs.pop("follow_redirects", True)
    caller_headers = kwargs.pop("headers", {})
    headers = _default_headers()
    headers.update(caller_headers)

    response = await _request_with_saved_session(
        url,
        method,
        follow_redirects=follow_redirects,
        headers=headers,
        **kwargs,
    )

    if _is_auth_failure(response):
        await authenticate(target_url=url)
        response = await _request_with_saved_session(
            url,
            method,
            follow_redirects=follow_redirects,
            headers=headers,
            **kwargs,
        )

    if _is_auth_failure(response):
        raise PermissionError("Omnivox authentication failed after retry")

    return response


async def omnivox_request(
    path: str,
    method: str = "GET",
    **kwargs,
) -> httpx.Response:
    return await omnivox_request_url(path, method=method, **kwargs)
