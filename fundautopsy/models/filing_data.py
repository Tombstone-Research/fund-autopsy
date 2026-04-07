"""SEC filing data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


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

    value: float | None
    tag: DataSourceTag
    source_filing: str | None = None  # e.g., "N-CEN 2024-03-15"
    note: str | None = None

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
    has_soft_dollar_arrangements: bool | None = None  # C.6 yes/no
    total_brokerage_commissions: TaggedValue | None = None  # C.6.a ($)
    soft_dollar_commissions: TaggedValue | None = None  # C.6.b ($)
    soft_dollar_transaction_volume: TaggedValue | None = None  # C.6.c ($)

    # Item C.7 — Turnover
    portfolio_turnover_rate: TaggedValue | None = None

    # Item B.1 — Net assets
    total_net_assets: TaggedValue | None = None

    @property
    def soft_dollar_share_pct(self) -> float | None:
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
    cusip: str | None = None
    isin: str | None = None
    balance: float | None = None  # Shares/units
    value_usd: float | None = None  # Market value
    pct_of_net_assets: float | None = None
    asset_category: str | None = None
    issuer_category: str | None = None

    # Fund-of-funds detection
    is_registered_investment_company: bool = False
    underlying_cik: str | None = None
    underlying_ticker: str | None = None


@dataclass
class NPortData:
    """Parsed data from SEC Form N-PORT."""

    filing_date: date
    reporting_period_end: date
    series_id: str
    total_net_assets: float | None = None
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
