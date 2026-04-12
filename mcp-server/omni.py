"""
Omniclaw MCP + HTTP server.

Authentication flow
-------------------
1. An MCP client (e.g. Claude Desktop) discovers the server at the configured URL.
2. FastMCP returns OAuth2 metadata pointing to Auth0.
3. The client opens a browser → the student logs in with Auth0.
4. The client receives a JWT access token; every subsequent MCP request carries
   it as  Authorization: Bearer <token>.
5. FastMCP validates the JWT and injects the token into tools via CurrentAccessToken().
6. Tools extract the Auth0 "sub" claim as user_id and look up that user's stored
   Omnivox cookies in user_tokens.json.

Linking an Omnivox account (MCP clients)
-----------------------------------------
get_account_status() returns a link_url pointing at the web frontend /setup page.
The student opens that URL in a browser, logs in with Auth0 (same identity), enters
their Omnivox credentials, and the backend runs a headless Playwright login to
capture and store their cookies.  After that, all MCP tool calls work automatically.

HTTP endpoints (registered as @mcp.custom_route so they live on the same port
as the MCP server):
  POST /setup-omnivox   — headless Omnivox login (used by the React frontend)
  GET  /account-status  — check link status (used by the React frontend)
  GET  /health          — liveness probe
  POST /chat            — Gemini chat proxy (used by the React frontend)
"""

from __future__ import annotations

import asyncio
import os
import secrets
from functools import lru_cache

import httpx as _httpx
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth import OAuthProxy, AccessToken
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.dependencies import CurrentAccessToken
from google import genai
from google.genai import types
from jose import jwt as _jose_jwt
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from auth_manager import authenticate_headless
from models.calendar import AllCalendarEventsReq, AllCalendarEventsRes
from models.calendar import get_calendar_events as fetch_calendar_events
from models.lea_classes import AllLeaClassesReq, AllLeaClassesRes
from models.lea_classes import get_lea_classes as fetch_lea_classes
from models.mio import AllMiosReq, AllMiosRes, MioReq, MioRes
from models.mio import get_all_mios as _get_all_mios
from models.mio import get_mio as _get_mio_detail
from models.news import AllNewsReq, AllNewsRes, NewsReq, NewsRes
from models.news import get_all_news as _get_all_news
from models.news import get_news as _get_news_detail
from omnivox_client import omnivox_request_for_user
from user_store import delete_omnivox_cookies, has_omnivox_cookies

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()

_required = [
    "AUTH0_DOMAIN",
    "AUTH0_CLIENT_ID",
    "AUTH0_CLIENT_SECRET",
    "AUTH0_AUDIENCE",
    "GEMINI_API_KEY",
]
for _var in _required:
    if not os.environ.get(_var):
        raise RuntimeError(f"Missing required environment variable: {_var}")

AUTH0_DOMAIN: str = os.environ["AUTH0_DOMAIN"]  # e.g. "dev-xxx.us.auth0.com"
AUTH0_CLIENT_ID: str = os.environ["AUTH0_CLIENT_ID"]
AUTH0_CLIENT_SECRET: str = os.environ["AUTH0_CLIENT_SECRET"]
AUTH0_AUDIENCE: str = os.environ["AUTH0_AUDIENCE"]  # e.g. "https://omniclaw.api"
BASE_URL: str = os.environ.get("BASE_URL", "http://localhost:8000")
FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "http://localhost:5173")
MCP_HOST: str = os.environ.get("MCP_HOST", "localhost")

# ---------------------------------------------------------------------------
# Auth0 OAuth proxy
# ---------------------------------------------------------------------------
# Auth0 does not support Dynamic Client Registration, so we use OAuthProxy which
# presents a DCR-compatible interface to MCP clients while using our pre-registered
# Auth0 app behind the scenes.

_token_verifier = JWTVerifier(
    jwks_uri=f"https://{AUTH0_DOMAIN}/.well-known/jwks.json",
    issuer=f"https://{AUTH0_DOMAIN}/",
    audience=AUTH0_AUDIENCE,
)

auth = OAuthProxy(
    upstream_authorization_endpoint=f"https://{AUTH0_DOMAIN}/authorize",
    upstream_token_endpoint=f"https://{AUTH0_DOMAIN}/oauth/token",
    upstream_client_id=AUTH0_CLIENT_ID,
    upstream_client_secret=AUTH0_CLIENT_SECRET,
    token_verifier=_token_verifier,
    base_url=BASE_URL,
    # Auth0 requires the audience parameter to issue a JWT (not an opaque token).
    extra_authorize_params={"audience": AUTH0_AUDIENCE},
    extra_token_params={"audience": AUTH0_AUDIENCE},
    # Stable signing key so client registrations survive server restarts.
    # Generate once with: python -c "import secrets; print(secrets.token_hex(32))"
    # and add JWT_SIGNING_KEY=<value> to your .env
    jwt_signing_key=os.environ.get("JWT_SIGNING_KEY") or AUTH0_CLIENT_SECRET,
)

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP("omniclaw", auth=auth)


def _get_user_id(token: AccessToken = CurrentAccessToken()) -> str:
    """Extract the Auth0 user ID (sub claim) from the validated JWT."""
    user_id: str | None = token.claims.get("sub")
    if not user_id:
        raise PermissionError("Token is missing the 'sub' claim.")
    return user_id


# ── MIO tools ────────────────────────────────────────────────────────────────


@mcp.tool()
async def get_mio(
    num: int = 10,
    token: AccessToken = CurrentAccessToken(),
) -> AllMiosRes:
    """Get the most recent MIOs (internal messages) from a student's Omnivox inbox."""
    if num < 1:
        raise ValueError("num must be at least 1")
    user_id = _get_user_id(token)
    mios = await _get_all_mios(AllMiosReq(), user_id=user_id)
    return AllMiosRes(mios=mios.mios[:num])


@mcp.tool()
async def get_mio_item(
    link: str,
    token: AccessToken = CurrentAccessToken(),
) -> MioRes:
    """Get the full contents of a single Omnivox MIO by its link."""
    user_id = _get_user_id(token)
    return await _get_mio_detail(MioReq(link=link), user_id=user_id)


@mcp.tool()
async def send_mio(
    subject: str,
    message: str,
    token: AccessToken = CurrentAccessToken(),
) -> str:
    """Send an MIO through a student's Omnivox account."""
    user_id = _get_user_id(token)
    resp = await omnivox_request_for_user(
        user_id,
        "/intr/Module/MessagerieEleve/Envoyer.aspx",
        method="POST",
        data={"subject": subject, "message": message},
    )
    return resp.text


# ── News tools ────────────────────────────────────────────────────────────────


@mcp.tool()
async def get_news(
    num: int = 10,
    token: AccessToken = CurrentAccessToken(),
) -> AllNewsRes:
    """Get the latest student news from John Abbott College Omnivox."""
    if num < 1:
        raise ValueError("num must be at least 1")
    user_id = _get_user_id(token)
    news = await _get_all_news(AllNewsReq(), user_id=user_id)
    return AllNewsRes(news_links=news.news_links[:num])


@mcp.tool()
async def get_news_item(
    link: str,
    token: AccessToken = CurrentAccessToken(),
) -> NewsRes:
    """Get the full contents of a single John Abbott College news post."""
    user_id = _get_user_id(token)
    return await _get_news_detail(NewsReq(link=link), user_id=user_id)


@mcp.tool()
async def get_calendar_events(
    num: int = 10,
    include_past: bool = False,
    token: AccessToken = CurrentAccessToken(),
) -> AllCalendarEventsRes:
    """Get calendar events from the student's Omnivox homepage."""
    if num < 1:
        raise ValueError("num must be at least 1")
    user_id = _get_user_id(token)
    events = await fetch_calendar_events(
        AllCalendarEventsReq(include_past=include_past), user_id=user_id
    )
    return AllCalendarEventsRes(events=events.events[:num])


@mcp.tool()
async def get_lea_classes(
    num: int = 10,
    token: AccessToken = CurrentAccessToken(),
) -> AllLeaClassesRes:
    """Get the dashboard info for the student's LEA classes."""
    if num < 1:
        raise ValueError("num must be at least 1")
    user_id = _get_user_id(token)
    classes = await fetch_lea_classes(AllLeaClassesReq(), user_id=user_id)
    return AllLeaClassesRes(classes=classes.classes[:num])


# ── Account status tool ───────────────────────────────────────────────────────


@mcp.tool()
async def get_account_status(
    token: AccessToken = CurrentAccessToken(),
) -> dict:
    """
    Check whether the student's Omnivox account is linked.
    Returns a dict with 'linked' (bool) and 'link_url' if not linked.
    """
    user_id = _get_user_id(token)
    linked = await has_omnivox_cookies(user_id)
    result: dict = {"linked": linked, "user_id": user_id}
    if not linked:
        result["link_url"] = f"{FRONTEND_URL}/setup"
        result["message"] = (
            "Your Omnivox account is not linked. "
            f"Please open {FRONTEND_URL}/setup in your browser to connect it."
        )
    return result


# ── Gemini setup (for the /chat endpoint used by the frontend) ───────────────

def _make_chat_handlers(user_id: str) -> dict:
    """
    Build Gemini tool handlers bound to a specific Auth0 user's Omnivox session.
    These call the model layer directly (bypassing FastMCP dependency injection)
    so they work from the plain HTTP /chat endpoint.
    """
    async def _get_mio(num: int = 10) -> dict:
        result = await _get_all_mios(AllMiosReq(), user_id=user_id)
        return AllMiosRes(mios=result.mios[:num]).model_dump()

    async def _send_mio(subject: str, message: str) -> str:
        resp = await omnivox_request_for_user(
            user_id,
            "/intr/Module/MessagerieEleve/Envoyer.aspx",
            method="POST",
            data={"subject": subject, "message": message},
        )
        return resp.text

    async def _get_news(num: int = 10) -> dict:
        result = await _get_all_news(AllNewsReq(), user_id=user_id)
        return AllNewsRes(news_links=result.news_links[:num]).model_dump()

    async def _get_news_item(link: str) -> dict:
        return (await _get_news_detail(NewsReq(link=link), user_id=user_id)).model_dump()

    async def _get_calendar_events(num: int = 10, include_past: bool = False) -> dict:
        result = await fetch_calendar_events(
            AllCalendarEventsReq(include_past=include_past), user_id=user_id
        )
        return AllCalendarEventsRes(events=result.events[:num]).model_dump()

    async def _get_lea_classes(num: int = 10) -> dict:
        result = await fetch_lea_classes(AllLeaClassesReq(), user_id=user_id)
        return AllLeaClassesRes(classes=result.classes[:num]).model_dump()

    return {
        "get_mio": _get_mio,
        "send_mio": _send_mio,
        "get_news": _get_news,
        "get_news_item": _get_news_item,
        "get_calendar_events": _get_calendar_events,
        "get_lea_classes": _get_lea_classes,
    }

GEMINI_TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_mio",
                description="Get MIOs (internal messages) for a student's Omnivox.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "num": types.Schema(
                            type=types.Type.INTEGER,
                            description="How many MIO messages to fetch.",
                        ),
                    },
                    required=["num"],
                ),
            ),
            types.FunctionDeclaration(
                name="send_mio",
                description="Send an MIO through a student's Omnivox.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "subject": types.Schema(
                            type=types.Type.STRING, description="Message subject."
                        ),
                        "message": types.Schema(
                            type=types.Type.STRING, description="Message body."
                        ),
                    },
                    required=["subject", "message"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_news",
                description="Get the latest student news links from John Abbott College.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "num": types.Schema(
                            type=types.Type.INTEGER,
                            description="How many news items to fetch (default 10).",
                        ),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="get_news_item",
                description="Get the full contents of a single news post by its link.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "link": types.Schema(
                            type=types.Type.STRING, description="The news post URL."
                        ),
                    },
                    required=["link"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_calendar_events",
                description="Get calendar events from the student's Omnivox homepage.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "num": types.Schema(
                            type=types.Type.INTEGER,
                            description="How many calendar events to fetch (default 10).",
                        ),
                        "include_past": types.Schema(
                            type=types.Type.BOOLEAN,
                            description="Whether to include past events in the results.",
                        ),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="get_lea_classes",
                description="Get the dashboard info for the student's LEA classes.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "num": types.Schema(
                            type=types.Type.INTEGER,
                            description="How many classes to fetch (default 10).",
                        ),
                    },
                ),
            ),
        ]
    )
]


class GeminiConfigurationError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is required to use the legacy /chat endpoint."
        )
    return genai.Client(api_key=api_key)

SYSTEM_PROMPT = (
    "You are Omniclaw, a helpful assistant for John Abbott College (JAC) students. "
    "The student's Omnivox session is already authenticated — you never need a student_id, "
    "username, password, or any auth parameter. "
    "Call tools exactly as defined: only pass the arguments listed in the tool schema, nothing else. "
    "Be concise and friendly. Use bullet points for lists. "
    "If you need more information ask a short clarifying question."
)


def _build_contents(message: str, history: list[dict]) -> list[types.Content]:
    """Convert frontend history (plain dicts) + new message into Content objects."""
    contents = []
    for item in history:
        role = item.get("role", "user")
        if role == "assistant":
            role = "model"
        parts = [
            types.Part(text=p["text"]) for p in item.get("parts", []) if "text" in p
        ]
        if parts:
            contents.append(types.Content(role=role, parts=parts))
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    return contents


async def _generate(contents: list) -> types.GenerateContentResponse:
    """Call Gemini with exponential backoff on rate limit errors."""
    gemini_client = _get_gemini_client()
    for attempt in range(3):
        try:
            return await gemini_client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=GEMINI_TOOLS,
                ),
            )
        except Exception as e:
            if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and attempt < 2:
                await asyncio.sleep(2**attempt)
                continue
            raise


async def run_chat(message: str, history: list[dict], user_id: str) -> str:
    """Agentic Gemini loop: call model, execute tool calls, repeat until text."""
    tool_handlers = _make_chat_handlers(user_id)
    contents = _build_contents(message, history)

    while True:
        response = await _generate(contents)
        candidate = response.candidates[0].content
        function_calls = [p for p in candidate.parts if p.function_call]

        if not function_calls:
            return "\n".join(p.text for p in candidate.parts if p.text)

        contents.append(candidate)

        tool_results: list[types.Part] = []
        for part in function_calls:
            fc = part.function_call
            handler = tool_handlers.get(fc.name)
            if handler:
                result = await handler(**dict(fc.args))
            else:
                result = f"Unknown tool: {fc.name}"

            tool_results.append(
                types.Part.from_function_response(
                    name=fc.name, response={"result": result}
                )
            )

        contents.append(types.Content(role="user", parts=tool_results))


# ---------------------------------------------------------------------------
# Shared JWT validation helpers (used by custom HTTP routes below)
# ---------------------------------------------------------------------------

# Cache the JWKS so we don't fetch it on every request.
_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        async with _httpx.AsyncClient() as hc:
            resp = await hc.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
            resp.raise_for_status()
            _jwks_cache = resp.json()
    return _jwks_cache


async def _decode_jwt(token: str) -> dict | None:
    """Validate an Auth0 JWT and return its payload, or None on failure."""
    try:
        jwks = await _get_jwks()
        return _jose_jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/",
        )
    except Exception:
        return None


async def _require_user_id(request: Request) -> str | None:
    """Extract and validate Bearer token from request; return sub claim or None."""
    auth_header: str = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer ") :]
    payload = await _decode_jwt(token)
    if not payload:
        return None
    return payload.get("sub")


def _json(data: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(content=data, status_code=status)


# ---------------------------------------------------------------------------
# Headless-login session store (for the two-phase /setup-omnivox flow)
# ---------------------------------------------------------------------------
# Each session is a plain dict:
#   {
#     "status": "running" | "needs_otp" | "success" | "error",
#     "event":  asyncio.Event,   # fired when the frontend submits an OTP code
#     "otp":    str | None,      # the code, set just before event.set()
#     "error":  str | None,      # set on failure
#   }

_sessions: dict[str, dict] = {}


async def _await_otp(session: dict) -> str:
    """Signal the frontend that an OTP is needed, then wait for it (5-min limit)."""
    session["status"] = "needs_otp"
    try:
        await asyncio.wait_for(session["event"].wait(), timeout=300.0)
    except asyncio.TimeoutError:
        raise RuntimeError("Timed out waiting for 2FA code (5-minute limit).")
    return session["otp"]


# Module URLs that need to be visited after login so Omnivox issues
# their sub-session tokens.  These are captured in the browser's cookie
# jar and stored alongside the base session cookies.
_OMNIVOX_WARM_URLS: list[str] = [
    os.getenv(
        "MIO_LIST_URL",
        "https://johnabbott.omnivox.ca/WebApplication/Module.MIOE/Commun/Message"
        "/MioListe.aspx?NomCategorie=SEARCH_FOLDER_MioRecu&C=JAC&E=P&L=ANG",
    ),
]


async def _run_login(session: dict, email: str, password: str, user_id: str) -> None:
    """Background task: run authenticate_headless and update session on completion."""
    try:
        await authenticate_headless(
            email,
            password,
            user_id,
            otp_callback=lambda: _await_otp(session),
            warm_urls=_OMNIVOX_WARM_URLS,
        )
        session["status"] = "success"
    except Exception as exc:
        session["error"] = str(exc)
        session["status"] = "error"


# ---------------------------------------------------------------------------
# Custom HTTP routes (registered on the FastMCP server so they share port 8000)
# ---------------------------------------------------------------------------


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> Response:
    """Simple liveness probe."""
    return _json({"status": "ok", "model": "gemini-2.5-flash"})


@mcp.custom_route("/account-status", methods=["GET"])
async def account_status(request: Request) -> Response:
    """Return whether the authenticated user has linked their Omnivox account."""
    user_id = await _require_user_id(request)
    if not user_id:
        return _json({"detail": "Missing or invalid Authorization header."}, 401)
    linked = await has_omnivox_cookies(user_id)
    return _json({"linked": linked, "user_id": user_id})


@mcp.custom_route("/setup-omnivox", methods=["POST"])
async def setup_omnivox(request: Request) -> Response:
    """
    Start a headless Omnivox login for the authenticated user.

    Accepts { email, password } and immediately returns { session_id }.
    The login runs in the background; poll /setup-status?session_id=<id> for
    progress.  If Omnivox requires 2FA, status becomes "needs_otp" — submit
    the code to POST /setup-2fa to resume.

    Requires:  Authorization: Bearer <auth0_access_token>
    """
    user_id = await _require_user_id(request)
    if not user_id:
        return _json({"detail": "Missing or invalid Authorization header."}, 401)

    try:
        body = await request.json()
    except Exception:
        return _json({"detail": "Invalid JSON body."}, 400)

    email: str = (body.get("email") or "").strip()
    password: str = body.get("password") or ""

    if not email or not password:
        return _json({"detail": "Email and password are required."}, 400)

    session_id = secrets.token_urlsafe(16)
    session: dict = {
        "status": "running",
        "event": asyncio.Event(),
        "otp": None,
        "error": None,
    }
    _sessions[session_id] = session

    asyncio.create_task(_run_login(session, email, password, user_id))

    return _json({"session_id": session_id})


@mcp.custom_route("/setup-status", methods=["GET"])
async def setup_status(request: Request) -> Response:
    """Poll the status of an in-progress headless Omnivox login session."""
    session_id: str = request.query_params.get("session_id", "")
    session = _sessions.get(session_id)
    if not session:
        return _json({"detail": "Session not found."}, 404)

    status = session["status"]
    result: dict = {"status": status}

    if status == "error":
        result["detail"] = session["error"]
        del _sessions[session_id]
    elif status == "success":
        del _sessions[session_id]

    return _json(result)


@mcp.custom_route("/setup-2fa", methods=["POST"])
async def setup_2fa(request: Request) -> Response:
    """Submit a 2FA verification code for an in-progress login session."""
    try:
        body = await request.json()
    except Exception:
        return _json({"detail": "Invalid JSON body."}, 400)

    session_id: str = (body.get("session_id") or "").strip()
    code: str = (body.get("code") or "").strip()

    session = _sessions.get(session_id)
    if not session:
        return _json({"detail": "Session not found."}, 404)
    if session["status"] != "needs_otp":
        return _json({"detail": "Session is not waiting for a verification code."}, 400)
    if not code:
        return _json({"detail": "Code is required."}, 400)

    session["otp"] = code
    session["event"].set()

    return _json({"ok": True})


@mcp.custom_route("/unlink-omnivox", methods=["DELETE"])
async def unlink_omnivox(request: Request) -> Response:
    """Remove the authenticated user's stored Omnivox cookies."""
    user_id = await _require_user_id(request)
    if not user_id:
        return _json({"detail": "Missing or invalid Authorization header."}, 401)
    await delete_omnivox_cookies(user_id)
    return _json({"success": True})


@mcp.custom_route("/chat", methods=["POST"])
async def chat(request: Request) -> Response:
    """Proxy chat messages to Gemini with tool support (used by the React frontend)."""
    user_id = await _require_user_id(request)
    if not user_id:
        return _json({"detail": "Missing or invalid Authorization header."}, 401)

    try:
        body = await request.json()
    except Exception:
        return _json({"detail": "Invalid JSON body."}, 400)

    message: str = body.get("message", "").strip()
    history: list[dict] = body.get("history", [])

    if not message:
        return _json({"detail": "Message cannot be empty."}, 400)

    try:
        reply = await run_chat(message, history, user_id=user_id)
        return _json({"reply": reply})
    except Exception as e:
        msg = str(e)
        status = 429 if "429" in msg or "RESOURCE_EXHAUSTED" in msg else 502
        return _json({"detail": msg}, status)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_CORS_MIDDLEWARE = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]


def main() -> None:
    """Run the FastMCP HTTP server with CORS enabled."""
    mcp.run(transport="http", host=MCP_HOST, port=8000, middleware=_CORS_MIDDLEWARE)


if __name__ == "__main__":
    main()
