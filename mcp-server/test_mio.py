"""
Manual integration test for the MIO model.

Fetches the MIO list from Omnivox and parses the first message using
the existing get_all_mios / get_mio functions.

Run (from the mcp-server directory):
    uv run python test_mio.py

Requirements:
  - If no valid Omnivox session is stored, the login window will open automatically.
"""

import asyncio
import sys
import textwrap
from pathlib import Path

# Ensure the mcp-server root is on sys.path when running the file directly
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from models.mio import AllMiosReq, MioReq, get_all_mios, get_mio  # noqa: E402


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


async def test_fetch_mio_list() -> list[str]:
    _section("1. Fetching MIO list")
    result = await get_all_mios(AllMiosReq())
    mios = result.mios

    if not mios:
        print("  [WARN] No MIOs found — the page structure may have changed.")
        return []

    print(f"  Found {len(mios)} MIO(s).")
    for i, mio in enumerate(mios[:5], 1):
        print(f"  [{i}] {mio.date} | {mio.sender} | {mio.title}")
        if mio.preview:
            print(textwrap.indent(mio.preview, "      "))
        print(f"      {mio.link}")
    if len(mios) > 5:
        print(f"  ... and {len(mios) - 5} more.")

    return [mio.link for mio in mios]


async def test_fetch_single_mio(link: str) -> None:
    _section(f"2. Parsing MIO\n     {link}")
    result = await get_mio(MioReq(link=link))

    print(f"\n  Title  : {result.title}")
    print(f"  Sender : {result.sender}")
    print(f"  Date   : {result.date}")
    print("\n  Content :\n")
    for line in result.content.splitlines():
        print(textwrap.indent(line, "    "))


async def main() -> None:
    print("Omnivox MIO model — integration test")

    try:
        links = await test_fetch_mio_list()
    except PermissionError as exc:
        print(f"\n  [AUTH ERROR] {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n  [ERROR] Failed to fetch MIO list: {exc}")
        sys.exit(1)

    if not links:
        print("\nNo MIOs to parse — exiting.")
        sys.exit(0)

    first_link = links[0]
    try:
        await test_fetch_single_mio(first_link)
    except PermissionError as exc:
        print(f"\n  [AUTH ERROR] {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n  [ERROR] Failed to parse MIO: {exc}")
        sys.exit(1)

    _section("All tests passed")


if __name__ == "__main__":
    asyncio.run(main())
