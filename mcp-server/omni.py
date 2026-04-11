import os

from fastmcp import FastMCP

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
async def get_mio(num: int) -> str:
    """Get MIOs (internal messages) for a student's Omnivox."""
    # TODO: replace path with actual Omnivox MIO endpoint once known
    resp = await omnivox_request("/intr/Module/MessagerieEleve/Default.aspx")
    return resp.text


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
    mcp.run(transport="http", host=host, port=8000)


if __name__ == "__main__":
    main()
