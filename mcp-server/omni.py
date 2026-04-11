import os
from fastmcp import FastMCP
from omnivox_client import omnivox_request

mcp = FastMCP("omniclaw")


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
async def get_news(num: int) -> str:
    """Get the latest student news from Omnivox."""
    # TODO: replace path with actual Omnivox news endpoint
    resp = await omnivox_request("/intr/Module/Nouvelles/Default.aspx")
    return resp.text


def main():
    mcp.run(transport="http", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
