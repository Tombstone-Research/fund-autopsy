"""N-PORT filing parser — fund holdings and asset class breakdown.

Parses SEC Form N-PORT XML filings to extract:
- Complete holdings list with market values
- Asset class classifications (assetCat)
- Issuer categories (issuerCat)
- Fund-of-funds detection via name patterns + CUSIP resolution
- Total net assets and reporting period

XML namespace: http://www.sec.gov/edgar/nport
"""

from __future__ import annotations

import logging
import re
from dataclasses import field
from datetime import date
from typing import Optional

import httpx
from defusedxml.lxml import fromstring as _safe_fromstring
from lxml import etree

from fundautopsy.models.filing_data import NPortData, NPortHolding

logger = logging.getLogger(__name__)
from fundautopsy.data.edgar import (
    MutualFundIdentifier,
    get_edgar_client,
    get_filings,
    download_filing_xml,
)

NPORT_NS = {"n": "http://www.sec.gov/edgar/nport"}

# Patterns that indicate a holding is likely another registered fund
_FUND_NAME_PATTERNS = re.compile(
    r"\b(trust|fund|portfolio|etf|index\s+fund|money\s+market)\b",
    re.IGNORECASE,
)


def retrieve_nport(
    fund_id: MutualFundIdentifier,
) -> Optional[NPortData]:
    """Retrieve and parse the most recent N-PORT filing for a fund.

    Args:
        fund_id: Resolved fund identifier with CIK and series ID.

    Returns:
        Parsed NPortData, or None if no filing found.
    """
    client = get_edgar_client()
    try:
        # Multi-series trusts file separate N-PORTs per series.
        # We may need to check several filings to find the one
        # matching our target series ID.
        # Large trusts (e.g. Fidelity Concord Street Trust) can have 25+
        # series, each filing separate N-PORTs. We need enough to find ours.
        filings = get_filings(fund_id.cik, "NPORT-P", client=client, count=50)
        if not filings:
            return None

        for filing in filings:
            # The primary_document field often points to an XSLT-rendered
            # HTML version (e.g. xslFormNPORT-P_X01/primary_doc.xml).
            # We need the raw XML, which is always at primary_doc.xml
            # in the filing's root directory.
            doc_candidates = ["primary_doc.xml"]
            raw_doc = filing.primary_document or ""
            if raw_doc and "/" not in raw_doc and raw_doc != "primary_doc.xml":
                doc_candidates.insert(0, raw_doc)

            xml_bytes = None
            for doc_name in doc_candidates:
                try:
                    xml_bytes = download_filing_xml(
                        cik=fund_id.cik,
                        accession_number=filing.accession_number,
                        primary_document=doc_name,
                        client=client,
                    )
                    # Quick sanity check: must be XML, not HTML
                    if xml_bytes and xml_bytes[:100].lower().find(b'<html') == -1:
                        break
                    xml_bytes = None
                except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                    logger.debug(
                        "N-PORT download failed for %s/%s: %s",
                        filing.accession_number, doc_name, exc,
                    )
                    continue

            if not xml_bytes:
                continue

            result = parse_nport_xml(xml_bytes, fund_id.series_id)
            if result:
                result.filing_date = date.fromisoformat(filing.filing_date)
                return result

        return None
    finally:
        client.close()


def parse_nport_xml(xml_content: bytes, target_series_id: str) -> Optional[NPortData]:
    """Parse raw N-PORT XML content for a specific series.

    N-PORT XML structure (namespace: http://www.sec.gov/edgar/nport):
      edgarSubmission
        headerData
          filerInfo > seriesClassInfo > seriesId
        formData
          genInfo > seriesId, repPdEnd, repPdDate
          fundInfo > totAssets, totLiabs, netAssets
          invstOrSecs > invstOrSec  <-- holdings

    Args:
        xml_content: Raw XML bytes from EDGAR.
        target_series_id: Series ID to match (e.g., "S000009228").

    Returns:
        Parsed NPortData with all holdings, or None if series doesn't match.
    """
    try:
        root = _safe_fromstring(xml_content)
    except etree.XMLSyntaxError:
        return None

    # Verify series match
    gen_info = root.find(".//n:genInfo", NPORT_NS)
    if gen_info is not None:
        file_series = _text(gen_info, "seriesId")
        if file_series and file_series != target_series_id:
            return None

    # Reporting period
    period_end = None
    if gen_info is not None:
        pe = _text(gen_info, "repPdDate") or _text(gen_info, "repPdEnd")
        if pe:
            try:
                period_end = date.fromisoformat(pe)
            except ValueError:
                pass

    # Fund-level financials
    fund_info = root.find(".//n:fundInfo", NPORT_NS)
    net_assets = None
    if fund_info is not None:
        na_text = _text(fund_info, "netAssets")
        if na_text:
            try:
                net_assets = float(na_text)
            except ValueError:
                pass

    result = NPortData(
        filing_date=date.today(),  # Will be overwritten by retrieve_nport
        reporting_period_end=period_end or date.today(),
        series_id=target_series_id,
        total_net_assets=net_assets,
    )

    # Parse holdings
    for inv in root.findall(".//n:invstOrSec", NPORT_NS):
        holding = _parse_holding(inv)
        if holding:
            result.holdings.append(holding)

    return result


def _parse_holding(inv: etree._Element) -> Optional[NPortHolding]:
    """Parse a single invstOrSec element into an NPortHolding."""
    name = _text(inv, "name")
    if not name:
        return None

    holding = NPortHolding(name=name.strip())

    holding.cusip = _text(inv, "cusip") or None
    holding.asset_category = _text(inv, "assetCat") or None
    holding.issuer_category = _text(inv, "issuerCat") or None

    # ISIN from identifiers block (normalize to None for missing)
    isin_elem = inv.find(".//n:isin", NPORT_NS)
    if isin_elem is not None:
        holding.isin = isin_elem.get("value") or None

    # Numeric fields
    balance_text = _text(inv, "balance")
    if balance_text:
        try:
            holding.balance = float(balance_text)
        except ValueError:
            pass

    val_text = _text(inv, "valUSD")
    if val_text:
        try:
            holding.value_usd = float(val_text)
        except ValueError:
            pass

    pct_text = _text(inv, "pctVal")
    if pct_text:
        try:
            # pctVal is already a percentage (0.1865 = 0.1865% of net assets)
            holding.pct_of_net_assets = float(pct_text)
        except ValueError:
            pass

    return holding


def detect_fund_holdings(nport: NPortData) -> list[NPortHolding]:
    """Identify holdings that are themselves registered investment companies.

    Detection logic (issuerCat is unreliable for RIC detection):
    1. Name matches fund naming patterns (Trust, Fund, Portfolio, ETF)
    2. issuerCat explicitly says "RF" (registered fund) — rare but useful
    3. Asset category is STIV (short-term investment vehicle) with fund-like name

    Args:
        nport: Parsed N-PORT data.

    Returns:
        List of holdings flagged as likely underlying funds.
    """
    fund_holdings = []

    for holding in nport.holdings:
        is_fund = False

        # Check issuerCat for explicit RIC indicator
        if holding.issuer_category and holding.issuer_category.upper() in ("RF", "RIC"):
            is_fund = True

        # Check name patterns
        if not is_fund and _FUND_NAME_PATTERNS.search(holding.name):
            is_fund = True

        # STIV with substantial allocation is often a money market fund
        # But small STIV positions (<5% of assets) are typically cash sweeps
        if not is_fund and holding.asset_category == "STIV":
            if holding.pct_of_net_assets and holding.pct_of_net_assets > 5.0:
                is_fund = True

        if is_fund:
            holding.is_registered_investment_company = True
            fund_holdings.append(holding)

    return fund_holdings


def _text(elem: etree._Element, child_tag: str) -> str:
    """Get text content of a child element, or empty string."""
    child = elem.find(f"n:{child_tag}", NPORT_NS)
    if child is not None and child.text:
        return child.text.strip()
    return ""
