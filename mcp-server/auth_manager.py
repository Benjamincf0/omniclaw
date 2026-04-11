import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Request

OMNIVOX_URL = "https://johnabbott.omnivox.ca"
AUTH_FILE = Path(__file__).parent / "auth.txt"

# After login, Omnivox redirects to URLs containing these patterns
LOGGED_IN_PATTERNS = [
    "/intr/",
    "/main/",
    "/cvir/",
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


async def authenticate() -> str:
    """
    Open Omnivox in a real browser, wait for the user to log in,
    capture the session cookies (curl -b format), and save to auth.txt.
    Returns the cookie string.
    """
    print(f"Opening Omnivox login page: {OMNIVOX_URL}")
    print("Please log in with your credentials. The window will close automatically.\n")

    cookie_body: str | None = None

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        captured_cookies: str | None = None

        async def on_request(request: Request):
            nonlocal captured_cookies
            if captured_cookies:
                return
            url = request.url.lower()
            if "omnivox" in url and not _is_login_page(request.url):
                cb = _request_to_curl_b(request)
                if cb:
                    captured_cookies = cb

        page.on("request", on_request)

        await page.goto(OMNIVOX_URL)

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

        # Give a moment for post-login requests to fire
        await asyncio.sleep(3)

        # Fallback: grab cookies directly from the browser context
        all_cookies = await context.cookies()
        context_cookie_str = _cookies_to_curl_b(all_cookies)

        cookie_body = captured_cookies or context_cookie_str

        if not cookie_body:
            print("WARNING: No cookies captured. Authentication may have failed.")
            await browser.close()
            return ""

        print(f"\nCaptured cookie body ({len(cookie_body)} chars)")

        await browser.close()

    AUTH_FILE.write_text(cookie_body, encoding="utf-8")
    print(f"Saved to {AUTH_FILE}")

    return cookie_body


def load_auth() -> str | None:
    """Load previously saved auth cookies from auth.txt, or None if missing."""
    if AUTH_FILE.exists():
        return AUTH_FILE.read_text(encoding="utf-8").strip() or None
    return None


if __name__ == "__main__":
    asyncio.run(authenticate())
