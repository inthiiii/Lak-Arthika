"""Archive discovery and resilient download services for HARTI bulletins."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from lak_arthika.ingestion.harti import (
    HARTI_BASE_URL,
    HARTI_INDEX_URL,
    USER_AGENT,
    BulletinLink,
    DownloadedBulletin,
    preserve_bulletin_bytes,
)


def parse_archive_index(
    html: str,
    *,
    start_date: date,
    end_date: date,
    base_url: str = HARTI_BASE_URL,
) -> list[BulletinLink]:
    """Parse all dated English PDF links in an official archive page."""

    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")

    soup = BeautifulSoup(html, "html.parser")
    discovered: dict[tuple[date, str], BulletinLink] = {}

    for row in soup.select("tr"):
        cells = row.find_all("td")

        if len(cells) < 2:
            continue

        try:
            bulletin_date = date.fromisoformat(cells[0].get_text(" ", strip=True))
        except ValueError:
            continue

        if not start_date <= bulletin_date <= end_date:
            continue

        row_text = row.get_text(" ", strip=True).lower()
        links = row.find_all("a", href=True)

        for link in links:
            if not isinstance(link, Tag):
                continue

            href = link.get("href")
            link_text = link.get_text(" ", strip=True).lower()

            if not isinstance(href, str) or ".pdf" not in href.lower():
                continue

            if "english" not in row_text and "english" not in link_text and len(cells) >= 3:
                continue

            url = urljoin(base_url, href)
            discovered[(bulletin_date, url)] = BulletinLink(bulletin_date, url)

    return sorted(discovered.values(), key=lambda item: (item.bulletin_date, item.url))


def discover_archive_bulletins(
    *,
    start_date: date,
    end_date: date,
    index_url: str = HARTI_INDEX_URL,
) -> list[BulletinLink]:
    """Fetch the official archive and return English bulletins in a date range."""

    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = client.get(index_url)
        response.raise_for_status()

    return parse_archive_index(
        response.text,
        start_date=start_date,
        end_date=end_date,
        base_url=index_url,
    )


def download_with_retries(
    bulletin: BulletinLink,
    *,
    raw_root: Path,
    max_attempts: int = 3,
    request_delay_seconds: float = 1.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> DownloadedBulletin:
    """Download a bulletin with bounded exponential backoff and validation."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    if request_delay_seconds < 0:
        raise ValueError("request_delay_seconds cannot be negative")

    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        delay = request_delay_seconds * (2 ** (attempt - 1))
        if delay:
            sleeper(delay)

        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=httpx.Timeout(30.0),
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = client.get(bulletin.url)
                response.raise_for_status()

            return preserve_bulletin_bytes(
                bulletin=bulletin,
                pdf_bytes=response.content,
                raw_root=raw_root,
            )
        except (httpx.HTTPError, ValueError) as error:
            last_error = error

    raise RuntimeError(
        f"Failed to download {bulletin.url} after {max_attempts} attempts"
    ) from last_error


def filter_pending_downloads(
    bulletins: Sequence[BulletinLink],
    downloaded_urls: set[str],
) -> list[BulletinLink]:
    """Return only bulletins not already represented by a preserved source."""

    return [bulletin for bulletin in bulletins if bulletin.url not in downloaded_urls]
