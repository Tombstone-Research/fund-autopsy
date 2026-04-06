"""Stage 1b: Fund-of-funds structure detection and holdings tree construction."""

from __future__ import annotations

from typing import Optional

from fundautopsy.models.fund_metadata import FundMetadata
from fundautopsy.models.filing_data import NPortData
from fundautopsy.models.holdings_tree import FundNode
from fundautopsy.data.edgar import MutualFundIdentifier
from fundautopsy.data.ncen import retrieve_ncen
from fundautopsy.data.nport import retrieve_nport, detect_fund_holdings


def detect_structure(fund: FundMetadata, depth: int = 0) -> FundNode:
    """Build a holdings tree by detecting fund-of-funds structures.

    Retrieves N-CEN and N-PORT filings, then scans N-PORT holdings
    for underlying fund positions. For the MVP, we detect fund-of-funds
    but don't recursively resolve underlying fund costs (that requires
    CUSIP-to-CIK resolution which is a Release 2+ feature).

    Args:
        fund: Fund metadata from identify_fund().
        depth: Current recursion depth (internal use).

    Returns:
        Root FundNode with filing data populated.
    """
    fund_id: MutualFundIdentifier = MutualFundIdentifier(
        ticker=fund.ticker,
        cik=int(fund.cik),
        series_id=fund.series_id,
        class_id=fund.class_id,
    )

    node: FundNode = FundNode(
        metadata=fund,
        allocation_weight=1.0,
        depth=depth,
    )

    # Retrieve N-CEN
    ncen_full = retrieve_ncen(fund_id)
    if ncen_full is not None:
        node.ncen_data = ncen_full.to_ncen_data()
        node.ncen_full = ncen_full  # Preserve full N-CEN for supplementary display
        node.ncen_available = True

        # Update fund name from N-CEN (more accurate than registrant name)
        if ncen_full.fund_name:
            fund.name = ncen_full.fund_name

        # Capture service provider info
        if ncen_full.investment_adviser:
            fund.fund_family = ncen_full.investment_adviser
    else:
        node.data_notes.append("N-CEN filing not found — brokerage commission data unavailable")

    # Retrieve N-PORT
    nport: Optional[NPortData] = retrieve_nport(fund_id)
    if nport is not None:
        node.nport_data = nport
        node.nport_available = True

        # Update net assets from N-PORT if we got it
        if nport.total_net_assets:
            fund.total_net_assets = nport.total_net_assets

        # Detect fund-of-funds structure
        fund_holdings = detect_fund_holdings(nport)
        if fund_holdings:
            total_fund_pct: float = sum(h.pct_of_net_assets or 0 for h in fund_holdings)
            # Only classify as true fund-of-funds if underlying funds are >25% of assets
            # Cash sweep vehicles (money market funds) don't make a fund a FoF
            if total_fund_pct > 25.0:
                fund.is_fund_of_funds = True
                node.data_notes.append(
                    f"Fund-of-funds detected: {len(fund_holdings)} underlying fund holdings "
                    f"representing ~{total_fund_pct:.1f}% of net assets. "
                    f"Recursive cost analysis of underlying funds requires CUSIP-to-CIK resolution (future release)."
                )
            elif total_fund_pct > 0.5:
                node.data_notes.append(
                    f"Cash management: {len(fund_holdings)} registered fund holdings "
                    f"(~{total_fund_pct:.1f}% of assets, likely cash sweep vehicles)."
                )
    else:
        node.data_notes.append("N-PORT filing not found — holdings-based estimates unavailable")

    return node
