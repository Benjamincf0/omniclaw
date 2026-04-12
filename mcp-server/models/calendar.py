from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel

# Ensure the mcp-server root is importable regardless of how this module is loaded
_SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from models.news import OMNIVOX_BASE, _fetch_html, _normalize_text, _optional_env  # noqa: E402

CALENDAR_URL_ENV = "CALENDAR_URL"
CALENDAR_WRAPPER_SELECTOR_ENV = "CALENDAR_WRAPPER_SELECTOR"
CALENDAR_EVENT_SELECTOR_ENV = "CALENDAR_EVENT_SELECTOR"

DEFAULT_CALENDAR_URL = f"{OMNIVOX_BASE}/intr/"
DEFAULT_WRAPPER_SELECTOR = (
    "#ctl00_cntFormulaire_ctl00_partCalendrier_uWebPart_Affichage4_wrapperListeEvenement"
)
DEFAULT_EVENT_SELECTOR = ".evenement"
_TIME_PATTERN = re.compile(
    r"^(?:\d{1,2}:\d{2}(?:\s*(?:to|-)\s*\d{1,2}:\d{2})?|\d{1,2}:\d{2})$"
)


class AllCalendarEventsReq(BaseModel):
    include_past: bool = False


class CalendarEvent(BaseModel):
    title: str
    date: str
    start_date: str | None = None
    end_date: str | None = None
    time: str = ""
    description: str = ""
    category: str = ""
    module_code: str = ""
    community: str = ""
    community_url: str | None = None
    location: str = ""
    state: str = ""


class AllCalendarEventsRes(BaseModel):
    events: list[CalendarEvent]


class CalendarConfig(BaseModel):
    list_url: str
    auth_header: str = "Cookie"
    auth_prefix: str = ""
    wrapper_selector: str | None = None
    event_selector: str | None = None


def _load_config() -> CalendarConfig:
    return CalendarConfig(
        list_url=(
            os_value
            if (os_value := _optional_env(CALENDAR_URL_ENV))
            else DEFAULT_CALENDAR_URL
        ),
        wrapper_selector=_optional_env(CALENDAR_WRAPPER_SELECTOR_ENV)
        or DEFAULT_WRAPPER_SELECTOR,
        event_selector=_optional_env(CALENDAR_EVENT_SELECTOR_ENV)
        or DEFAULT_EVENT_SELECTOR,
    )


def _extract_blocks_from_html(raw_html: str) -> list[str]:
    decoded = unescape(raw_html).strip()
    if not decoded:
        return []

    soup = BeautifulSoup(decoded, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")

    blocks: list[str] = []
    for node in soup.find_all(["p", "li"]):
        text = _normalize_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if node.name == "li":
            text = f"- {text}"
        blocks.append(text)

    if blocks:
        return blocks

    fallback_lines = [
        normalized
        for raw_line in soup.get_text("\n").splitlines()
        if (normalized := _normalize_text(raw_line))
    ]
    if fallback_lines:
        return ["\n".join(fallback_lines)]

    fallback_text = _normalize_text(soup.get_text(" ", strip=True))
    return [fallback_text] if fallback_text else []


def _extract_visible_time_and_description(event: Tag) -> tuple[str, str]:
    container = event.select_one(".evenement-description")
    if not isinstance(container, Tag):
        return "", ""

    working = BeautifulSoup(str(container), "html.parser")
    for br in working.find_all("br"):
        br.replace_with("\n")

    lines = [
        normalized
        for raw_line in working.get_text("\n").splitlines()
        if (normalized := _normalize_text(raw_line))
    ]
    if not lines:
        return "", ""

    if len(lines) == 1:
        line = lines[0]
        if _TIME_PATTERN.match(line):
            return line, ""
        return "", line

    first_line = lines[0]
    if _TIME_PATTERN.match(first_line):
        return first_line, "\n\n".join(lines[1:])
    return "", "\n\n".join(lines)


def _extract_day_range(day_node: Tag) -> tuple[str | None, str | None]:
    raw_value = day_node.get("data-date", "").strip()
    if not raw_value:
        return None, None

    start, _, end = raw_value.partition("|")
    start_date = start.strip() or None
    end_date = end.strip() or start_date
    return start_date, end_date


def _extract_event_type_text(event: Tag) -> str:
    container = event.select_one(".evenement-type")
    if not isinstance(container, Tag):
        return ""
    return _normalize_text(container.get_text(" ", strip=True))


def _extract_calendar_events(html: str, config: CalendarConfig) -> list[CalendarEvent]:
    soup = BeautifulSoup(html, "html.parser")
    wrapper = soup.select_one(config.wrapper_selector or DEFAULT_WRAPPER_SELECTOR)
    if not isinstance(wrapper, Tag):
        raise ValueError("Unable to locate the calendar event list in the HTML response")

    events: list[CalendarEvent] = []
    for day_node in wrapper.select(":scope > .bloc-jour"):
        if not isinstance(day_node, Tag):
            continue

        start_date, end_date = _extract_day_range(day_node)
        for event_node in day_node.select(config.event_selector or DEFAULT_EVENT_SELECTOR):
            if not isinstance(event_node, Tag):
                continue

            modal = event_node.select_one(".modal-data")
            title_node = event_node.select_one(".evenement-titre")
            community_anchor = event_node.select_one(".evenement-type a[href]")

            visible_time, visible_description = _extract_visible_time_and_description(
                event_node
            )
            type_text = _extract_event_type_text(event_node)

            title = ""
            if isinstance(modal, Tag):
                title = _normalize_text(modal.get("data-titre", ""))
            if not title and isinstance(title_node, Tag):
                title = _normalize_text(title_node.get_text(" ", strip=True))
            if not title:
                continue

            date = _normalize_text(modal.get("data-date", "")) if isinstance(modal, Tag) else ""
            time = _normalize_text(modal.get("data-heure", "")) if isinstance(modal, Tag) else ""
            description = (
                "\n\n".join(_extract_blocks_from_html(modal.get("data-description", "")))
                if isinstance(modal, Tag)
                else ""
            )
            category = (
                _normalize_text(modal.get("data-nom-categorie", ""))
                if isinstance(modal, Tag)
                else ""
            )
            module_code = (
                _normalize_text(modal.get("data-code-module", ""))
                if isinstance(modal, Tag)
                else ""
            )
            community = (
                _normalize_text(modal.get("data-titre-communaute", ""))
                if isinstance(modal, Tag)
                else ""
            )
            community_url_raw = modal.get("data-url-communaute", "").strip() if isinstance(modal, Tag) else ""
            location = (
                _normalize_text(modal.get("data-local", ""))
                if isinstance(modal, Tag)
                else ""
            )

            if not date:
                date = start_date or ""
            if not time:
                time = visible_time
            if not description:
                description = visible_description
            if not category:
                category = type_text.split(":", 1)[0].strip() if ":" in type_text else type_text
            if not community and isinstance(community_anchor, Tag):
                community = _normalize_text(community_anchor.get_text(" ", strip=True))
            if not community_url_raw and isinstance(community_anchor, Tag):
                community_url_raw = community_anchor.get("href", "").strip()

            community_url = (
                urljoin(config.list_url, community_url_raw) if community_url_raw else None
            )

            events.append(
                CalendarEvent(
                    title=title,
                    date=date,
                    start_date=start_date,
                    end_date=end_date,
                    time=time,
                    description=description,
                    category=category,
                    module_code=module_code,
                    community=community,
                    community_url=community_url,
                    location=location,
                    state=_normalize_text(event_node.get("data-state", "")),
                )
            )

    return events


async def get_calendar_events(req: AllCalendarEventsReq, user_id: str | None = None) -> AllCalendarEventsRes:
    config = _load_config()
    html = await _fetch_html(config.list_url, config, user_id=user_id)
    events = _extract_calendar_events(html, config)
    if not req.include_past:
        events = [event for event in events if event.state.lower() != "passee"]
    return AllCalendarEventsRes(events=events)
