"""Supplementary data sources: Yahoo Finance, Morningstar fallbacks."""

from __future__ import annotations

from typing import Optional

from fundautopsy.models.fund_metadata import FundMetadata


def get_fund_metadata_yahoo(ticker: str) -> Optional[dict]:
    """Retrieve basic fund metadata from Yahoo Finance.

    Fallback source for: expense ratio, turnover, fund category,
    total net assets, NAV, inception date.

    Args:
        ticker: Fund ticker symbol.

    Returns:
        Dict of metadata fields, or None if unavailable.
    """
    # TODO: Implement Yahoo Finance lookup
    raise NotImplementedError


def get_fund_category(ticker: str) -> Optional[str]:
    """Resolve fund category (e.g., Large Blend, Target Date 2040).

    Used for context in output and as input to spread estimation
    when N-PORT asset class data is insufficient.
    """
    # TODO: Implement category lookup
    raise NotImplementedError
