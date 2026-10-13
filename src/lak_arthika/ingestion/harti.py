"""Download and extract HARTI daily commodity-price bulletins."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast
from urllib.parse import urljoin

import httpx
import pymupdf
from bs4 import BeautifulSoup
from bs4.element import Tag

from lak_arthika.models.price import PriceRecord

HARTI_INDEX_URL = "https://www.harti.gov.lk/daily-price.php"
HARTI_BASE_URL = "https://www.harti.gov.lk/"

USER_AGENT = "LakArthika/0.1 (research ingestion; one request per scheduled update)"

TARGET_CATEGORIES = {
    "up country vegetable": "Up Country Vegetable",
    "low country vegetable": "Low Country Vegetable",
}


@dataclass(frozen=True)
class BulletinLink:
    """A dated link discovered on the HARTI bulletin index."""

    bulletin_date: date
    url: str


@dataclass(frozen=True)
class DownloadedBulletin:
    """Metadata for a locally preserved HARTI bulletin."""

    bulletin_date: date
    source_url: str
    pdf_path: Path
    metadata_path: Path
    sha256: str
    ingested_at: datetime


def _http_client() -> httpx.Client:
    """Create the polite HTTP client used for HARTI requests."""

    return httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
        headers={"User-Agent": USER_AGENT},
    )


def discover_latest_bulletin(
    index_url: str = HARTI_INDEX_URL,
) -> BulletinLink:
    """Discover the newest dated English PDF on the HARTI index."""

    with _http_client() as client:
        response = client.get(index_url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    discovered: list[BulletinLink] = []

    for row in soup.select("table tbody tr"):
        cells = row.find_all("td")

        if len(cells) < 3:
            continue

        date_text = cells[0].get_text(" ", strip=True)
        medium = cells[1].get_text(" ", strip=True).lower()
        link = row.find("a", href=True)

        if medium != "english" or not isinstance(link, Tag):
            continue

        href = link.get("href")

        if not isinstance(href, str) or not href.lower().endswith(".pdf"):
            continue

        try:
            bulletin_date = date.fromisoformat(date_text)
        except ValueError:
            continue

        discovered.append(
            BulletinLink(
                bulletin_date=bulletin_date,
                url=urljoin(HARTI_BASE_URL, href),
            )
        )

    if not discovered:
        raise RuntimeError("No dated English HARTI bulletin PDF was discovered.")

    return max(discovered, key=lambda item: item.bulletin_date)


def download_bulletin(
    bulletin: BulletinLink,
    raw_root: Path,
) -> DownloadedBulletin:
    """Download and preserve a bulletin with immutable provenance metadata."""

    with _http_client() as client:
        response = client.get(bulletin.url)
        response.raise_for_status()

    return preserve_bulletin_bytes(
        bulletin=bulletin,
        pdf_bytes=response.content,
        raw_root=raw_root,
    )


def preserve_local_bulletin(
    bulletin: BulletinLink,
    source_path: Path,
    raw_root: Path,
) -> DownloadedBulletin:
    """Preserve an already downloaded official bulletin in the raw data lake."""

    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    return preserve_bulletin_bytes(
        bulletin=bulletin,
        pdf_bytes=source_path.read_bytes(),
        raw_root=raw_root,
    )


def preserve_bulletin_bytes(
    *,
    bulletin: BulletinLink,
    pdf_bytes: bytes,
    raw_root: Path,
) -> DownloadedBulletin:
    """Validate and immutably preserve HARTI PDF bytes with provenance."""

    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("The downloaded HARTI resource is not a valid PDF document.")

    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    ingested_at = datetime.now(UTC)

    destination_directory = (
        raw_root / str(bulletin.bulletin_date.year) / f"{bulletin.bulletin_date.month:02d}"
    )
    destination_directory.mkdir(parents=True, exist_ok=True)

    filename = f"harti_daily_{bulletin.bulletin_date.isoformat()}_{sha256[:12]}.pdf"
    pdf_path = destination_directory / filename
    metadata_path = pdf_path.with_suffix(".metadata.json")

    # A repeated run does not overwrite or redownload a different revision.
    if not pdf_path.exists():
        pdf_path.write_bytes(pdf_bytes)

    if metadata_path.exists():
        existing_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        ingested_at = datetime.fromisoformat(existing_metadata["ingested_at"])

    metadata = {
        "source_name": "HARTI",
        "bulletin_date": bulletin.bulletin_date.isoformat(),
        "source_url": bulletin.url,
        "sha256": sha256,
        "content_length_bytes": len(pdf_bytes),
        "ingested_at": ingested_at.isoformat(),
        "local_pdf_path": str(pdf_path),
    }

    if not metadata_path.exists():
        metadata_path.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

    return DownloadedBulletin(
        bulletin_date=bulletin.bulletin_date,
        source_url=bulletin.url,
        pdf_path=pdf_path,
        metadata_path=metadata_path,
        sha256=sha256,
        ingested_at=ingested_at,
    )


def _clean_text(value: str | None) -> str:
    """Collapse PDF whitespace into a consistent representation."""

    if value is None:
        return ""

    return " ".join(value.split()).strip()


def canonicalize_market(raw_market: str) -> str:
    """Normalize known HARTI market-name extraction variations."""

    cleaned = _clean_text(raw_market)
    key = re.sub(r"[^a-z]", "", cleaned.lower().replace("market", ""))

    if key.startswith("peliyagoda"):
        return "Peliyagoda"
    if key.startswith("kandy"):
        return "Kandy"
    if key.startswith("dambulla"):
        return "Dambulla"
    if key.startswith("meegoda"):
        return "Meegoda"
    if key.startswith("norochchole"):
        return "Norochcholai"
    if "hambuththegam" in key:
        return "Thambuththegama"
    if key.startswith("keppetipola"):
        return "Keppetipola"
    if key.startswith("nuwaraeliya"):
        return "Nuwara Eliya"
    if key.startswith("bandarawela"):
        return "Bandarawela"
    if key.startswith("veyangoda"):
        return "Veyangoda"

    return cleaned.removesuffix(" Market").strip()


def parse_price_range(
    raw_value: str | None,
) -> tuple[float, float] | None:
    """Parse values such as '400 - 450', '120' or missing markers."""

    cleaned = _clean_text(raw_value).replace(",", "")

    if not cleaned or cleaned in {"-", "–", "—"}:
        return None

    values = re.findall(r"\d+(?:\.\d+)?", cleaned)

    if len(values) == 1:
        price = float(values[0])
        return price, price

    if len(values) == 2:
        price_min = float(values[0])
        price_max = float(values[1])
        return price_min, price_max

    return None


def extract_records_from_table(
    rows: list[list[str | None]],
    *,
    bulletin_date: date,
    source_url: str,
    source_sha256: str,
    ingested_at: datetime,
) -> list[PriceRecord]:
    """Convert a detected HARTI wholesale table into validated records."""

    if len(rows) < 3:
        raise ValueError("The detected HARTI table has too few rows.")

    date_cells = rows[0][1:]
    market_cells = rows[1][1:]

    observation_dates: list[date | None] = []

    for raw_date in date_cells:
        cleaned_date = _clean_text(raw_date)

        try:
            observation_dates.append(datetime.strptime(cleaned_date, "%Y.%m.%d").date())
        except ValueError:
            observation_dates.append(None)

    markets = [canonicalize_market(_clean_text(raw_market)) for raw_market in market_cells]

    records: list[PriceRecord] = []
    current_category: str | None = None

    for row in rows[2:]:
        if not row:
            continue

        commodity = _clean_text(row[0])
        category_key = commodity.lower()

        if category_key == "banana":
            break

        if category_key in TARGET_CATEGORIES:
            current_category = TARGET_CATEGORIES[category_key]
            continue

        if current_category is None or not commodity:
            continue

        for column_index, raw_price in enumerate(row[1:]):
            if column_index >= len(markets):
                break

            observation_date = observation_dates[column_index]
            market = markets[column_index]
            parsed_range = parse_price_range(raw_price)

            if observation_date is None or not market or parsed_range is None:
                continue

            price_min, price_max = parsed_range
            midpoint = (price_min + price_max) / 2

            records.append(
                PriceRecord(
                    bulletin_date=bulletin_date,
                    observation_date=observation_date,
                    category=current_category,
                    commodity=commodity,
                    market=market,
                    price_min_lkr=price_min,
                    price_max_lkr=price_max,
                    price_midpoint_lkr=midpoint,
                    source_url=source_url,
                    source_sha256=source_sha256,
                    ingested_at=ingested_at,
                )
            )

    return records


def extract_wholesale_vegetable_prices(
    bulletin: DownloadedBulletin,
) -> list[PriceRecord]:
    """Extract the stable English wholesale vegetable table."""

    document = pymupdf.open(bulletin.pdf_path)  # type: ignore[no-untyped-call]

    try:
        target_page = None

        for page in document:  # type: ignore[attr-defined]
            page_text = page.get_text("text")

            if (
                "Peliyagoda" in page_text
                and "Dambulla" in page_text
                and "Up Country Vegetable" in page_text
            ):
                target_page = page
                break

        if target_page is None:
            raise ValueError("The English wholesale vegetable page was not found.")

        detected_tables = target_page.find_tables().tables

        if not detected_tables:
            raise ValueError("No table was detected on the wholesale vegetable page.")

        table = max(
            detected_tables,
            key=lambda candidate: candidate.row_count * candidate.col_count,
        )

        rows = cast(list[list[str | None]], table.extract())

        return extract_records_from_table(
            rows,
            bulletin_date=bulletin.bulletin_date,
            source_url=bulletin.source_url,
            source_sha256=bulletin.sha256,
            ingested_at=bulletin.ingested_at,
        )
    finally:
        document.close()  # type: ignore[no-untyped-call]
