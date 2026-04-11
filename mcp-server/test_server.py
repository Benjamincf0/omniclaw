"""
Lightweight HTTP server for testing the Omnivox auth-retry flow without MCP.

Run:
    python test_server.py

Then visit any of these in your browser:
    http://localhost:8080/test/auth          — trigger login & verify cookies
    http://localhost:8080/test/get_mio       — test get_mio (hits Omnivox)
    http://localhost:8080/test/get_news      — test get_news (hits Omnivox)
"""

import json
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from omnivox_client import omnivox_request, ensure_authenticated


async def index(request):
    routes = [
        {"path": "/test/auth", "description": "Trigger login popup & verify cookies"},
        {"path": "/test/get_mio", "description": "Fetch MIO page from Omnivox"},
        {"path": "/test/get_news", "description": "Fetch News page from Omnivox"},
    ]
    return JSONResponse({"available_routes": routes})


async def test_auth(request):
    """Just authenticate — opens browser popup if no cookies are stored."""
    try:
        cookies = await ensure_authenticated()
        return JSONResponse({
            "status": "ok",
            "cookies_length": len(cookies),
            "preview": cookies[:80] + "…" if len(cookies) > 80 else cookies,
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def test_get_mio(request):
    """Hit the MIO endpoint through the auth-retry client."""
    try:
        resp = await omnivox_request("/intr/Module/MessagerieEleve/Default.aspx")
        return PlainTextResponse(
            f"[{resp.status_code}] {resp.url}\n\n{resp.text[:2000]}"
        )
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def test_get_news(request):
    """Hit the News endpoint through the auth-retry client."""
    try:
        resp = await omnivox_request("/intr/Module/Nouvelles/Default.aspx")
        return PlainTextResponse(
            f"[{resp.status_code}] {resp.url}\n\n{resp.text[:2000]}"
        )
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


app = Starlette(
    routes=[
        Route("/", index),
        Route("/test/auth", test_auth),
        Route("/test/get_mio", test_get_mio),
        Route("/test/get_news", test_get_news),
    ],
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
