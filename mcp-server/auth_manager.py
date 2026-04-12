import asyncio
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Request

OMNIVOX_URL = "https://johnabbott.omnivox.ca"
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
    target = target_url or OMNIVOX_URL
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

        await page.goto(target)

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

        if target != OMNIVOX_URL:
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
) -> str:
    """
    Log in to Omnivox programmatically using *email* and *password*.

    Runs a headless Chromium browser, fills the login form, submits it,
    waits for a post-login redirect, then captures and returns the session
    cookies.  Persists them to user_tokens.json under *user_id*.

    Raises RuntimeError if login fails (wrong credentials, unexpected page, etc.).
    """
    from user_store import save_omnivox_cookies

    LOGIN_URL = (
        f"{OMNIVOX_URL}/intr/Module/Identification/Login/LoginJAC.aspx?C=JAC&L=ANG"
    )
    # Selectors for the JAC Omnivox login page (may need adjustment if Omnivox updates).
    EMAIL_SELECTOR = "#Identifiant"
    PASSWORD_SELECTOR = "#SaisieMotPasse"
    SUBMIT_SELECTOR = "#BoutonSoumettre"

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
            await page.goto(LOGIN_URL, wait_until="domcontentloaded")

            # Fill in credentials.
            try:
                await page.fill(EMAIL_SELECTOR, email)
                await page.fill(PASSWORD_SELECTOR, password)
                await page.click(SUBMIT_SELECTOR)
            except Exception as exc:
                await browser.close()
                raise RuntimeError(
                    f"Could not interact with Omnivox login form: {exc}"
                ) from exc

            # Wait up to 15 seconds for a post-login redirect.
            deadline = 15
            interval = 0.5
            elapsed = 0.0
            while elapsed < deadline:
                await asyncio.sleep(interval)
                elapsed += interval
                try:
                    current_url = page.url
                except Exception:
                    break
                if _is_logged_in(current_url):
                    break
                if _is_login_page(current_url) and elapsed > 5:
                    # Still on login page after 5 s → wrong credentials.
                    await browser.close()
                    raise RuntimeError(
                        "Omnivox login failed — check your email and password."
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
