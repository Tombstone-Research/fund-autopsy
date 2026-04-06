"""Supplementary data sources: Yahoo Finance, Morningstar fallbacks.

NOT YET IMPLEMENTED.

This module provides fallback metadata sources when SEC filings don't contain
enough detail. Planned functionality:

  - Yahoo Finance ticker lookup for basic fund metadata (AUM, NAV, category)
  - Morningstar fund category resolution for asset class disambiguation
  - Historical pricing for NAV-based spread estimation

These are lower-priority integrations — core analysis works with SEC data alone.
"""

from __future__ import annotations

from typing import Optional

from fundautopsy.models.fund_metadata import FundMetadata


def get_fund_metadata_yahoo(ticker: str) -> Optional[dict]:
    """Retrieve basic fund metadata from Yahoo Finance.

    PLANNED: Fallback source for expense ratio, turnover, fund category,
    total net assets, NAV, and inception date when SEC filings are sparse.

    Args:
        ticker: Fund ticker symbol.

    Returns:
        Dict of metadata fields, or None if unavailable.

    Raises:
        NotImplementedError: This feature is not yet implemented.
    """
    raise NotImplementedError(
        "Yahoo Finance metadata lookup not yet implemented. "
        "Currently uses SEC EDGAR data only."
    )


def get_fund_category(ticker: str) -> Optional[str]:
    """Resolve fund category (e.g., Large Blend, Target Date 2040).

    PLANNED: Used for context in output and as input to spread estimation
    when N-PORT asset class data is insufficient. Will pull from Morningstar
    or other classification schemes.

    Args:
        ticker: Fund ticker symbol.

    Returns:
        Fund category string, or None if unavailable.

    Raises:
        NotImplementedError: This feature is not yet implemented.
    """
    raise NotImplementedError(
        "Fund category lookup not yet implemented. "
        "Asset class is inferred from N-PORT holdings instead."
    )
