import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Request, async_playwright

OMNIVOX_URL = "https://johnabbott.omnivox.ca"
OMNIVOX_LOGIN_URL = f"{OMNIVOX_URL}/Login/Account/Login"
AUTH_FILE = Path(__file__).parent / "auth.txt"

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


def _request_to_curl_b(request: Request) -> str | None:
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


async def authenticate(target_url: str | None = None) -> str:
    """
    Open Omnivox in a real browser, wait for the user to log in,
    optionally warm a specific module URL, capture the session cookies
    (curl -b format), and save to auth.txt.
    Returns the cookie string.
    """
    target = target_url or OMNIVOX_LOGIN_URL
    module_hint = _module_hint(target)

    print(f"Opening Omnivox login page: {target}")
    print("Please log in with your credentials. The window will close automatically.\n")

    cookie_body: str | None = None

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
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

        await page.goto(OMNIVOX_LOGIN_URL)

        # DEBUG: wait 10 seconds after opening the login page
        print("DEBUG: waiting 1 seconds after page load...")
        await asyncio.sleep(1)

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

        if target not in (OMNIVOX_URL, OMNIVOX_LOGIN_URL):
            print(f"Warming target module: {target}")
            await page.goto(target)

        # Give a moment for target-module requests to fire
        await asyncio.sleep(3)

        # Fallback: grab cookies directly from the browser context
        all_cookies = await context.cookies()
        context_cookie_str = _cookies_to_curl_b(all_cookies)

        cookie_body = target_cookies or captured_cookies or context_cookie_str

        if not cookie_body:
            print("WARNING: No cookies captured. Authentication may have failed.")
            await browser.close()
            return ""

        print(f"\nCaptured cookie body ({len(cookie_body)} chars)")

        await browser.close()

    AUTH_FILE.write_text(cookie_body, encoding="utf-8")
    print(f"Saved to {AUTH_FILE}")

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
            browser = await pw.chromium.launch(headless=False)
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
                await asyncio.sleep(10)
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
    """Load previously saved auth cookies from auth.txt, or None if missing."""
    if AUTH_FILE.exists():
        return AUTH_FILE.read_text(encoding="utf-8").strip() or None
    return None


if __name__ == "__main__":
    asyncio.run(authenticate())
