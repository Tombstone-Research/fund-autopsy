"""Fund metadata data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class FundMetadata:
    """Core identifying information for a mutual fund."""

    ticker: str
    name: str
    cik: str
    series_id: str
    class_id: str
    fund_family: str
    fiscal_year_end: Optional[date] = None
    total_net_assets: Optional[float] = None
    inception_date: Optional[date] = None
    category: Optional[str] = None
    is_fund_of_funds: bool = False

    @property
    def ticker_upper(self) -> str:
        """Uppercase version of ticker symbol."""
        return self.ticker.upper()
