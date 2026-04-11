"""
Manual integration test for the news model.

Fetches the news list from Omnivox and parses the first article using
the existing get_all_news / get_news functions.

Run (from the mcp-server directory):
    uv run python test_news.py
    # or
    python test_news.py

Requirements:
  - auth.txt must contain a valid session cookie (run auth_manager.py first
    if the file is missing or stale: `uv run python auth_manager.py`)
"""

import sys
import textwrap
from pathlib import Path

# Ensure the mcp-server root is on sys.path when running the file directly
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from models.news import AllNewsReq, NewsReq, get_all_news, get_news  # noqa: E402


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def test_fetch_news_list() -> list[str]:
    _section("1. Fetching news list")
    result = get_all_news(AllNewsReq())
    links = result.news_links

    if not links:
        print("  [WARN] No news links found — the page structure may have changed.")
        return []

    print(f"  Found {len(links)} news link(s).")
    for i, link in enumerate(links[:5], 1):
        print(f"  [{i}] {link}")
    if len(links) > 5:
        print(f"  ... and {len(links) - 5} more.")

    return links


def test_fetch_single_news(link: str) -> None:
    _section(f"2. Parsing article\n     {link}")
    result = get_news(NewsReq(link=link))

    print(f"\n  Title   : {result.title}")
    print(f"\n  Content :\n")
    for line in result.content.splitlines():
        print(textwrap.indent(line, "    "))


def main() -> None:
    print("Omnivox news model — integration test")

    try:
        links = test_fetch_news_list()
    except PermissionError as exc:
        print(f"\n  [AUTH ERROR] {exc}")
        print("  Run:  uv run python auth_manager.py   to refresh your session.")
        sys.exit(1)
    except Exception as exc:
        print(f"\n  [ERROR] Failed to fetch news list: {exc}")
        sys.exit(1)

    if not links:
        print("\nNo articles to parse — exiting.")
        sys.exit(0)

    first_link = links[0]
    try:
        test_fetch_single_news(first_link)
    except PermissionError as exc:
        print(f"\n  [AUTH ERROR] {exc}")
        print("  Run:  uv run python auth_manager.py   to refresh your session.")
        sys.exit(1)
    except Exception as exc:
        print(f"\n  [ERROR] Failed to parse article: {exc}")
        sys.exit(1)

    _section("All tests passed")


if __name__ == "__main__":
    main()
