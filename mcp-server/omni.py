import os
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

# Anyone connecting must send: Authorization: Bearer my-secret-token
auth = StaticTokenVerifier(
    tokens={
        os.environ["MCP_TOKEN"]: {
            "client_id": "trusted-client",
            "scopes": ["read", "write"],
        }
    }
)

# Initialize FastMCP server
mcp = FastMCP("weather", auth=auth)

# Constants


@mcp.tool()
async def get_mio(num: int) -> str:
    """get an MIO for a student's omnivox"""
    return f"\n---\nHELLO WORLD FROM get_mio({num}) heheheh\n---\n"


@mcp.tool()
async def send_mio(subject: str, message: str) -> str:
    """get an MIO for a student's omnivox"""
    return f"\n---\nHELLO WORLD FROM get_subject(subject:{subject}, message:{message}) heheheh\n---\n"


@mcp.tool()
async def get_news(num: int) -> str:
    """get the latest student news"""
    return f"\n---\nHELLO WORLD FROM get_news({num}) heheheh\n---\n"


def main():
    # run the server
    mcp.run(transport="http", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
