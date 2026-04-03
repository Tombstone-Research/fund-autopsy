"""Cost breakdown data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from fundautopsy.models.filing_data import DataSourceTag, TaggedValue


@dataclass
class CostRange:
    """A cost estimate expressed as a range (low to high) in basis points."""

    low_bps: float
    high_bps: float
    tag: DataSourceTag
    methodology: Optional[str] = None

    @property
    def midpoint_bps(self) -> float:
        return (self.low_bps + self.high_bps) / 2

    @property
    def low_pct(self) -> float:
        return self.low_bps / 100

    @property
    def high_pct(self) -> float:
        return self.high_bps / 100


@dataclass
class CostBreakdown:
    """Complete cost breakdown for a single fund."""

    ticker: str
    fund_name: str

    # Reported costs
    expense_ratio_bps: Optional[TaggedValue] = None  # Net expense ratio
    management_fee_bps: Optional[TaggedValue] = None
    twelve_b1_fee_bps: Optional[TaggedValue] = None
    other_expenses_bps: Optional[TaggedValue] = None

    # N-CEN derived
    brokerage_commissions_bps: Optional[TaggedValue] = None  # C.6.a / net assets
    soft_dollar_commissions_bps: Optional[TaggedValue] = None  # C.6.b / net assets
    soft_dollar_share_pct: Optional[TaggedValue] = None  # C.6.b / C.6.a

    # Estimated costs
    bid_ask_spread_cost: Optional[CostRange] = None
    market_impact_cost: Optional[CostRange] = None

    # Composite
    @property
    def total_reported_bps(self) -> Optional[float]:
        """Expense ratio + brokerage commissions."""
        er = self.expense_ratio_bps.value if self.expense_ratio_bps and self.expense_ratio_bps.is_available else None
        bc = self.brokerage_commissions_bps.value if self.brokerage_commissions_bps and self.brokerage_commissions_bps.is_available else None
        if er is not None:
            return er + (bc or 0)
        return None

    @property
    def total_estimated_low_bps(self) -> Optional[float]:
        """Total reported + low end of estimated costs."""
        reported = self.total_reported_bps
        if reported is None:
            return None
        spread_low = self.bid_ask_spread_cost.low_bps if self.bid_ask_spread_cost else 0
        impact_low = self.market_impact_cost.low_bps if self.market_impact_cost else 0
        return reported + spread_low + impact_low

    @property
    def total_estimated_high_bps(self) -> Optional[float]:
        """Total reported + high end of estimated costs."""
        reported = self.total_reported_bps
        if reported is None:
            return None
        spread_high = self.bid_ask_spread_cost.high_bps if self.bid_ask_spread_cost else 0
        impact_high = self.market_impact_cost.high_bps if self.market_impact_cost else 0
        return reported + spread_high + impact_high

    @property
    def hidden_cost_gap_bps(self) -> Optional[tuple[float, float]]:
        """The gap between stated expense ratio and estimated total cost."""
        er = self.expense_ratio_bps.value if self.expense_ratio_bps and self.expense_ratio_bps.is_available else None
        low = self.total_estimated_low_bps
        high = self.total_estimated_high_bps
        if er is not None and low is not None and high is not None:
            return (low - er, high - er)
        return None
