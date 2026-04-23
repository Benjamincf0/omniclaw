import asyncio
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from config_paths import playwright_browsers_dir, user_data_dir
from playwright.async_api import Request, async_playwright

OMNIVOX_URL = "https://johnabbott.omnivox.ca"
OMNIVOX_LOGIN_URL = f"{OMNIVOX_URL}/Login/Account/Login"


def _storage_dir() -> Path:
    """Always user-writable (Application Support when frozen, not inside .app bundle)."""
    return user_data_dir()


AUTH_FILE = _storage_dir() / "auth.txt"
AUTH_STATE_FILE = _storage_dir() / "auth_state.json"
PLAYWRIGHT_PROFILE_DIR = _storage_dir() / "omnivox-browser-profile"


def _ensure_browsers_installed() -> None:
    """Install Playwright's Chromium browser if not already present."""
    try:
        from playwright._impl._driver import compute_driver_executable

        driver_exe, driver_cli = compute_driver_executable()
        env = os.environ.copy()
        if getattr(sys, "frozen", False):
            try:
                pb = playwright_browsers_dir()
                pb.mkdir(parents=True, exist_ok=True)
                env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(pb))
            except OSError:
                pass
        result = subprocess.run(
            [str(driver_exe), str(driver_cli), "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        if result.returncode == 0:
            print("[auth] Playwright Chromium browser is ready.")
        else:
            err = (result.stderr or result.stdout or "").strip()
            print(f"[auth] Playwright browser install warning: {err}")
    except Exception as exc:
        print(f"[auth] Could not auto-install Playwright browsers: {exc}")
        print("[auth] Run 'playwright install chromium' manually if login fails.")


def clear_auth_state(*, include_profile: bool = False) -> list[Path]:
    removed: list[Path] = []
    for path in (AUTH_FILE, AUTH_STATE_FILE):
        if path.exists():
            path.unlink()
            removed.append(path)

    if include_profile and PLAYWRIGHT_PROFILE_DIR.exists():
        shutil.rmtree(PLAYWRIGHT_PROFILE_DIR)
        removed.append(PLAYWRIGHT_PROFILE_DIR)

    return removed


def _profile_lock_paths() -> list[Path]:
    return [
        PLAYWRIGHT_PROFILE_DIR / "SingletonCookie",
        PLAYWRIGHT_PROFILE_DIR / "SingletonLock",
        PLAYWRIGHT_PROFILE_DIR / "SingletonSocket",
    ]


def _clear_profile_locks() -> list[Path]:
    removed: list[Path] = []
    for path in _profile_lock_paths():
        if not path.exists() and not path.is_symlink():
            continue
        path.unlink()
        removed.append(path)
    return removed


# Lock so only one Playwright browser runs at a time (browsers are heavy).
_browser_lock = asyncio.Lock()

# After login, Omnivox redirects to URLs containing these patterns
LOGGED_IN_PATTERNS = [
    "/intr/",
    "/main/",
    "/cvir/",
    "/WebApplication/",
    "Module=",
    "Identification=False",
]

LOGIN_PAGE_PATTERNS = [
    "/Login",
    "/login",
    "Identification=True",
]

# 2FA verification-code input selector.
# IMPORTANT: verify this against the actual Omnivox 2FA page HTML and update if needed.
# Open DevTools on the 2FA page and inspect the code input's id/name attribute.
_OTP_INPUT_SELECTOR = "main input.MuiInputBase-input"
_OTP_SUBMIT_SELECTOR = "main button.MuiButton-root[type=button]"


def _is_logged_in(url: str) -> bool:
    return any(pat.lower() in url.lower() for pat in LOGGED_IN_PATTERNS)


def _is_login_page(url: str) -> bool:
    return any(pat.lower() in url.lower() for pat in LOGIN_PAGE_PATTERNS)


def _cookies_to_curl_b(cookies: list[dict]) -> str:
    """Format browser cookies as a curl -b string: key=val; key2=val2"""
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def _omnivox_host() -> str:
    parsed = urlparse(OMNIVOX_URL)
    return parsed.hostname or "johnabbott.omnivox.ca"


def _normalized_cookie(cookie: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "name": str(cookie["name"]),
        "value": str(cookie["value"]),
    }
    for key in ("domain", "path", "expires", "httpOnly", "secure", "sameSite"):
        value = cookie.get(key)
        if value not in (None, ""):
            normalized[key] = value
    if "domain" not in normalized:
        normalized["domain"] = _omnivox_host()
    if "path" not in normalized:
        normalized["path"] = "/"
    return normalized


def _load_cookie_state() -> list[dict[str, Any]] | None:
    if not AUTH_STATE_FILE.exists():
        return None
    try:
        raw = json.loads(AUTH_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, list):
        return None

    cookies: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue
        cookies.append(_normalized_cookie(item))
    return cookies or None


def _load_legacy_cookie_header() -> str | None:
    if AUTH_FILE.exists():
        return AUTH_FILE.read_text(encoding="utf-8").strip() or None
    return None


def _legacy_cookie_header_to_state(cookie_header: str) -> list[dict[str, Any]]:
    cookies: list[dict[str, Any]] = []
    for part in cookie_header.split(";"):
        name, sep, value = part.strip().partition("=")
        if not sep or not name:
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": _omnivox_host(),
                "path": "/",
                "secure": True,
            }
        )
    return cookies


def load_auth_cookies() -> list[dict[str, Any]] | None:
    cookies = _load_cookie_state()
    if cookies:
        return cookies

    legacy = _load_legacy_cookie_header()
    if not legacy:
        return None
    return _legacy_cookie_header_to_state(legacy) or None


def save_auth_cookies(cookies: list[dict[str, Any]] | None) -> str:
    normalized = [
        _normalized_cookie(cookie) for cookie in (cookies or []) if cookie.get("name")
    ]
    AUTH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_STATE_FILE.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    cookie_header = _cookies_to_curl_b(normalized)
    AUTH_FILE.write_text(cookie_header, encoding="utf-8")
    return cookie_header


def _request_to_curl_b(request: Any) -> str | None:
    """Extract the cookie header from a Playwright request (same as curl -b)."""
    headers = request.headers
    cookie = headers.get("cookie")
    return cookie


def _module_hint(url: str) -> str:
    path = urlparse(url).path.lower()
    if path.startswith("/webapplication/module."):
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2:
            return f"/{parts[0]}/{parts[1]}"
    if path.startswith("/intr/"):
        return "/intr"
    return path or "/"


def _login_entry_url() -> str:
    return f"{OMNIVOX_URL}/intr/"


def _is_profile_lock_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "singleton" in message or "processsingleton" in message


async def authenticate(
    target_url: str | None = None,
    *,
    restore_saved_cookies: bool = True,
) -> str:
    """
    Open Omnivox in a real browser, reuse any previously saved cookies,
    optionally warm a specific module URL, capture the refreshed session
    cookies, and save them to disk.
    Returns the cookie string.
    """
    target = target_url or _login_entry_url()
    login_entry = _login_entry_url()
    module_hint = _module_hint(target)

    _ensure_browsers_installed()
    from playwright.async_api import Request, async_playwright

    print(f"Opening Omnivox login page: {login_entry}")
    if target != login_entry:
        print(f"Target module to warm after login: {target}")
    print("Please log in with your credentials. The window will close automatically.\n")
    print(f"Using persistent browser profile: {PLAYWRIGHT_PROFILE_DIR}")

    cookie_body: str | None = None

    async with async_playwright() as pw:
        PLAYWRIGHT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        browser = None
        try:
            context = await pw.chromium.launch_persistent_context(
                str(PLAYWRIGHT_PROFILE_DIR),
                headless=False,
            )
        except Exception as exc:
            if not _is_profile_lock_error(exc):
                raise

            removed = _clear_profile_locks()
            if removed:
                print("[auth] Cleared stale browser profile lock files:")
                for path in removed:
                    print(f"[auth]   - {path}")
                try:
                    context = await pw.chromium.launch_persistent_context(
                        str(PLAYWRIGHT_PROFILE_DIR),
                        headless=False,
                    )
                except Exception as retry_exc:
                    if not _is_profile_lock_error(retry_exc):
                        raise
                    print(
                        "[auth] Persistent browser profile is still locked after cleanup; falling back to a temporary browser context."
                    )
                    browser = await pw.chromium.launch(headless=False)
                    context = await browser.new_context()
            else:
                print(
                    "[auth] Persistent browser profile is still locked; falling back to a temporary browser context."
                )
                browser = await pw.chromium.launch(headless=False)
                context = await browser.new_context()
        if restore_saved_cookies:
            existing_cookies = load_auth_cookies()
            if existing_cookies:
                try:
                    await context.add_cookies(existing_cookies)
                except Exception as exc:
                    print(f"[auth] Could not restore saved cookies: {exc}")
        else:
            await context.clear_cookies()
            print("[auth] Starting with a fresh Omnivox cookie jar.")
        page = await context.new_page()

        captured_cookies: str | None = None
        target_cookies: str | None = None

        async def on_request(request: Request):
            nonlocal captured_cookies, target_cookies
            url = request.url.lower()
            if "omnivox" in url and not _is_login_page(request.url):
                cb = _request_to_curl_b(request)
                if cb:
                    captured_cookies = cb
                    if urlparse(request.url).path.lower().startswith(module_hint):
                        target_cookies = cb

        page.on("request", on_request)

        await page.goto(login_entry)

        print("Waiting for login...")
        poll_interval = 1  # seconds

        while True:
            await asyncio.sleep(poll_interval)

            try:
                current_url = page.url
            except Exception:
                break

            if _is_logged_in(current_url):
                print(f"Detected logged-in URL: {current_url}")
                break

        if target != login_entry:
            print(f"Warming target module: {target}")
            await page.goto(target)

        # Give a moment for target-module requests to fire
        await asyncio.sleep(3)

        # Fallback: grab cookies directly from the browser context
        all_cookies = await context.cookies()
        context_cookie_str = save_auth_cookies(all_cookies)

        cookie_body = target_cookies or captured_cookies or context_cookie_str

        if not cookie_body:
            print("WARNING: No cookies captured. Authentication may have failed.")
            await context.close()
            if browser is not None:
                await browser.close()
            return ""

        print(f"\nCaptured cookie body ({len(cookie_body)} chars)")

        await context.close()
        if browser is not None:
            await browser.close()

    print(f"Saved to {AUTH_FILE} and {AUTH_STATE_FILE}")

    return cookie_body


async def authenticate_for_user(user_id: str, target_url: str | None = None) -> str:
    """
    Open a browser for the student to log in to Omnivox, capture their cookies,
    and persist them to the per-user store (user_tokens.json).

    This is the multi-tenant variant of `authenticate()`.  Only one browser
    window is opened at a time thanks to _browser_lock.
    """
    # Import here to avoid circular imports at module load time.
    from user_store import save_omnivox_cookies

    async with _browser_lock:
        cookies = await authenticate(target_url=target_url)

    if cookies:
        await save_omnivox_cookies(user_id, cookies)

    return cookies


async def authenticate_headless(
    email: str,
    password: str,
    user_id: str,
    otp_callback: Callable[[], Awaitable[str]] | None = None,
    warm_urls: list[str] | None = None,
) -> str:
    """
    Log in to Omnivox programmatically using *email* and *password*.

    Runs a headless Chromium browser, fills the login form, submits it, and
    waits for a post-login redirect.  If Omnivox presents a 2FA verification
    step, *otp_callback* is awaited to obtain the code; it must be provided
    when 2FA is expected, otherwise a RuntimeError is raised.

    Captures and returns the session cookies, persisting them under *user_id*.

    Raises RuntimeError if login fails (wrong credentials, 2FA timeout, etc.).
    """
    from user_store import save_omnivox_cookies

    # Selectors for the JAC Omnivox login page (may need adjustment if Omnivox updates).
    EMAIL_SELECTOR = "#Identifiant"
    PASSWORD_SELECTOR = "#Password"
    SUBMIT_SELECTOR = "#formLogin button[type=submit]"

    cookie_body: str | None = None

    async with _browser_lock:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            captured_cookies: str | None = None

            async def on_request(request: Request) -> None:
                nonlocal captured_cookies
                url = request.url.lower()
                if "omnivox" in url and not _is_login_page(request.url):
                    cb = _request_to_curl_b(request)
                    if cb:
                        captured_cookies = cb

            page.on("request", on_request)

            # Navigate to the login page.
            await page.goto(OMNIVOX_LOGIN_URL, wait_until="domcontentloaded")

            # Fill in credentials.
            try:
                await page.fill(EMAIL_SELECTOR, email)
                await page.fill(PASSWORD_SELECTOR, password)
                await page.click(SUBMIT_SELECTOR)
                await asyncio.sleep(2)
            except Exception as exc:
                await browser.close()
                raise RuntimeError(
                    f"Could not interact with Omnivox login form: {exc}"
                ) from exc

            # Wait for the page to settle after credential submit.
            try:
                await page.wait_for_load_state("networkidle", timeout=9000)
            except Exception:
                pass  # Timeout is fine; we check the URL state below.

            if not _is_logged_in(page.url):
                if await page.query_selector(_OTP_INPUT_SELECTOR):
                    # Omnivox presented a 2FA / verification-code step.
                    if otp_callback is None:
                        await browser.close()
                        raise RuntimeError(
                            "Omnivox requires a verification code but no callback was provided."
                        )
                    try:
                        print("Waiting for 2FA code...")
                        code = await otp_callback()
                        print(f"2FA code: {code} tyoe: {type(code)}")
                    except Exception:
                        print("2FA code callback failed.")
                        await browser.close()
                        raise
                    try:
                        print(
                            f"Submitting 2FA code...{code} {_OTP_INPUT_SELECTOR}, {_OTP_SUBMIT_SELECTOR}"
                        )
                        await page.fill(_OTP_INPUT_SELECTOR, code)
                        # await asyncio.sleep(15)
                        await page.click(_OTP_SUBMIT_SELECTOR)
                    except Exception as exc:
                        await browser.close()
                        raise RuntimeError(
                            f"Could not submit verification code: {exc}"
                        ) from exc

                    # Wait for login after 2FA (up to 15 s).
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    for _ in range(30):
                        await asyncio.sleep(0.5)
                        if _is_logged_in(page.url):
                            break
                    else:
                        await browser.close()
                        raise RuntimeError(
                            "Omnivox 2FA verification failed or timed out."
                        )
                else:
                    # Not logged in and no OTP field → wrong credentials.
                    await browser.close()
                    raise RuntimeError(
                        "Omnivox login failed — check your student ID and password."
                    )

            # Navigate to each warm URL so module-specific session tokens are
            # issued and captured in the browser context's cookie jar.
            for warm_url in warm_urls or []:
                try:
                    await page.goto(
                        warm_url, wait_until="domcontentloaded", timeout=10000
                    )
                    await asyncio.sleep(1)
                except Exception as exc:
                    print(f"[auth] Warning: could not warm {warm_url}: {exc}")

            # Give a moment for post-login requests to fire so we capture cookies.
            await asyncio.sleep(2)

            # Fallback: pull cookies directly from the browser context.
            all_cookies = await context.cookies()
            context_cookie_str = _cookies_to_curl_b(all_cookies)
            cookie_body = captured_cookies or context_cookie_str

            await browser.close()

    if not cookie_body:
        raise RuntimeError("Omnivox login succeeded but no cookies were captured.")

    await save_omnivox_cookies(user_id, cookie_body)
    return cookie_body


def load_auth() -> str | None:
    """Load previously saved auth cookies as a Cookie header string."""
    cookies = load_auth_cookies()
    if cookies:
        return _cookies_to_curl_b(cookies)
    return _load_legacy_cookie_header()


if __name__ == "__main__":
    asyncio.run(authenticate())
