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
from models.mio import AllMiosReq, AllMiosRes, MioReq, MioRes
from models.mio import get_all_mios as _get_all_mios
from models.mio import get_mio as _get_mio_detail
from models.news import AllNewsReq, AllNewsRes, NewsReq, NewsRes
from models.news import get_all_news as _get_all_news
from models.news import get_news as _get_news_detail
from omnivox_client import omnivox_request_for_user
from user_store import has_omnivox_cookies

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


# ── Gemini setup (for the /chat FastAPI endpoint used by the frontend) ────────

TOOL_HANDLERS: dict = {
    "get_mio": get_mio,
    "send_mio": send_mio,
    "get_news": get_news,
    "get_news_item": get_news_item,
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
        ]
    )
]

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

SYSTEM_PROMPT = (
    "You are Omniclaw, a helpful assistant for John Abbott College (JAC) students. "
    "You have access to the student's Omnivox account and can fetch messages and news. "
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


async def run_chat(message: str, history: list[dict]) -> str:
    """Agentic Gemini loop: call model, execute tool calls, repeat until text."""
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
            handler = TOOL_HANDLERS.get(fc.name)
            if handler:
                result = await handler(**dict(fc.args))
                if hasattr(result, "model_dump"):
                    result = result.model_dump()
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
    Accepts Omnivox email + password from the web setup page.
    Runs a headless Playwright login, captures cookies, stores them for the user.

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

    try:
        await authenticate_headless(email, password, user_id)
    except RuntimeError as exc:
        return _json({"detail": str(exc)}, 400)
    except Exception as exc:
        return _json({"detail": f"Unexpected error: {exc}"}, 500)

    return _json({"success": True, "message": "Omnivox account linked successfully."})


@mcp.custom_route("/chat", methods=["POST"])
async def chat(request: Request) -> Response:
    """Proxy chat messages to Gemini with tool support (used by the React frontend)."""
    try:
        body = await request.json()
    except Exception:
        return _json({"detail": "Invalid JSON body."}, 400)

    message: str = body.get("message", "").strip()
    history: list[dict] = body.get("history", [])

    if not message:
        return _json({"detail": "Message cannot be empty."}, 400)

    try:
        reply = await run_chat(message, history)
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
