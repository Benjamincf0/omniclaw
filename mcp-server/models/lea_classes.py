from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field

# Ensure the mcp-server root is importable regardless of how this module is loaded
_SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from omnivox_client import DEFAULT_USER_AGENT, omnivox_request_url, omnivox_request_for_user  # noqa: E402
from models.news import OMNIVOX_BASE, _normalize_text  # noqa: E402

LEA_CLASSES_URL_ENV = "LEA_CLASSES_URL"
DEFAULT_LEA_CLASSES_URL = (
    f"{OMNIVOX_BASE}/intr/Module/ServicesExterne/Skytech.aspx"
    "?IdServiceSkytech=Skytech_Omnivox"
    "&lk=%2festd%2fcvie"
    "&IdService=CVIE"
    "&C=JAC&E=P&L=ANG"
)
_COURSE_CODE_PATTERN = re.compile(r"^([A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{2})\s+(.*)$")


class AllLeaClassesReq(BaseModel):
    pass


class LeaMetric(BaseModel):
    label: str
    value: str


class LeaAnnouncement(BaseModel):
    date: str
    title: str
    url: str | None = None


class LeaSection(BaseModel):
    title: str
    url: str | None = None
    metrics: list[LeaMetric] = Field(default_factory=list)
    announcements: list[LeaAnnouncement] = Field(default_factory=list)
    summary: str = ""
    status: str = ""


class LeaClass(BaseModel):
    course_code: str = ""
    course_title: str
    section: str = ""
    schedule: str = ""
    teacher: str = ""
    header: str
    sections: list[LeaSection] = Field(default_factory=list)


class AllLeaClassesRes(BaseModel):
    classes: list[LeaClass]


def _load_list_url() -> str:
    return os.getenv(LEA_CLASSES_URL_ENV, DEFAULT_LEA_CLASSES_URL).strip()


def _build_headers(url: str) -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": f"{OMNIVOX_BASE}/intr/",
        "Origin": OMNIVOX_BASE,
    }


async def _fetch_response(url: str, user_id: str | None = None):
    if user_id:
        response = await omnivox_request_for_user(user_id, url.replace(OMNIVOX_BASE, ""))
    else:
        response = await omnivox_request_url(url, headers=_build_headers(url))
    response.raise_for_status()
    return response


def _parse_course_header(header_text: str) -> tuple[str, str]:
    normalized = _normalize_text(header_text)
    match = _COURSE_CODE_PATTERN.match(normalized)
    if not match:
        return "", normalized
    return match.group(1), match.group(2)


def _parse_course_desc(desc_text: str) -> tuple[str, str, str]:
    normalized = _normalize_text(desc_text)
    if not normalized:
        return "", "", ""

    section = ""
    remainder = normalized
    if " - " in normalized:
        section_part, remainder = normalized.split(" - ", 1)
        section = section_part.removeprefix("sect.").strip()

    schedule = remainder.strip()
    teacher = ""
    if ", " in schedule:
        schedule, teacher = schedule.rsplit(", ", 1)
    return section, schedule.strip(), teacher.strip()


def _extract_section_url(node: Tag, base_url: str) -> str | None:
    href = ""
    if node.name == "a":
        href = node.get("href", "").strip()
    if not href:
        anchor = node.find("a", href=True)
        if isinstance(anchor, Tag):
            href = anchor.get("href", "").strip()
    return urljoin(base_url, href) if href else None


def _extract_visible_text(node: Tag) -> str:
    cleaned = BeautifulSoup(str(node), "html.parser")
    for decorative in cleaned.select(".svg-icon, svg, title, use, i.item-header-icon"):
        if isinstance(decorative, Tag):
            decorative.decompose()
    return _normalize_text(cleaned.get_text(" ", strip=True))


def _extract_announcements(node: Tag, base_url: str) -> list[LeaAnnouncement]:
    announcements: list[LeaAnnouncement] = []
    seen: set[tuple[str, str, str | None]] = set()
    for wrapper in node.select(".communique-date-title-wrapper"):
        if not isinstance(wrapper, Tag):
            continue
        spans = wrapper.find_all("span")
        if len(spans) < 2:
            continue
        date = _normalize_text(spans[0].get_text(" ", strip=True))
        title = _normalize_text(spans[1].get_text(" ", strip=True))
        if not date or not title:
            continue

        onclick = wrapper.get("onclick", "")
        relative_url = ""
        if "OpenCentre('" in onclick:
            relative_url = onclick.split("OpenCentre('", 1)[1].split("'", 1)[0]

        absolute_url = urljoin(base_url, relative_url) if relative_url else None
        key = (date, title, absolute_url)
        if key in seen:
            continue
        seen.add(key)

        announcements.append(
            LeaAnnouncement(
                date=date,
                title=title,
                url=absolute_url,
            )
        )
    return announcements


def _extract_metrics(node: Tag) -> list[LeaMetric]:
    metrics: list[LeaMetric] = []
    for row in node.select(".item-content-row"):
        if not isinstance(row, Tag):
            continue
        label_node = row.select_one(".left-section")
        value_node = row.select_one(".right-section")
        if not isinstance(label_node, Tag) or not isinstance(value_node, Tag):
            continue
        label = _normalize_text(label_node.get_text(" ", strip=True))
        value = _normalize_text(value_node.get_text(" ", strip=True))
        if label and value:
            metrics.append(LeaMetric(label=label, value=value))
    return metrics


def _extract_summary(node: Tag) -> str:
    content = node.select_one(".card-panel-item-content")
    if not isinstance(content, Tag):
        return ""
    paragraphs = [
        _normalize_text(p.get_text(" ", strip=True))
        for p in content.find_all("p")
        if isinstance(p, Tag)
    ]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    if paragraphs:
        return "\n".join(paragraphs)
    return ""


def _extract_section(node: Tag, base_url: str) -> LeaSection | None:
    title_node = node.select_one(".item-header-title")
    if not isinstance(title_node, Tag):
        return None

    title = _extract_visible_text(title_node)
    if not title:
        return None

    status_node = node.select_one(".item-header-element")
    status = (
        _normalize_text(status_node.get_text(" ", strip=True))
        if isinstance(status_node, Tag)
        else ""
    )

    section = LeaSection(
        title=title,
        url=_extract_section_url(node, base_url),
        metrics=_extract_metrics(node),
        announcements=_extract_announcements(node, base_url),
        summary=_extract_summary(node),
        status=status,
    )
    return section


def _extract_lea_classes(html: str, base_url: str) -> list[LeaClass]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".classes-wrapper .card-panel.section-spacing")
    if not cards:
        raise ValueError("Unable to locate the LEA class cards in the HTML response")

    classes: list[LeaClass] = []
    for card in cards:
        if not isinstance(card, Tag):
            continue

        title_node = card.select_one(".card-panel-title")
        desc_node = card.select_one(".card-panel-desc")
        if not isinstance(title_node, Tag):
            continue

        header = _normalize_text(title_node.get_text(" ", strip=True))
        course_code, course_title = _parse_course_header(header)
        section, schedule, teacher = _parse_course_desc(
            desc_node.get_text(" ", strip=True) if isinstance(desc_node, Tag) else ""
        )

        sections: list[LeaSection] = []
        for section_node in card.select(".card-panel-content > .card-panel-item-wrapper"):
            if not isinstance(section_node, Tag):
                continue
            parsed = _extract_section(section_node, base_url)
            if parsed is not None:
                sections.append(parsed)

        classes.append(
            LeaClass(
                course_code=course_code,
                course_title=course_title or header,
                section=section,
                schedule=schedule,
                teacher=teacher,
                header=header,
                sections=sections,
            )
        )

    return classes


async def get_lea_classes(req: AllLeaClassesReq, user_id: str | None = None) -> AllLeaClassesRes:
    del req
    list_url = _load_list_url()
    response = await _fetch_response(list_url, user_id=user_id)
    final_url = str(response.url)
    return AllLeaClassesRes(classes=_extract_lea_classes(response.text, final_url))
