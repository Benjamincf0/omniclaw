"""
Manual integration test for the LEA classes model.

Fetches the LEA dashboard and prints a short summary for each class.

Run (from the mcp-server directory):
    uv run python test_lea_classes.py

Requirements:
  - If no valid Omnivox session is stored, the login window may open automatically.
"""

import asyncio
import sys
from pathlib import Path

# Ensure the mcp-server root is on sys.path when running the file directly
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from models.lea_classes import AllLeaClassesReq, get_lea_classes  # noqa: E402


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


async def main() -> None:
    print("LEA classes model — integration test")

    try:
        result = await get_lea_classes(AllLeaClassesReq())
    except PermissionError as exc:
        print(f"\n  [AUTH ERROR] {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n  [ERROR] Failed to fetch LEA classes: {exc}")
        sys.exit(1)

    classes = result.classes
    if not classes:
        print("\n  [WARN] No LEA classes found.")
        sys.exit(0)

    _section("LEA classes")
    print(f"  Found {len(classes)} class(es).")
    for i, class_info in enumerate(classes, 1):
        print(f"  [{i}] {class_info.header}")
        if class_info.section or class_info.schedule or class_info.teacher:
            print(
                "      "
                f"Section: {class_info.section} | "
                f"Schedule: {class_info.schedule} | "
                f"Teacher: {class_info.teacher}"
            )
        for section in class_info.sections:
            print(f"      - {section.title}")
            if section.status:
                print(f"          status: {section.status}")
            if section.summary:
                print(f"          summary: {section.summary}")
            for metric in section.metrics[:3]:
                print(f"          {metric.label}: {metric.value}")
            for announcement in section.announcements[:3]:
                print(f"          {announcement.date}: {announcement.title}")

    _section("All tests passed")


if __name__ == "__main__":
    asyncio.run(main())
