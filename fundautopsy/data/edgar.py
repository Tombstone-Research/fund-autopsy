"""EDGAR filing retrieval and base parsing utilities."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from fundautopsy.config import EDGAR_USER_AGENT, EDGAR_RATE_LIMIT_DELAY, MAX_XML_DOWNLOAD_BYTES

logger = logging.getLogger(__name__)

# SEC EDGAR endpoints
EDGAR_SUBMISSIONS_URL: str = "https://data.sec.gov/submissions"
EDGAR_ARCHIVES_URL: str = "https://www.sec.gov/Archives/edgar/data"
EDGAR_MF_TICKERS_URL: str = "https://www.sec.gov/files/company_tickers_mf.json"

# Rate limiting: SEC requests max 10 requests/second
RATE_LIMIT_DELAY: float = EDGAR_RATE_LIMIT_DELAY

# Retry configuration
MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: float = 1.0  # seconds; doubles each retry
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# Thread-safe rate limiting
_rate_limit_lock = threading.Lock()
_last_request_time: float = 0.0

# Per-request EDGAR health tracking (thread-local)
_edgar_health = threading.local()


def reset_edgar_health() -> None:
    """Reset EDGAR health counters at the start of a pipeline run."""
    _edgar_health.retries = 0
    _edgar_health.errors = 0


def get_edgar_health() -> dict:
    """Return EDGAR health stats for the current request.

    Returns dict with 'retries' and 'errors' counts. If EDGAR needed
    retries, the dashboard can show a subtle indicator.
    """
    return {
        "retries": getattr(_edgar_health, "retries", 0),
        "errors": getattr(_edgar_health, "errors", 0),
    }


def pad_cik(cik: int | str) -> str:
    """Pad a CIK to 10 digits for EDGAR URL construction."""
    return str(cik).zfill(10)


@dataclass
class MutualFundIdentifier:
    """Resolved mutual fund identifiers from SEC."""

    ticker: str
    cik: int
    series_id: str
    class_id: str
    cik_padded: str = ""

    def __post_init__(self) -> None:
        """Pad CIK to 10 digits for EDGAR URL construction."""
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
            "User-Agent": EDGAR_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        },
        timeout=30.0,
        follow_redirects=True,
    )


def _rate_limit() -> None:
    """Enforce SEC rate limit of 10 requests/second. Thread-safe.

    Computes the required sleep duration inside the lock but releases it
    before sleeping, so concurrent threads can compute their own sleep
    times without blocking on each other's I/O wait.
    """
    global _last_request_time
    sleep_duration: float = 0.0
    with _rate_limit_lock:
        now: float = time.time()
        elapsed: float = now - _last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            sleep_duration = RATE_LIMIT_DELAY - elapsed
        # Reserve this time slot immediately so the next thread
        # sees the correct _last_request_time even before we sleep.
        _last_request_time = now + sleep_duration
    if sleep_duration > 0:
        time.sleep(sleep_duration)


def _request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    """Make an HTTP request with rate limiting and exponential backoff retry.

    Retries on transient EDGAR errors (429, 5xx) and network failures.
    Logs warnings on retry and errors on final failure.

    Args:
        client: httpx.Client instance.
        method: HTTP method (GET, POST, etc.).
        url: Request URL.
        **kwargs: Additional arguments passed to client.request().

    Returns:
        httpx.Response on success.

    Raises:
        httpx.HTTPStatusError: If the request fails after all retries.
        httpx.TransportError: If a network-level error persists.
    """
    last_exc: Exception | None = None
    last_resp: httpx.Response | None = None
    for attempt in range(MAX_RETRIES):
        _rate_limit()
        try:
            resp = client.request(method, url, **kwargs)
            if resp.status_code in RETRYABLE_STATUS_CODES:
                last_resp = resp
                _edgar_health.retries = getattr(_edgar_health, "retries", 0) + 1
                wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "EDGAR returned %d for %s (attempt %d/%d), retrying in %.1fs",
                    resp.status_code, url, attempt + 1, MAX_RETRIES, wait,
                )
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except httpx.TransportError as exc:
            last_exc = exc
            _edgar_health.retries = getattr(_edgar_health, "retries", 0) + 1
            wait = RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "Network error fetching %s (attempt %d/%d): %s, retrying in %.1fs",
                url, attempt + 1, MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)
        except httpx.HTTPStatusError:
            raise  # non-retryable HTTP errors propagate immediately

    # All retries exhausted
    _edgar_health.errors = getattr(_edgar_health, "errors", 0) + 1
    logger.error("EDGAR request failed after %d attempts: %s", MAX_RETRIES, url)
    if last_exc is not None:
        raise last_exc
    if last_resp is not None:
        last_resp.raise_for_status()
    raise httpx.TransportError(f"EDGAR request failed after {MAX_RETRIES} attempts: {url}")


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
    own_client: bool = client is None
    if own_client:
        client = get_edgar_client()

    try:
        resp = _request_with_retry(client, "GET", EDGAR_MF_TICKERS_URL)
        data: dict = resp.json()

        # Structure: {"fields": ["cik","seriesId","classId","symbol"], "data": [[...], ...]}
        ticker_upper: str = ticker.upper()
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
    own_client: bool = client is None
    if own_client:
        client = get_edgar_client()

    try:
        cik_padded: str = str(cik).zfill(10)
        resp = _request_with_retry(client, "GET", f"{EDGAR_SUBMISSIONS_URL}/CIK{cik_padded}.json")
        sub: dict = resp.json()

        recent: dict = sub.get("filings", {}).get("recent", {})
        forms: list = recent.get("form", [])
        dates: list = recent.get("filingDate", [])
        accessions: list = recent.get("accessionNumber", [])
        primary_docs: list = recent.get("primaryDocument", [])

        # Validate list lengths are consistent before iterating
        min_len = min(len(forms), len(dates), len(accessions))
        if min_len < len(forms):
            logger.warning(
                "Inconsistent filing data lengths for CIK %s: forms=%d, dates=%d, accessions=%d",
                cik_padded, len(forms), len(dates), len(accessions),
            )

        entries: list[FilingEntry] = []
        for i in range(min_len):
            if form_type in forms[i] and len(entries) < count:
                entries.append(FilingEntry(
                    form_type=forms[i],
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
    own_client: bool = client is None
    if own_client:
        client = get_edgar_client()

    try:
        # Check cache first — filings are immutable so cached data is always valid
        from fundautopsy.data.cache import get_cache
        cache = get_cache()
        cached = cache.get_xml(cik, accession_number, primary_document)
        if cached is not None:
            return cached

        accession_path: str = accession_number.replace("-", "")
        url: str = f"{EDGAR_ARCHIVES_URL}/{cik}/{accession_path}/{primary_document}"
        resp = _request_with_retry(client, "GET", url)
        content = resp.content

        if len(content) > MAX_XML_DOWNLOAD_BYTES:
            logger.warning(
                "EDGAR response for %s/%s exceeds size limit (%d > %d bytes), discarding",
                accession_number, primary_document, len(content), MAX_XML_DOWNLOAD_BYTES,
            )
            raise httpx.TransportError(
                f"Filing content exceeds {MAX_XML_DOWNLOAD_BYTES} byte limit"
            )

        # Cache the response for future requests
        cache.put_xml(cik, accession_number, primary_document, content)

        return content
    finally:
        if own_client:
            client.close()
