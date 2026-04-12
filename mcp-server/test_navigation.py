"""
Manual integration test for cross-module Omnivox session reuse.

This script is meant to be watched by a human. It prints each navigation step,
tracks how many times the browser-based auth helper was invoked, and exercises
module switches that should reuse the same Omnivox session.

Recommended runs (from the mcp-server directory):
    uv run python test_navigation.py home-to-mio --reset-auth
    uv run python test_navigation.py news-to-mio --reset-auth
    uv run python test_navigation.py mio-to-news --reset-auth

What to verify manually:
  - With `--reset-auth`, the browser auth helper may open once at the start.
  - Switching into the second module should not force you to enter credentials
    or MFA a second time.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import textwrap
from pathlib import Path
from typing import Awaitable, Callable

from bs4 import BeautifulSoup

# Ensure the mcp-server root is on sys.path when running the file directly
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import auth_manager  # noqa: E402
import omnivox_client  # noqa: E402
from models.mio import AllMiosReq, MioReq, get_all_mios, get_mio  # noqa: E402
from models.news import AllNewsReq, NewsReq, get_all_news, get_news  # noqa: E402


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _html_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title is None or soup.title.string is None:
        return None
    title = _normalize_text(soup.title.string)
    return title or None


def _clear_saved_auth() -> None:
    removed = auth_manager.clear_auth_state(include_profile=True)

    if removed:
        print("Removed saved auth state:")
        for path in removed:
            print(f"  - {path}")
    else:
        print("No saved auth state found.")


class BrowserAuthTracker:
    def __init__(self) -> None:
        self.count = 0
        self.targets: list[str] = []
        self._original = omnivox_client.authenticate

    async def _wrapped(self, target_url: str | None = None) -> str:
        self.count += 1
        target = target_url or auth_manager.OMNIVOX_URL
        self.targets.append(target)
        _section(f"Browser Auth #{self.count}")
        print("  Omnivox requested an interactive browser auth flow.")
        print(f"  Target URL: {target}")
        print("  Please note whether you had to enter credentials or MFA again.")
        return await self._original(target_url=target_url)

    def install(self) -> None:
        omnivox_client.authenticate = self._wrapped

    def restore(self) -> None:
        omnivox_client.authenticate = self._original


async def _visit_home_page() -> None:
    _section("1. Visiting Omnivox Home")
    response = await omnivox_client.omnivox_request_url("/intr/")
    print(f"  [{response.status_code}] {response.url}")
    title = _html_title(response.text)
    if title:
        print(f"  Title: {title}")


async def _visit_news_list() -> list[str]:
    _section("News List")
    result = await get_all_news(AllNewsReq())
    links = result.news_links

    if not links:
        print("  [WARN] No news links found.")
        return []

    print(f"  Found {len(links)} news link(s).")
    for i, link in enumerate(links[:3], 1):
        print(f"  [{i}] {link}")
    if len(links) > 3:
        print(f"  ... and {len(links) - 3} more.")

    return links


async def _visit_news_detail(link: str) -> None:
    _section("News Detail")
    result = await get_news(NewsReq(link=link))
    print(f"  Title: {result.title}")
    preview = "\n".join(result.content.splitlines()[:5]).strip()
    if preview:
        print("\n  Preview:\n")
        print(textwrap.indent(preview, "    "))


async def _visit_mio_list() -> list[str]:
    _section("MIO List")
    result = await get_all_mios(AllMiosReq())
    mios = result.mios

    if not mios:
        print("  [WARN] No MIOs found.")
        return []

    print(f"  Found {len(mios)} MIO(s).")
    for i, mio in enumerate(mios[:3], 1):
        print(f"  [{i}] {mio.date} | {mio.sender} | {mio.title}")
    if len(mios) > 3:
        print(f"  ... and {len(mios) - 3} more.")

    return [mio.link for mio in mios]


async def _visit_mio_detail(link: str) -> None:
    _section("MIO Detail")
    result = await get_mio(MioReq(link=link))
    print(f"  Title : {result.title}")
    print(f"  Sender: {result.sender}")
    print(f"  Date  : {result.date}")
    preview = "\n".join(result.content.splitlines()[:5]).strip()
    if preview:
        print("\n  Preview:\n")
        print(textwrap.indent(preview, "    "))


async def _scenario_home_to_mio() -> None:
    await _visit_home_page()
    mio_links = await _visit_mio_list()
    if mio_links:
        await _visit_mio_detail(mio_links[0])


async def _scenario_news_to_mio() -> None:
    news_links = await _visit_news_list()
    if news_links:
        await _visit_news_detail(news_links[0])
    mio_links = await _visit_mio_list()
    if mio_links:
        await _visit_mio_detail(mio_links[0])


async def _scenario_mio_to_news() -> None:
    mio_links = await _visit_mio_list()
    if mio_links:
        await _visit_mio_detail(mio_links[0])
    news_links = await _visit_news_list()
    if news_links:
        await _visit_news_detail(news_links[0])


SCENARIOS: dict[str, tuple[str, Callable[[], Awaitable[None]]]] = {
    "home-to-mio": ("Omnivox Home -> MIO", _scenario_home_to_mio),
    "news-to-mio": ("News -> MIO", _scenario_news_to_mio),
    "mio-to-news": ("MIO -> News", _scenario_mio_to_news),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manual integration test for Omnivox cross-module navigation."
    )
    parser.add_argument(
        "scenario",
        choices=sorted(SCENARIOS),
        help="Which navigation flow to run.",
    )
    parser.add_argument(
        "--reset-auth",
        action="store_true",
        help="Delete saved Omnivox auth first so the run starts cold.",
    )
    return parser


async def main() -> None:
    args = _build_parser().parse_args()
    scenario_name, scenario = SCENARIOS[args.scenario]

    _section(f"Scenario: {scenario_name}")
    if args.reset_auth:
        _clear_saved_auth()
    else:
        print("Keeping existing saved auth state.")

    tracker = BrowserAuthTracker()
    tracker.install()
    try:
        await scenario()
    finally:
        tracker.restore()

    _section("Summary")
    print(f"  Browser auth helper invoked: {tracker.count} time(s)")
    if tracker.targets:
        for i, target in enumerate(tracker.targets, 1):
            print(f"  [{i}] {target}")
    if args.reset_auth:
        print("\n  Expected manual result:")
        print("    One interactive login at the beginning is acceptable.")
        print("    You should not have to enter credentials or MFA a second time.")
    else:
        print("\n  Expected manual result:")
        print("    You should not have to log in at all if the saved session is valid.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except PermissionError as exc:
        print(f"\n[AUTH ERROR] {exc}")
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        raise SystemExit(1) from exc
