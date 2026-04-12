from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel

# Ensure the mcp-server root is importable regardless of how this module is loaded
_SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from models.news import OMNIVOX_BASE, _fetch_html, _normalize_text, _optional_env  # noqa: E402

MIO_LIST_URL_ENV = "MIO_LIST_URL"
MIO_DETAIL_URL_ENV = "MIO_DETAIL_URL"
MIO_CATEGORY_ENV = "MIO_CATEGORY"
MIO_LIST_SELECTOR_ENV = "MIO_LIST_SELECTOR"
MIO_SENDER_SELECTOR_ENV = "MIO_SENDER_SELECTOR"
MIO_TITLE_SELECTOR_ENV = "MIO_TITLE_SELECTOR"
MIO_DATE_SELECTOR_ENV = "MIO_DATE_SELECTOR"
MIO_CONTENT_SELECTOR_ENV = "MIO_CONTENT_SELECTOR"

DEFAULT_MIO_CATEGORY = "SEARCH_FOLDER_MioRecu"
DEFAULT_MIO_LIST_URL = (
    f"{OMNIVOX_BASE}/WebApplication/Module.MIOE/Commun/Message/MioListe.aspx"
    f"?NomCategorie={DEFAULT_MIO_CATEGORY}&C=JAC&E=P&L=ANG"
)
DEFAULT_MIO_DETAIL_URL = (
    f"{OMNIVOX_BASE}/WebApplication/Module.MIOE/Commun/Message/MioDetail.aspx"
    "?C=JAC&E=P&L=ANG"
)
DEFAULT_LIST_SELECTOR = "#lstMIO tr[data-isMioEnvoi]"
DEFAULT_SENDER_SELECTOR = ".cDe"
DEFAULT_TITLE_SELECTOR = ".cSujet"
DEFAULT_DATE_SELECTOR = ".cDate"
DEFAULT_CONTENT_SELECTOR = "#contenuWrapper"


class AllMiosReq(BaseModel):
    pass


class MioListItem(BaseModel):
    link: str
    sender: str
    title: str
    preview: str
    date: str


class AllMiosRes(BaseModel):
    mios: list[MioListItem]


class MioReq(BaseModel):
    link: str


class MioRes(BaseModel):
    title: str
    sender: str
    date: str
    content: str


class MioConfig(BaseModel):
    list_url: str
    detail_url: str
    category: str
    auth_header: str = "Cookie"
    auth_prefix: str = ""
    list_selector: str | None = None
    sender_selector: str | None = None
    title_selector: str | None = None
    date_selector: str | None = None
    content_selector: str | None = None


def _category_from_url(url: str) -> str | None:
    query = parse_qs(urlparse(url).query)
    for key in ("NomCategorie", "nomcategorie", "categorie"):
        values = query.get(key)
        if values:
            return values[0]
    return None


def _load_config() -> MioConfig:
    list_url = os.getenv(MIO_LIST_URL_ENV, DEFAULT_MIO_LIST_URL).strip()
    return MioConfig(
        list_url=list_url,
        detail_url=os.getenv(MIO_DETAIL_URL_ENV, DEFAULT_MIO_DETAIL_URL).strip(),
        category=_optional_env(MIO_CATEGORY_ENV)
        or _category_from_url(list_url)
        or DEFAULT_MIO_CATEGORY,
        list_selector=_optional_env(MIO_LIST_SELECTOR_ENV) or DEFAULT_LIST_SELECTOR,
        sender_selector=_optional_env(MIO_SENDER_SELECTOR_ENV)
        or DEFAULT_SENDER_SELECTOR,
        title_selector=_optional_env(MIO_TITLE_SELECTOR_ENV) or DEFAULT_TITLE_SELECTOR,
        date_selector=_optional_env(MIO_DATE_SELECTOR_ENV) or DEFAULT_DATE_SELECTOR,
        content_selector=_optional_env(MIO_CONTENT_SELECTOR_ENV)
        or DEFAULT_CONTENT_SELECTOR,
    )


def _ensure_ref(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if not query.get("Ref"):
        query["Ref"] = [datetime.now().strftime("%Y%m%d%H%M%S")]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _config_with_runtime_ref(config: MioConfig) -> MioConfig:
    return config.model_copy(update={"list_url": _ensure_ref(config.list_url)})


def _base_detail_query(config: MioConfig) -> dict[str, str]:
    merged: dict[str, str] = {}
    for raw_url in (config.list_url, config.detail_url):
        parsed = urlparse(raw_url)
        for key, values in parse_qs(parsed.query, keep_blank_values=True).items():
            if values:
                merged[key] = values[-1]

    for transient_key in ("m", "View", "categorie", "NomCategorie", "IdMessage"):
        merged.pop(transient_key, None)

    return merged


def _build_mio_link(detail_id: str, config: MioConfig) -> str:
    parsed = urlparse(config.detail_url)
    query = _base_detail_query(config)
    query["NomCategorie"] = config.category
    query["m"] = detail_id
    query["View"] = "Full"
    query["Ref"] = query.get("Ref") or datetime.now().strftime("%Y%m%d%H%M%S")
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _first_text(root: Tag | BeautifulSoup, selector: str | None) -> str | None:
    if not selector:
        return None

    for node in root.select(selector):
        if not isinstance(node, Tag):
            continue
        text = _normalize_text(node.get_text(" ", strip=True))
        if text:
            return text
    return None


def _extract_row_detail_id(row: Tag) -> str | None:
    checkbox = row.select_one('td.Td_CheckBox input[id^="chk"]')
    if isinstance(checkbox, Tag):
        checkbox_id = checkbox.get("id", "").strip()
        if checkbox_id.startswith("chk") and len(checkbox_id) > 3:
            return checkbox_id[3:]

    indicator = row.select_one("[data-message]")
    if isinstance(indicator, Tag):
        detail_id = indicator.get("data-message", "").strip()
        if detail_id:
            return f"{detail_id}0"

    return None


def _extract_preview(row: Tag, title: str) -> str:
    title_cell = row.select_one("td.lsTdTitle")
    if not isinstance(title_cell, Tag):
        return ""

    full_text = _normalize_text(title_cell.get_text(" ", strip=True))
    if not full_text:
        return ""
    if title and full_text.startswith(title):
        return full_text[len(title) :].strip()
    return full_text


def _extract_mios(html: str, config: MioConfig) -> list[MioListItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[MioListItem] = []

    for row in soup.select(config.list_selector or DEFAULT_LIST_SELECTOR):
        if not isinstance(row, Tag):
            continue

        detail_id = _extract_row_detail_id(row)
        sender = _first_text(row, ".name .msgUser") or ""
        title = _first_text(row, "td.lsTdTitle em") or ""
        date = _first_text(row, "td.date span") or ""

        if not detail_id or not title:
            continue

        items.append(
            MioListItem(
                link=_build_mio_link(detail_id, config),
                sender=sender,
                title=title,
                preview=_extract_preview(row, title),
                date=date,
            )
        )

    return items


def _extract_detail_body(root: Tag | BeautifulSoup, selector: str | None) -> str:
    container = root.select_one(selector or DEFAULT_CONTENT_SELECTOR)
    if not isinstance(container, Tag):
        raise ValueError("Unable to extract MIO content from the HTML response")

    working = BeautifulSoup(str(container), "html.parser")
    for br in working.find_all("br"):
        br.replace_with("\n")

    raw_text = working.get_text()
    cleaned_lines: list[str] = []
    saw_blank = False
    for raw_line in raw_text.splitlines():
        line = _normalize_text(raw_line.replace("\xa0", " "))
        if line:
            if saw_blank and cleaned_lines:
                cleaned_lines.append("")
            cleaned_lines.append(line)
            saw_blank = False
        else:
            saw_blank = True

    content = "\n".join(cleaned_lines).strip()
    if not content:
        raise ValueError("Unable to extract MIO content from the HTML response")
    return content


async def get_all_mios(req: AllMiosReq, user_id: str | None = None) -> AllMiosRes:
    """Return a list of MIO inbox items from the student's Omnivox account."""
    del req
    config = _config_with_runtime_ref(_load_config())
    html = await _fetch_html(config.list_url, config, user_id=user_id)
    return AllMiosRes(mios=_extract_mios(html, config))


async def get_mio(req: MioReq, user_id: str | None = None) -> MioRes:
    """Return the full content of a single MIO message."""
    config = _config_with_runtime_ref(_load_config())
    link = _ensure_ref(req.link)
    html = await _fetch_html(link, config, user_id=user_id)
    soup = BeautifulSoup(html, "html.parser")

    title = _first_text(soup, config.title_selector)
    sender = _first_text(soup, config.sender_selector)
    date = _first_text(soup, config.date_selector)

    if not title:
        raise ValueError("Unable to extract a MIO title from the HTML response")
    if not sender:
        raise ValueError("Unable to extract a MIO sender from the HTML response")
    if not date:
        raise ValueError("Unable to extract a MIO date from the HTML response")

    return MioRes(
        title=title,
        sender=sender,
        date=date,
        content=_extract_detail_body(soup, config.content_selector),
    )
