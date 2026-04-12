from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel

# Ensure the mcp-server root is importable regardless of how this module is loaded
_SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from auth_manager import authenticate, load_auth  # noqa: E402
from omnivox_client import omnivox_request_for_user  # noqa: E402

NEWS_LIST_URL_ENV = "NEWS_LIST_URL"
NEWS_TOKEN_ENV = "NEWS_TOKEN"
NEWS_AUTH_HEADER_ENV = "NEWS_AUTH_HEADER"
NEWS_AUTH_PREFIX_ENV = "NEWS_AUTH_PREFIX"
NEWS_LINK_SELECTOR_ENV = "NEWS_LINK_SELECTOR"
NEWS_TITLE_SELECTOR_ENV = "NEWS_TITLE_SELECTOR"
NEWS_CONTENT_SELECTOR_ENV = "NEWS_CONTENT_SELECTOR"
REQUEST_TIMEOUT_SECONDS = 20.0
OMNIVOX_BASE = "https://johnabbott.omnivox.ca"
DEFAULT_NEWS_LIST_URL = f"{OMNIVOX_BASE}/intr/collegenews/"
DEFAULT_LIST_LINK_SELECTOR = "a.carte-actualite[href]"
DEFAULT_TITLE_SELECTOR = "h1.titre"
DEFAULT_CONTENT_SELECTOR = ".description p, .description li"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)


class AllNewsReq(BaseModel):
    pass


class AllNewsRes(BaseModel):
    news_links: list[str]


class NewsReq(BaseModel):
    link: str


class NewsRes(BaseModel):
    title: str
    content: str


class NewsConfig(BaseModel):
    list_url: str
    auth_header: str = "Cookie"
    auth_prefix: str = ""
    link_selector: str | None = None
    title_selector: str | None = None
    content_selector: str | None = None


def _get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _load_config() -> NewsConfig:
    return NewsConfig(
        list_url=os.getenv(NEWS_LIST_URL_ENV, DEFAULT_NEWS_LIST_URL).strip(),
        auth_header=os.getenv(NEWS_AUTH_HEADER_ENV, "Cookie").strip(),
        auth_prefix=os.getenv(NEWS_AUTH_PREFIX_ENV, ""),
        link_selector=_optional_env(NEWS_LINK_SELECTOR_ENV)
        or DEFAULT_LIST_LINK_SELECTOR,
        title_selector=_optional_env(NEWS_TITLE_SELECTOR_ENV) or DEFAULT_TITLE_SELECTOR,
        content_selector=_optional_env(NEWS_CONTENT_SELECTOR_ENV)
        or DEFAULT_CONTENT_SELECTOR,
    )


def _build_headers(config: NewsConfig) -> dict[str, str]:
    token = os.getenv(NEWS_TOKEN_ENV, "").strip() or load_auth()
    if not token:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": DEFAULT_USER_AGENT,
            "Referer": config.list_url,
        }

    auth_value = f"{config.auth_prefix}{token}" if config.auth_prefix else token
    return {
        config.auth_header: auth_value,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": config.list_url,
    }


_LOGIN_PATTERNS = ("/login", "identification=true")


def _is_auth_redirect(response: httpx.Response) -> bool:
    if response.status_code in (401, 403):
        return True
    if response.status_code in (301, 302, 303, 307, 308):
        location = response.headers.get("location", "").lower()
        return any(pat in location for pat in _LOGIN_PATTERNS)
    return False


async def _ensure_news_token(target_url: str | None = None) -> str:
    token = os.getenv(NEWS_TOKEN_ENV, "").strip() or load_auth()
    if token:
        return token

    token = await authenticate(target_url=target_url)
    if not token:
        raise RuntimeError("Authentication failed — no cookies obtained")
    return token


def _headers_with_token(config: NewsConfig, token: str) -> dict[str, str]:
    auth_value = f"{config.auth_prefix}{token}" if config.auth_prefix else token
    headers = _build_headers(config)
    headers[config.auth_header] = auth_value
    return headers


async def _fetch_html(url: str, config: NewsConfig, user_id: str | None = None) -> str:
    """Fetch an Omnivox HTML page.

    When *user_id* is provided (multi-tenant mode) the request is made via
    omnivox_request_for_user which reads per-user cookies from user_store.
    Otherwise falls back to the legacy single-user flow (auth.txt).
    """
    if user_id:
        # Multi-tenant path: delegate cookie management to omnivox_client.
        resp = await omnivox_request_for_user(user_id, url.replace(OMNIVOX_BASE, ""))
        resp.raise_for_status()
        return resp.text

    # Legacy single-user path.
    token = await _ensure_news_token(target_url=url)

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False
    ) as client:
        response = await client.get(url, headers=_headers_with_token(config, token))
        if _is_auth_redirect(response):
            refreshed_token = await authenticate(target_url=url)
            if not refreshed_token:
                raise RuntimeError("Re-authentication failed")
            response = await client.get(
                url, headers=_headers_with_token(config, refreshed_token)
            )

        if _is_auth_redirect(response):
            raise PermissionError("Omnivox authentication failed after retry")

        response.raise_for_status()
        return response.text


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _iter_selected_anchors(soup: BeautifulSoup, selector: str | None) -> Iterable[Tag]:
    if selector:
        for node in soup.select(selector):
            if not isinstance(node, Tag):
                continue
            if node.name == "a" and node.get("href"):
                yield node
                continue
            anchor = node.find("a", href=True)
            if anchor is not None:
                yield anchor
        return

    for anchor in soup.find_all("a", href=True):
        yield anchor


def _extract_news_links(html: str, base_url: str, selector: str | None) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    links: list[str] = []

    for anchor in _iter_selected_anchors(soup, selector):
        href = anchor.get("href")
        if href is None:
            continue

        absolute_url = urljoin(base_url, href.strip())
        lower_url = absolute_url.lower()
        if lower_url.startswith("javascript:") or lower_url.startswith("mailto:"):
            continue
        if "mode=one" not in lower_url:
            continue
        if "#" in absolute_url:
            absolute_url = absolute_url.split("#", 1)[0]
        if absolute_url in seen:
            continue

        text = _normalize_text(anchor.get_text(" ", strip=True))
        if not text:
            continue

        seen.add(absolute_url)
        links.append(absolute_url)

    return links


def _extract_requested_news_id(url: str) -> str | None:
    query = parse_qs(urlparse(url).query)
    for key in ("idNews", "idnews"):
        values = query.get(key)
        if values:
            return values[0]
    return None


def _find_matching_news_container(
    soup: BeautifulSoup, requested_id: str | None
) -> Tag | None:
    candidates = soup.select(".nouvelle")
    if not candidates:
        return None
    if requested_id is None:
        return candidates[0]

    for candidate in candidates:
        print_link = candidate.select_one(".btn-imprimer[href]")
        if not isinstance(print_link, Tag):
            continue
        href = print_link.get("href", "")
        if href is not None and (
            f"idNews={requested_id}" in href or f"idnews={requested_id}" in href
        ):
            return candidate

    return candidates[0]


def _first_text_from_selector(
    root: Tag | BeautifulSoup, selector: str | None
) -> str | None:
    if not selector:
        return None

    for node in root.select(selector):
        if not isinstance(node, Tag):
            continue
        text = _normalize_text(node.get_text(" ", strip=True))
        if text:
            return text
    return None


def _extract_title(root: Tag | BeautifulSoup, selector: str | None) -> str:
    configured_title = _first_text_from_selector(root, selector)
    if configured_title:
        return configured_title

    for candidate in ("h1", "title", "h2"):
        node = root.find(candidate)
        if node is None:
            continue
        text = _normalize_text(node.get_text(" ", strip=True))
        if text:
            return text

    raise ValueError("Unable to extract a news title from the HTML response")


def _extract_content_blocks(nodes: Iterable[Tag]) -> list[str]:
    blocks: list[str] = []
    for node in nodes:
        if node.name == "li":
            text = _normalize_text(f"- {node.get_text(' ', strip=True)}")
        else:
            text = _normalize_text(node.get_text(" ", strip=True))
        if text:
            blocks.append(text)
    return blocks


def _extract_content(root: Tag | BeautifulSoup, selector: str | None) -> str:
    if selector:
        configured_blocks = _extract_content_blocks(
            node for node in root.select(selector) if isinstance(node, Tag)
        )
        if configured_blocks:
            return "\n\n".join(configured_blocks)

    container = (
        root.find("article") or root.find("main") or getattr(root, "body", None) or root
    )
    if container is None:
        raise ValueError("Unable to locate a content container in the HTML response")

    description = (
        container.select_one(".description") if isinstance(container, Tag) else None
    )
    scoped_container = description if isinstance(description, Tag) else container

    blocks = _extract_content_blocks(scoped_container.find_all(["p", "li"]))
    if not blocks:
        fallback_text = _normalize_text(scoped_container.get_text(" ", strip=True))
        if not fallback_text:
            raise ValueError("Unable to extract news content from the HTML response")
        return fallback_text

    return "\n\n".join(blocks)


async def get_all_news(req: AllNewsReq, user_id: str | None = None) -> AllNewsRes:
    """Return a list of news article URLs from the Omnivox news feed."""
    del req
    config = _load_config()
    html = await _fetch_html(config.list_url, config, user_id=user_id)
    return AllNewsRes(
        news_links=_extract_news_links(
            html, base_url=config.list_url, selector=config.link_selector
        )
    )


async def get_news(req: NewsReq, user_id: str | None = None) -> NewsRes:
    """Return the title and content of a single Omnivox news article."""
    config = _load_config()
    html = await _fetch_html(req.link, config, user_id=user_id)
    soup = BeautifulSoup(html, "html.parser")
    container = _find_matching_news_container(
        soup, _extract_requested_news_id(req.link)
    )
    root = container or soup
    return NewsRes(
        title=_extract_title(root, config.title_selector),
        content=_extract_content(root, config.content_selector),
    )
