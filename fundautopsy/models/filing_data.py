"""SEC filing data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class DataSourceTag(str, Enum):
    """Transparency tag for every data point."""

    REPORTED = "REPORTED"  # Directly from SEC filing
    CALCULATED = "CALCULATED"  # Computed from reported data
    ESTIMATED = "ESTIMATED"  # Derived using assumptions/proxies
    UNAVAILABLE = "UNAVAILABLE"  # Expected but missing from filing
    NOT_DISCLOSED = "NOT_DISCLOSED"  # Fund acknowledged but didn't report amounts


@dataclass
class TaggedValue:
    """A numeric value paired with its data source tag."""

    value: Optional[float]
    tag: DataSourceTag
    source_filing: Optional[str] = None  # e.g., "N-CEN 2024-03-15"
    note: Optional[str] = None

    @property
    def is_available(self) -> bool:
        """True if value exists and is not marked unavailable or not disclosed."""
        return self.value is not None and self.tag not in (
            DataSourceTag.UNAVAILABLE,
            DataSourceTag.NOT_DISCLOSED,
        )


@dataclass
class NCENData:
    """Parsed data from SEC Form N-CEN."""

    filing_date: date
    reporting_period_end: date
    series_id: str

    # Item C.6 — Brokerage and soft dollars
    has_soft_dollar_arrangements: Optional[bool] = None  # C.6 yes/no
    total_brokerage_commissions: Optional[TaggedValue] = None  # C.6.a ($)
    soft_dollar_commissions: Optional[TaggedValue] = None  # C.6.b ($)
    soft_dollar_transaction_volume: Optional[TaggedValue] = None  # C.6.c ($)

    # Item C.7 — Turnover
    portfolio_turnover_rate: Optional[TaggedValue] = None

    # Item B.1 — Net assets
    total_net_assets: Optional[TaggedValue] = None

    @property
    def soft_dollar_share_pct(self) -> Optional[float]:
        """Soft dollar commissions as % of total commissions."""
        if (
            self.total_brokerage_commissions
            and self.soft_dollar_commissions
            and self.total_brokerage_commissions.is_available
            and self.soft_dollar_commissions.is_available
            and self.total_brokerage_commissions.value > 0
        ):
            return (
                self.soft_dollar_commissions.value
                / self.total_brokerage_commissions.value
                * 100
            )
        return None


@dataclass
class NPortHolding:
    """A single holding from N-PORT."""

    name: str
    cusip: Optional[str] = None
    isin: Optional[str] = None
    balance: Optional[float] = None  # Shares/units
    value_usd: Optional[float] = None  # Market value
    pct_of_net_assets: Optional[float] = None
    asset_category: Optional[str] = None
    issuer_category: Optional[str] = None

    # Fund-of-funds detection
    is_registered_investment_company: bool = False
    underlying_cik: Optional[str] = None
    underlying_ticker: Optional[str] = None


@dataclass
class NPortData:
    """Parsed data from SEC Form N-PORT."""

    filing_date: date
    reporting_period_end: date
    series_id: str
    total_net_assets: Optional[float] = None
    holdings: list[NPortHolding] = field(default_factory=list)

    @property
    def fund_holdings(self) -> list[NPortHolding]:
        """Holdings that are themselves registered investment companies."""
        return [h for h in self.holdings if h.is_registered_investment_company]

    @property
    def direct_holdings(self) -> list[NPortHolding]:
        """Holdings that are direct securities, not other funds."""
        return [h for h in self.holdings if not h.is_registered_investment_company]

    def asset_class_weights(self) -> dict[str, float]:
        """Compute allocation weights by asset category."""
        weights: dict[str, float] = {}
        for holding in self.holdings:
            cat = holding.asset_category or "UNKNOWN"
            weights[cat] = weights.get(cat, 0.0) + (holding.pct_of_net_assets or 0.0)
        return weights
