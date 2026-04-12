import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from models.calendar import (
    AllCalendarEventsReq,
    CalendarConfig,
    DEFAULT_CALENDAR_URL,
    DEFAULT_EVENT_SELECTOR,
    DEFAULT_WRAPPER_SELECTOR,
    _extract_calendar_events,
    get_calendar_events,
)


class CalendarParserTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_html = (
            Path(__file__).with_name("homepage.html").read_text(encoding="utf-8")
        )

    def test_extract_calendar_events_from_fixture(self) -> None:
        config = CalendarConfig(
            list_url=DEFAULT_CALENDAR_URL,
            wrapper_selector=DEFAULT_WRAPPER_SELECTOR,
            event_selector=DEFAULT_EVENT_SELECTOR,
        )

        events = _extract_calendar_events(self.fixture_html, config)

        self.assertGreater(len(events), 0)
        self.assertTrue(any(event.state == "courant" for event in events))

        first = events[0]
        self.assertEqual(first.title, "Academic Advising is closed AM only***")
        self.assertEqual(first.date, "Friday, November 7, 2025")
        self.assertEqual(first.start_date, "2025-11-07")
        self.assertEqual(first.end_date, "2025-11-07")
        self.assertEqual(first.time, "8:00 to 13:00")
        self.assertIn("Academic Advising office is closed", first.description)
        self.assertEqual(first.category, "Community")
        self.assertEqual(first.module_code, "COMM")
        self.assertEqual(first.community, "Academic Advising H-117")
        self.assertEqual(
            first.community_url, "https://johnabbott.omnivox.ca/intr/advising/"
        )
        self.assertEqual(first.state, "passee")

        make_up_day = next(
            event
            for event in events
            if event.title == "Day Division - A Wednesday Schedule"
        )
        self.assertEqual(make_up_day.time, "")
        self.assertEqual(make_up_day.description, "Make-up day for March 11")

    async def test_get_calendar_events_filters_past_events_by_default(self) -> None:
        with patch(
            "models.calendar._fetch_html", AsyncMock(return_value=self.fixture_html)
        ):
            result = await get_calendar_events(AllCalendarEventsReq())

        self.assertGreater(len(result.events), 0)
        self.assertTrue(all(event.state != "passee" for event in result.events))
        self.assertEqual(result.events[0].title, "Day Division - A Wednesday Schedule")


if __name__ == "__main__":
    unittest.main()
