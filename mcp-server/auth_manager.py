import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright, Request

OMNIVOX_URL = "https://johnabbott.omnivox.ca"
AUTH_FILE = Path(__file__).parent / "auth.txt"

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

MFA_PAGE_PATTERNS = [
    "/MFA",
    "/mfa",
    "TwoFactor",
    "twofactor",
    "2fa",
    "verification",
]


def _load_env():
    """Load variables from .env into os.environ (simple parser, no deps)."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _is_logged_in(url: str) -> bool:
    return any(pat.lower() in url.lower() for pat in LOGGED_IN_PATTERNS)


def _is_login_page(url: str) -> bool:
    return any(pat.lower() in url.lower() for pat in LOGIN_PAGE_PATTERNS)


def _is_mfa_page(url: str) -> bool:
    return any(pat.lower() in url.lower() for pat in MFA_PAGE_PATTERNS)


def _cookies_to_curl_b(cookies: list[dict]) -> str:
    """Format browser cookies as a curl -b string: key=val; key2=val2"""
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def _request_to_curl_b(request: Request) -> str | None:
    """Extract the cookie header from a Playwright request (same as curl -b)."""
    return request.headers.get("cookie")


async def authenticate() -> str:
    """
    Log in to Omnivox automatically using OMNIVOX_ID / OMNIVOX_PASSWORD
    from .env, handle 2FA by prompting in the terminal, capture session
    cookies and save them to auth.txt.  Returns the cookie string.
    """
    _load_env()

    omnivox_id = os.environ.get("OMNIVOX_ID")
    omnivox_password = os.environ.get("OMNIVOX_PASSWORD")

    if not omnivox_id or not omnivox_password:
        raise RuntimeError(
            "OMNIVOX_ID and OMNIVOX_PASSWORD must be set in .env "
            "(or as environment variables)"
        )

    print(f"Logging in to Omnivox as {omnivox_id} ...")

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

        # --- Step 1: Navigate to login page and fill credentials -----------
        await page.goto(OMNIVOX_URL)
        await page.wait_for_load_state("networkidle")

        await page.fill("#Identifiant", omnivox_id)
        await page.fill("#Password", omnivox_password)
        await page.click('button[type="submit"]')

        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        # --- Step 2: Handle 2FA if needed ----------------------------------
        current_url = page.url

        if not _is_logged_in(current_url) and not _is_login_page(current_url):
            print("\n2FA verification required.")
            code = await asyncio.to_thread(input, "Enter your 2FA code: ")

            mfa_input = page.locator(
                'input[type="text"], input[type="tel"], input[type="number"]'
            ).first
            await mfa_input.fill(code.strip())

            submit = page.locator(
                'button[type="submit"], input[type="submit"]'
            ).first
            await submit.click()

            await page.wait_for_load_state("networkidle")

        # --- Step 3: Wait until we land on a logged-in page ----------------
        for _ in range(30):
            await asyncio.sleep(1)
            try:
                if _is_logged_in(page.url):
                    print(f"Logged in: {page.url}")
                    break
            except Exception:
                break
        else:
            print("WARNING: Timed out waiting for logged-in redirect.")

        await asyncio.sleep(2)

        # --- Step 4: Collect cookies and save ------------------------------
        all_cookies = await context.cookies()
        context_cookie_str = _cookies_to_curl_b(all_cookies)
        cookie_body = captured_cookies or context_cookie_str

        await browser.close()

    if not cookie_body:
        print("WARNING: No cookies captured. Authentication may have failed.")
        return ""

    print(f"Captured cookie body ({len(cookie_body)} chars)")
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
