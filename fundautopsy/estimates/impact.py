"""Market-impact cost estimation.

Based on Edelen, Evans, and Kadlec (2007) framework.
This is the least precise estimate in Fund Autopsy — always report with
explicit confidence caveats and wide ranges.
"""

from __future__ import annotations

from fundautopsy.models.cost_breakdown import CostRange
from fundautopsy.models.filing_data import DataSourceTag
from fundautopsy.estimates.assumptions import (
    IMPACT_ASSUMPTIONS,
    TURNOVER_LOW_HIGH_THRESHOLD,
)


def estimate_market_impact(
    turnover_rate: float,
    total_net_assets: float,
    is_small_cap: bool = False,
) -> CostRange:
    """Estimate market-impact cost from fund characteristics.

    Market impact is the adverse price movement caused by a fund's
    own trading activity. Larger orders in less liquid securities
    cause greater impact.

    Args:
        turnover_rate: Portfolio turnover rate (decimal).
        total_net_assets: Fund total net assets in dollars.
        is_small_cap: Whether the fund primarily holds small-cap securities.

    Returns:
        CostRange with low/high estimates in basis points.
    """
    # Classify fund
    is_high_turnover = turnover_rate > TURNOVER_LOW_HIGH_THRESHOLD

    if is_small_cap and is_high_turnover:
        assumption = IMPACT_ASSUMPTIONS["small_high_turnover"]
    elif is_small_cap:
        assumption = IMPACT_ASSUMPTIONS["small_low_turnover"]
    elif is_high_turnover:
        assumption = IMPACT_ASSUMPTIONS["large_high_turnover"]
    else:
        assumption = IMPACT_ASSUMPTIONS["large_low_turnover"]

    # Apply turnover to impact factor
    cost_low = turnover_rate * assumption.low_pct_of_turnover * 10_000  # bps
    cost_high = turnover_rate * assumption.high_pct_of_turnover * 10_000

    return CostRange(
        low_bps=round(cost_low, 2),
        high_bps=round(cost_high, 2),
        tag=DataSourceTag.ESTIMATED,
        methodology=(
            "Market impact estimated using simplified Edelen, Evans, "
            "and Kadlec (2007) framework. Based on fund size category "
            f"({'small-cap' if is_small_cap else 'large-cap'}) and "
            f"turnover level ({'high' if is_high_turnover else 'low'}). "
            "This is the least precise estimate — treat as directional."
        ),
    )
