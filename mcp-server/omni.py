import os

from fastmcp import FastMCP

from models.mio import AllMiosReq, AllMiosRes, MioReq, MioRes, get_all_mios
from models.mio import get_mio as fetch_mio
from models.news import AllNewsReq, AllNewsRes, NewsReq, NewsRes, get_all_news
from models.news import get_news as fetch_news
from omnivox_client import omnivox_request

# Anyone connecting must send: Authorization: Bearer my-secret-token
# auth = StaticTokenVerifier(
#     tokens={
#         os.environ["MCP_TOKEN"]: {
#             "client_id": "trusted-client",
#             "scopes": ["read", "write"],
#         }
#     }
# )

# Initialize FastMCP server
mcp = FastMCP("omniclaw")

# Constants
host = os.environ.get("MCP_HOST") or "localhost"


@mcp.tool()
async def get_mio(num: int = 10) -> AllMiosRes:
    """Get MIOs (internal messages) for a student's Omnivox."""
    if num < 1:
        raise ValueError("num must be at least 1")

    mios = await get_all_mios(AllMiosReq())
    return AllMiosRes(mios=mios.mios[:num])


@mcp.tool()
async def get_mio_item(link: str) -> MioRes:
    """Get the contents of a single Omnivox MIO."""
    return await fetch_mio(MioReq(link=link))


@mcp.tool()
async def send_mio(subject: str, message: str) -> str:
    """Send an MIO through a student's Omnivox."""
    # TODO: replace with actual Omnivox send endpoint + proper form fields
    resp = await omnivox_request(
        "/intr/Module/MessagerieEleve/Envoyer.aspx",
        method="POST",
        data={"subject": subject, "message": message},
    )
    return resp.text


@mcp.tool()
async def get_news(num: int = 10) -> AllNewsRes:
    """get the latest student news"""
    if num < 1:
        raise ValueError("num must be at least 1")

    news = await get_all_news(AllNewsReq())
    return AllNewsRes(news_links=news.news_links[:num])


@mcp.tool()
async def get_news_item(link: str) -> NewsRes:
    """get the contents of a single student news post"""
    return await fetch_news(NewsReq(link=link))


def main():
    # run the server
    mcp.run(transport="http", host=host, port=8000)


if __name__ == "__main__":
    main()
