"""EDGAR filing retrieval and base parsing utilities."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx

# SEC EDGAR endpoints
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions"
EDGAR_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
EDGAR_MF_TICKERS_URL = "https://www.sec.gov/files/company_tickers_mf.json"

# Rate limiting: SEC requests max 10 requests/second
RATE_LIMIT_DELAY = 0.12  # seconds between requests (slightly over 100ms for safety)

# Module-level timestamp for rate limiting
_last_request_time: float = 0.0


@dataclass
class MutualFundIdentifier:
    """Resolved mutual fund identifiers from SEC."""

    ticker: str
    cik: int
    series_id: str
    class_id: str
    cik_padded: str = ""

    def __post_init__(self) -> None:
        self.cik_padded = str(self.cik).zfill(10)


@dataclass
class FilingEntry:
    """A single filing from the EDGAR submissions index."""

    form_type: str
    filing_date: str
    accession_number: str
    primary_document: str = ""


def get_edgar_client() -> httpx.Client:
    """Create an HTTP client configured for EDGAR access."""
    return httpx.Client(
        headers={
            "User-Agent": "FundAutopsy/0.1.0 (fundautopsy@tombstoneresearch.com; open-source fund cost analyzer)",
            "Accept-Encoding": "gzip, deflate",
        },
        timeout=30.0,
        follow_redirects=True,
    )


def _rate_limit() -> None:
    """Enforce SEC rate limit of 10 requests/second."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_request_time = time.time()


def resolve_ticker(ticker: str, client: Optional[httpx.Client] = None) -> Optional[MutualFundIdentifier]:
    """Resolve a mutual fund ticker to CIK, series ID, and class ID.

    Uses SEC's company_tickers_mf.json which maps every mutual fund
    share class to its CIK, series ID, and class ID.

    Args:
        ticker: Fund ticker symbol (e.g., "AGTHX").
        client: Optional httpx client (creates one if not provided).

    Returns:
        MutualFundIdentifier if found, None otherwise.
    """
    own_client = client is None
    if own_client:
        client = get_edgar_client()

    try:
        _rate_limit()
        resp = client.get(EDGAR_MF_TICKERS_URL)
        resp.raise_for_status()
        data = resp.json()

        # Structure: {"fields": ["cik","seriesId","classId","symbol"], "data": [[...], ...]}
        ticker_upper = ticker.upper()
        for row in data["data"]:
            cik, series_id, class_id, symbol = row
            if symbol and symbol.upper() == ticker_upper:
                return MutualFundIdentifier(
                    ticker=ticker_upper,
                    cik=cik,
                    series_id=series_id,
                    class_id=class_id,
                )
        return None
    finally:
        if own_client:
            client.close()


def get_filings(
    cik: int,
    form_type: str,
    client: Optional[httpx.Client] = None,
    count: int = 10,
) -> list[FilingEntry]:
    """Retrieve filing entries for a CIK filtered by form type.

    Uses the EDGAR submissions API:
    https://data.sec.gov/submissions/CIK{padded_cik}.json

    Args:
        cik: SEC CIK number.
        form_type: Filing type to filter (e.g., "N-CEN", "NPORT-P").
        client: Optional httpx client.
        count: Max filings to return.

    Returns:
        List of FilingEntry sorted by date descending (most recent first).
    """
    own_client = client is None
    if own_client:
        client = get_edgar_client()

    try:
        cik_padded = str(cik).zfill(10)
        _rate_limit()
        resp = client.get(f"{EDGAR_SUBMISSIONS_URL}/CIK{cik_padded}.json")
        resp.raise_for_status()
        sub = resp.json()

        recent = sub.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        entries: list[FilingEntry] = []
        for i, form in enumerate(forms):
            if form_type in form and len(entries) < count:
                entries.append(FilingEntry(
                    form_type=form,
                    filing_date=dates[i],
                    accession_number=accessions[i],
                    primary_document=primary_docs[i] if i < len(primary_docs) else "",
                ))

        return entries
    finally:
        if own_client:
            client.close()


def download_filing_xml(
    cik: int,
    accession_number: str,
    primary_document: str = "primary_doc.xml",
    client: Optional[httpx.Client] = None,
) -> bytes:
    """Download the XML content of a specific filing.

    Args:
        cik: SEC CIK number.
        accession_number: EDGAR accession number (e.g., "0001145549-24-069034").
        primary_document: Filename of the primary document.
        client: Optional httpx client.

    Returns:
        Raw XML bytes.

    Raises:
        httpx.HTTPStatusError: If the download fails.
    """
    own_client = client is None
    if own_client:
        client = get_edgar_client()

    try:
        accession_path = accession_number.replace("-", "")
        url = f"{EDGAR_ARCHIVES_URL}/{cik}/{accession_path}/{primary_document}"
        _rate_limit()
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content
    finally:
        if own_client:
            client.close()
