"""Cash drag estimation from N-PORT holdings.

Cash drag is the performance reduction from holding cash or cash equivalents
instead of fully investing in the portfolio's target securities. Active funds
typically hold 3-4x more cash than index funds.

Academic reference:
    Simutin (2014) — "Cash Holdings and Mutual Fund Performance"
    Average active stock fund cash drag: approximately -0.15% per year.

Implementation:
    Extract STIV (short-term investment vehicles) and cash-like holdings
    from N-PORT. Estimate drag at ~15 bps per 1% of excess cash above a
    2% operational baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fundautopsy.models.filing_data import DataSourceTag, NPortData
from fundautopsy.models.cost_breakdown import CostRange


# Baseline cash % that all funds need for operational purposes
# (redemptions, settlement, margin). Below this, no drag is assigned.
OPERATIONAL_CASH_BASELINE_PCT = 2.0

# Drag per 1% of excess cash, in basis points.
# Calibrated to equity market risk premium minus money market yield.
# At 7% equity return and 5% MM return, the drag is ~2 bps per 1% cash.
# However, during periods of low rates the gap widens to ~5-7 bps.
# We use a range to capture both environments.
DRAG_PER_PCT_LOW_BPS = 2.0   # Normal rate environment
DRAG_PER_PCT_HIGH_BPS = 6.0  # Low rate or rising equity environment

# Flag threshold — above this, the fund is materially under-deployed
CASH_FLAG_THRESHOLD_PCT = 5.0


@dataclass
class CashDragEstimate:
    """Cash drag analysis for a single fund."""

    cash_pct: float  # Total cash/STIV as % of net assets
    excess_cash_pct: float  # Above operational baseline
    drag_low_bps: float
    drag_high_bps: float
    is_flagged: bool  # True if cash_pct > flag threshold
    methodology: str


def estimate_cash_drag(nport: NPortData) -> Optional[CostRange]:
    """Estimate cash drag from N-PORT holdings data.

    Identifies STIV (short-term investment vehicles) and cash-equivalent
    holdings, then estimates the opportunity cost of holding cash instead
    of the fund's target securities.

    Args:
        nport: Parsed N-PORT data with holdings.

    Returns:
        CostRange with drag estimate, or None if no meaningful cash position.
    """
    if not nport or not nport.holdings or not nport.total_net_assets:
        return None

    # Sum cash-equivalent holdings
    # N-PORT asset categories: STIV = short-term investment vehicles
    # Also catch holdings with names suggesting cash/MM
    cash_value = 0.0
    for h in nport.holdings:
        if h.asset_category == "STIV":
            cash_value += abs(h.value_usd or 0)
        elif _is_cash_like(h):
            cash_value += abs(h.value_usd or 0)

    if cash_value <= 0 or nport.total_net_assets <= 0:
        return CostRange(
            low_bps=0.0,
            high_bps=0.0,
            tag=DataSourceTag.CALCULATED,
            methodology="No cash or STIV holdings detected in N-PORT.",
        )

    cash_pct = (cash_value / nport.total_net_assets) * 100.0
    excess = max(0.0, cash_pct - OPERATIONAL_CASH_BASELINE_PCT)

    if excess <= 0:
        return CostRange(
            low_bps=0.0,
            high_bps=0.0,
            tag=DataSourceTag.CALCULATED,
            methodology=(
                f"Cash/STIV = {cash_pct:.1f}% of net assets, "
                f"within operational baseline ({OPERATIONAL_CASH_BASELINE_PCT:.0f}%). "
                "No material cash drag."
            ),
        )

    drag_low = round(excess * DRAG_PER_PCT_LOW_BPS, 2)
    drag_high = round(excess * DRAG_PER_PCT_HIGH_BPS, 2)
    is_flagged = cash_pct > CASH_FLAG_THRESHOLD_PCT

    flag_note = ""
    if is_flagged:
        flag_note = (
            f" WARNING: Cash position ({cash_pct:.1f}%) exceeds "
            f"{CASH_FLAG_THRESHOLD_PCT:.0f}% threshold — fund may be "
            "materially under-deployed."
        )

    return CostRange(
        low_bps=drag_low,
        high_bps=drag_high,
        tag=DataSourceTag.ESTIMATED,
        methodology=(
            f"Cash drag estimated from N-PORT STIV/cash holdings. "
            f"Cash/STIV = {cash_pct:.1f}% of net assets, "
            f"excess above {OPERATIONAL_CASH_BASELINE_PCT:.0f}% baseline = {excess:.1f}%. "
            f"Drag = {DRAG_PER_PCT_LOW_BPS:.0f}–{DRAG_PER_PCT_HIGH_BPS:.0f} bps "
            f"per 1% excess cash (Simutin 2014 framework).{flag_note}"
        ),
    )


def _is_cash_like(holding) -> bool:
    """Heuristic: check if a holding looks like cash/money market."""
    name = (holding.name or "").upper()
    cash_keywords = [
        "MONEY MARKET",
        "TREASURY BILL",
        "T-BILL",
        "COMMERCIAL PAPER",
        "REPURCHASE AGREE",
        "REPO",
        "CASH COLLATERAL",
        "CERTIFICATE OF DEPOSIT",
        "TIME DEPOSIT",
        "OVERNIGHT",
        "FED FUNDS",
    ]
    return any(kw in name for kw in cash_keywords)
