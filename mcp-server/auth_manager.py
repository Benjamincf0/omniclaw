import asyncio
import os
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Request, Page

OMNIVOX_URL = "https://johnabbott.omnivox.ca"
AUTH_FILE = Path(__file__).parent / "auth.txt"

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
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def _request_to_curl_b(request: Request) -> str | None:
    return request.headers.get("cookie")


def _module_hint(url: str) -> str:
    path = urlparse(url).path.lower()
    if path.startswith("/webapplication/module."):
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2:
            return f"/{parts[0]}/{parts[1]}"
    if path.startswith("/intr/"):
        return "/intr"
    return path or "/"


class AuthState(str, Enum):
    IDLE = "idle"
    LOGGING_IN = "logging_in"
    WAITING_MFA = "waiting_mfa"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"


class AuthManager:
    MAX_MFA_ATTEMPTS = 3

    def __init__(self):
        self.state: AuthState = AuthState.IDLE
        self.error_message: str | None = None
        self.mfa_attempts_left: int = 0
        self._mfa_code_queue: asyncio.Queue[str] | None = None
        self._mfa_result_queue: asyncio.Queue[bool] | None = None
        self._auth_lock = asyncio.Lock()

    def _ensure_queues(self):
        """Lazily create queues so they belong to the running event loop."""
        if self._mfa_code_queue is None:
            self._mfa_code_queue = asyncio.Queue()
            self._mfa_result_queue = asyncio.Queue()

    def get_status(self) -> dict:
        return {
            "state": self.state.value,
            "error": self.error_message,
            "mfa_attempts_left": self.mfa_attempts_left if self.state == AuthState.WAITING_MFA else None,
        }

    async def submit_mfa_code(self, code: str) -> dict:
        if self.state != AuthState.WAITING_MFA or self.mfa_attempts_left <= 0:
            reason = (
                "No attempts remaining"
                if self.state == AuthState.WAITING_MFA
                else "Not waiting for MFA code"
            )
            return {"success": False, "error": reason, "attempts_left": 0}

        self._ensure_queues()
        await self._mfa_code_queue.put(code)
        success = await self._mfa_result_queue.get()
        return {
            "success": success,
            "attempts_left": self.mfa_attempts_left,
            "error": None if success else "Invalid code",
        }

    async def authenticate(self, target_url: str | None = None) -> str:
        async with self._auth_lock:
            existing = load_auth()
            if existing:
                self.state = AuthState.AUTHENTICATED
                return existing
            return await self._do_authenticate(target_url)

    async def _do_authenticate(self, target_url: str | None = None) -> str:
        self.state = AuthState.LOGGING_IN
        self.error_message = None
        self.mfa_attempts_left = 0
        self._ensure_queues()

        for q in (self._mfa_code_queue, self._mfa_result_queue):
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break

        omnivox_id = os.environ.get("OMNIVOX_ID", "")
        omnivox_password = os.environ.get("OMNIVOX_PASSWORD", "")
        if not omnivox_id or not omnivox_password:
            self.state = AuthState.FAILED
            self.error_message = "OMNIVOX_ID or OMNIVOX_PASSWORD not set in .env"
            return ""

        target = target_url or OMNIVOX_URL
        module_hint = _module_hint(target)
        cookie_body: str | None = None

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
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
                await page.wait_for_load_state("networkidle")

                filled = await self._fill_login(page, omnivox_id, omnivox_password)
                if not filled:
                    self.state = AuthState.FAILED
                    self.error_message = "Could not locate login form fields on the page"
                    await browser.close()
                    return ""

                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)

                if not _is_logged_in(page.url):
                    if await self._detect_mfa(page):
                        self.state = AuthState.WAITING_MFA
                        self.mfa_attempts_left = self.MAX_MFA_ATTEMPTS
                        mfa_ok = await self._handle_mfa(page)
                        if not mfa_ok:
                            self.state = AuthState.FAILED
                            self.error_message = "MFA verification failed after maximum attempts"
                            await browser.close()
                            return ""
                    elif _is_login_page(page.url):
                        self.state = AuthState.FAILED
                        self.error_message = "Login failed — invalid credentials"
                        await browser.close()
                        return ""

                if target != OMNIVOX_URL:
                    await page.goto(target)
                    await asyncio.sleep(3)

                all_cookies = await context.cookies()
                context_cookie_str = _cookies_to_curl_b(all_cookies)
                cookie_body = target_cookies or captured_cookies or context_cookie_str

                await browser.close()

        except Exception as exc:
            self.state = AuthState.FAILED
            self.error_message = f"Browser automation error: {exc}"
            return ""

        if not cookie_body:
            self.state = AuthState.FAILED
            self.error_message = "No cookies captured after login"
            return ""

        AUTH_FILE.write_text(cookie_body, encoding="utf-8")
        self.state = AuthState.AUTHENTICATED
        return cookie_body

    # ── Private helpers ───────────────────────────────────────────────────

    async def _fill_login(self, page: Page, omnivox_id: str, password: str) -> bool:
        try:
            id_filled = False
            for sel in [
                '#NoDA', 'input[name="NoDA"]',
                '#Identifiant', 'input[name="Identifiant"]',
            ]:
                loc = page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    await loc.first.fill(omnivox_id)
                    id_filled = True
                    break

            if not id_filled:
                fallback = page.locator(
                    'input[type="text"]:visible, input:not([type]):visible'
                )
                if await fallback.count() > 0:
                    await fallback.first.fill(omnivox_id)
                    id_filled = True

            pw_filled = False
            for sel in [
                '#Password', 'input[name="Password"]',
                '#MotDePasse', 'input[name="MotDePasse"]',
            ]:
                loc = page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    await loc.first.fill(password)
                    pw_filled = True
                    break

            if not pw_filled:
                pw_loc = page.locator('input[type="password"]:visible')
                if await pw_loc.count() > 0:
                    await pw_loc.first.fill(password)
                    pw_filled = True

            if not id_filled or not pw_filled:
                return False

            for sel in [
                'button[type="submit"]', 'input[type="submit"]',
                '#btnSubmit', '.btn-connexion',
                'button:has-text("Connexion")', 'button:has-text("Login")',
                'button:has-text("Se connecter")', 'button:has-text("Sign in")',
            ]:
                loc = page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    await loc.first.click()
                    return True

            await page.keyboard.press("Enter")
            return True

        except Exception:
            return False

    async def _detect_mfa(self, page: Page) -> bool:
        url_lower = page.url.lower()
        if any(
            h in url_lower
            for h in ("mfa", "2fa", "twofactor", "multifactor", "verification", "otp")
        ):
            return True

        try:
            text = (await page.content()).lower()
            return any(
                h in text
                for h in (
                    "verification code", "two-factor", "multi-factor",
                    "authenticator", "code de vérification",
                    "code d'authentification", "enter the code",
                    "entrez le code", "security code",
                )
            )
        except Exception:
            return False

    async def _handle_mfa(self, page: Page) -> bool:
        for attempt in range(self.MAX_MFA_ATTEMPTS):
            self.mfa_attempts_left = self.MAX_MFA_ATTEMPTS - attempt

            code = await self._mfa_code_queue.get()

            code_filled = False
            for sel in [
                'input[name*="code" i]', 'input[name*="otp" i]',
                'input[name*="token" i]', 'input[name*="mfa" i]',
                'input[type="text"]:visible', 'input[type="number"]:visible',
                'input[type="tel"]:visible',
            ]:
                try:
                    loc = page.locator(sel)
                    if await loc.count() > 0 and await loc.first.is_visible():
                        await loc.first.fill(code)
                        code_filled = True
                        break
                except Exception:
                    continue

            if not code_filled:
                self.mfa_attempts_left = self.MAX_MFA_ATTEMPTS - attempt - 1
                await self._mfa_result_queue.put(False)
                continue

            for sel in [
                'button[type="submit"]', 'input[type="submit"]',
                'button:has-text("Verify")', 'button:has-text("Vérifier")',
                'button:has-text("Submit")', 'button:has-text("Soumettre")',
                'button:has-text("Confirm")', 'button:has-text("Confirmer")',
            ]:
                try:
                    loc = page.locator(sel)
                    if await loc.count() > 0 and await loc.first.is_visible():
                        await loc.first.click()
                        break
                except Exception:
                    continue
            else:
                await page.keyboard.press("Enter")

            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            if _is_logged_in(page.url):
                await self._mfa_result_queue.put(True)
                return True

            self.mfa_attempts_left = self.MAX_MFA_ATTEMPTS - attempt - 1
            await self._mfa_result_queue.put(False)

        return False


auth_manager = AuthManager()


def load_auth() -> str | None:
    if AUTH_FILE.exists():
        return AUTH_FILE.read_text(encoding="utf-8").strip() or None
    return None


if __name__ == "__main__":
    asyncio.run(auth_manager.authenticate())
