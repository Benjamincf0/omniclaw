"""
Manual integration test for the calendar model.

Fetches the Omnivox homepage calendar and prints the first few events.

Run (from the mcp-server directory):
    uv run python test_calendar.py

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

from models.calendar import AllCalendarEventsReq, get_calendar_events  # noqa: E402


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


async def main() -> None:
    print("Omnivox calendar model — integration test")

    try:
        result = await get_calendar_events(AllCalendarEventsReq())
    except PermissionError as exc:
        print(f"\n  [AUTH ERROR] {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n  [ERROR] Failed to fetch calendar events: {exc}")
        sys.exit(1)

    events = result.events
    if not events:
        print("\n  [WARN] No current or upcoming calendar events found.")
        sys.exit(0)

    _section("Upcoming calendar events")
    print(f"  Found {len(events)} event(s).")
    for i, event in enumerate(events[:10], 1):
        print(f"  [{i}] {event.date} | {event.title}")
        if event.time:
            print(f"      Time      : {event.time}")
        if event.category:
            print(f"      Category  : {event.category}")
        if event.community:
            print(f"      Community : {event.community}")
        if event.description:
            print(textwrap.indent(event.description, "      "))

    _section("All tests passed")


if __name__ == "__main__":
    asyncio.run(main())
