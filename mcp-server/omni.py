import logging
import os

from fastmcp import Context, FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from auth_manager import MfaCodeProvider
from models.news import AllNewsReq, AllNewsRes, NewsReq, NewsRes, get_all_news
from models.news import get_news as fetch_news
from omnivox_client import omnivox_request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("omniclaw")

mcp = FastMCP("omniclaw")

host = os.environ.get("MCP_HOST") or "localhost"


def _mfa_provider_from_ctx(ctx: Context) -> MfaCodeProvider:
    """Build an async MFA-code provider that asks the MCP client via elicitation."""

    async def _ask() -> str:
        result = await ctx.elicit(
            "Omnivox requires a 2FA verification code. "
            "Please enter the code sent to your device:",
            response_type=str,
        )
        if result.action != "accept" or not result.data:
            raise RuntimeError("2FA code not provided — authentication cancelled")
        return result.data.strip()

    return _ask


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.tool()
async def get_mio(num: int, ctx: Context) -> str:
    """Get MIOs (internal messages) for a student's Omnivox."""
    resp = await omnivox_request(
        "/intr/Module/MessagerieEleve/Default.aspx",
        mfa_code_provider=_mfa_provider_from_ctx(ctx),
    )
    return resp.text


@mcp.tool()
async def send_mio(subject: str, message: str, ctx: Context) -> str:
    """Send an MIO through a student's Omnivox."""
    resp = await omnivox_request(
        "/intr/Module/MessagerieEleve/Envoyer.aspx",
        method="POST",
        mfa_code_provider=_mfa_provider_from_ctx(ctx),
        data={"subject": subject, "message": message},
    )
    return resp.text


@mcp.tool()
async def get_news(num: int = 10, ctx: Context = None) -> AllNewsRes:
    """get the latest student news"""
    if num < 1:
        raise ValueError("num must be at least 1")

    provider = _mfa_provider_from_ctx(ctx) if ctx else None
    news = await get_all_news(AllNewsReq(), mfa_code_provider=provider)
    return AllNewsRes(news_links=news.news_links[:num])


@mcp.tool()
async def get_news_item(link: str, ctx: Context = None) -> NewsRes:
    """get the contents of a single student news post"""
    provider = _mfa_provider_from_ctx(ctx) if ctx else None
    return await fetch_news(NewsReq(link=link), mfa_code_provider=provider)


def main():
    app = mcp.http_app(transport="http")
    routes = getattr(app, "routes", [])
    log.info("=== Registered routes ===")
    for r in routes:
        methods = getattr(r, "methods", "ALL")
        path = getattr(r, "path", "???")
        log.info(f"  {methods} {path}")
    log.info("=========================")
    mcp.run(transport="http", host=host, port=8000)


if __name__ == "__main__":
    main()
