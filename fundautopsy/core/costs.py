"""Stage 3: Cost computation engine.

Assembles a CostBreakdown from N-CEN brokerage data, N-PORT asset class mix,
and estimation models for bid-ask spread and market impact.
"""

from __future__ import annotations

from fundautopsy.models.filing_data import DataSourceTag, TaggedValue
from fundautopsy.models.cost_breakdown import CostBreakdown, CostRange
from fundautopsy.models.holdings_tree import FundNode
from fundautopsy.estimates.spread import estimate_bid_ask_spread
from fundautopsy.estimates.impact import estimate_market_impact


# Default turnover assumption when N-CEN doesn't report it
DEFAULT_TURNOVER_RATE = 0.30  # 30% — conservative for active fund


def compute_costs(tree: FundNode) -> FundNode:
    """Compute cost breakdowns for every node in the holdings tree.

    For each fund node:
    - Extracts brokerage commissions from N-CEN
    - Estimates bid-ask spread cost from N-PORT asset class mix + turnover
    - Estimates market-impact cost from fund size + turnover

    Args:
        tree: Holdings tree from detect_structure().

    Returns:
        Same tree with cost_breakdown populated on every node.
    """
    for node in tree.walk():
        node.cost_breakdown = _compute_single_fund_costs(node)
    return tree


def _compute_single_fund_costs(node: FundNode) -> CostBreakdown:
    """Compute costs for a single fund node."""
    breakdown = CostBreakdown(
        ticker=node.metadata.ticker,
        fund_name=node.metadata.name,
    )

    ncen = node.ncen_data
    nport = node.nport_data

    # Net assets — prefer N-PORT (more recent), fall back to N-CEN
    net_assets = None
    if nport and nport.total_net_assets:
        net_assets = nport.total_net_assets
    elif ncen and ncen.total_net_assets and ncen.total_net_assets.is_available:
        net_assets = ncen.total_net_assets.value

    # --- N-CEN derived costs ---
    if ncen is not None:
        # Brokerage commissions in bps
        if ncen.total_brokerage_commissions and ncen.total_brokerage_commissions.is_available:
            comm_dollars = ncen.total_brokerage_commissions.value
            if net_assets and net_assets > 0:
                comm_bps = (comm_dollars / net_assets) * 10_000
                breakdown.brokerage_commissions_bps = TaggedValue(
                    value=round(comm_bps, 2),
                    tag=DataSourceTag.CALCULATED,
                    source_filing=ncen.total_brokerage_commissions.source_filing,
                    note=f"${comm_dollars:,.0f} commissions / ${net_assets:,.0f} net assets",
                )
            else:
                breakdown.brokerage_commissions_bps = TaggedValue(
                    value=None,
                    tag=DataSourceTag.UNAVAILABLE,
                    note="Commissions reported but net assets unavailable for bps conversion",
                )
        else:
            breakdown.brokerage_commissions_bps = TaggedValue(
                value=None,
                tag=DataSourceTag.UNAVAILABLE,
            )

        # Soft dollar flag
        if ncen.has_soft_dollar_arrangements:
            breakdown.soft_dollar_commissions_bps = TaggedValue(
                value=None,
                tag=DataSourceTag.NOT_DISCLOSED,
                note=(
                    "Fund reports soft dollar arrangements but N-CEN XML "
                    "does not separate the dollar amount. Cross-reference SAI."
                ),
            )
        elif ncen.soft_dollar_commissions and ncen.soft_dollar_commissions.is_available:
            sd_dollars = ncen.soft_dollar_commissions.value
            if net_assets and net_assets > 0:
                sd_bps = (sd_dollars / net_assets) * 10_000
                breakdown.soft_dollar_commissions_bps = TaggedValue(
                    value=round(sd_bps, 2),
                    tag=DataSourceTag.CALCULATED,
                    source_filing=ncen.soft_dollar_commissions.source_filing,
                )

    # --- Turnover rate ---
    # Priority: 497K prospectus > N-CEN > default assumption
    turnover_rate = DEFAULT_TURNOVER_RATE
    turnover_source = "default assumption (30%)"

    if node.prospectus_turnover is not None:
        turnover_rate = node.prospectus_turnover / 100.0
        turnover_source = f"497K prospectus ({node.prospectus_turnover:.0f}%)"
    elif ncen and ncen.portfolio_turnover_rate and ncen.portfolio_turnover_rate.is_available:
        turnover_rate = ncen.portfolio_turnover_rate.value / 100.0
        turnover_source = f"N-CEN reported ({turnover_rate:.0%})"

    # --- Estimated costs from N-PORT ---
    if nport is not None and nport.holdings:
        # Bid-ask spread
        breakdown.bid_ask_spread_cost = estimate_bid_ask_spread(nport, turnover_rate)

        # Market impact
        is_small_cap = _is_small_cap_fund(nport)
        if net_assets:
            breakdown.market_impact_cost = estimate_market_impact(
                turnover_rate=turnover_rate,
                total_net_assets=net_assets,
                is_small_cap=is_small_cap,
            )
    else:
        # No N-PORT — can't estimate spread or impact
        breakdown.bid_ask_spread_cost = CostRange(
            low_bps=0, high_bps=0,
            tag=DataSourceTag.UNAVAILABLE,
            methodology="N-PORT data unavailable — cannot estimate bid-ask spread.",
        )
        breakdown.market_impact_cost = CostRange(
            low_bps=0, high_bps=0,
            tag=DataSourceTag.UNAVAILABLE,
            methodology="N-PORT data unavailable — cannot estimate market impact.",
        )

    return breakdown


def _is_small_cap_fund(nport) -> bool:
    """Heuristic: check if fund is primarily small-cap based on avg holding size."""
    if not nport.holdings:
        return False

    # Check average holding value — small cap funds tend to have smaller positions
    values = [h.value_usd for h in nport.holdings if h.value_usd and h.value_usd > 0]
    if not values:
        return False

    avg_holding = sum(values) / len(values)
    # If average holding is under $200M and fund has many holdings, likely small-cap
    return avg_holding < 200_000_000 and len(values) > 50
