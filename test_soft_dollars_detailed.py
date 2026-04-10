#!/usr/bin/env python3
"""
Detailed test script to analyze 10 common mutual funds for soft dollar costs.
Includes breakdown of all cost components.

Run with:
    export EDGAR_IDENTITY="Fund Autopsy fundautopsy@tombstoneresearch.com"
    python test_soft_dollars_detailed.py
"""

import os
import sys
import logging
from typing import Optional

# Set EDGAR identity before imports
if "EDGAR_IDENTITY" not in os.environ:
    os.environ["EDGAR_IDENTITY"] = "Fund Autopsy fundautopsy@tombstoneresearch.com"

# Set up logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Test tickers
TEST_TICKERS = ["AGTHX", "VFINX", "FCNTX", "DODGX", "PIMIX", "SWPPX", "VFIAX", "FXAIX", "ABALX", "TRBCX"]

def analyze_fund_detailed(ticker: str) -> dict:
    """Run full analysis and extract detailed cost breakdown."""
    from fundautopsy.core.fund import identify_fund
    from fundautopsy.core.structure import detect_structure
    from fundautopsy.core.costs import compute_costs
    from fundautopsy.core.rollup import rollup_costs
    from fundautopsy.data.prospectus import retrieve_prospectus_fees
    from fundautopsy.models.filing_data import DataSourceTag

    ticker = ticker.strip().upper()
    print(f"\n{'='*80}")
    print(f"ANALYZING: {ticker}")
    print(f"{'='*80}")

    try:
        # Identify fund and build structure
        fund = identify_fund(ticker)
        tree = detect_structure(fund)

        # Get prospectus data
        prospectus_fees = None
        try:
            prospectus_fees = retrieve_prospectus_fees(
                ticker, series_id=fund.series_id, class_id=fund.class_id
            )
            if prospectus_fees and prospectus_fees.portfolio_turnover is not None:
                tree.prospectus_turnover = prospectus_fees.portfolio_turnover
        except Exception as exc:
            logger.debug(f"Prospectus fetch skipped: {exc}")

        # Compute costs
        tree = compute_costs(tree)
        tree = rollup_costs(tree)

        cb = tree.cost_breakdown

        # Print fund info
        print(f"\nFund Name: {cb.fund_name}")
        print(f"Net Assets: ${tree.nport_data.total_net_assets / 1_000_000_000:.2f}B" if tree.nport_data and tree.nport_data.total_net_assets else "Net Assets: N/A")

        # Cost breakdown
        print(f"\n--- Cost Breakdown ---")

        if cb:
            # Brokerage commissions
            if cb.brokerage_commissions_bps and cb.brokerage_commissions_bps.is_available:
                print(f"Brokerage Commissions:  {cb.brokerage_commissions_bps.value:>8.2f} bps ({cb.brokerage_commissions_bps.tag.name})")
                if cb.brokerage_commissions_bps.note:
                    print(f"  └─ {cb.brokerage_commissions_bps.note}")
            else:
                print(f"Brokerage Commissions:       N/A")

            # Soft dollars
            if cb.soft_dollar_commissions_bps:
                sd = cb.soft_dollar_commissions_bps
                if sd.tag == DataSourceTag.ESTIMATED and sd.value is not None:
                    sd_low = cb.soft_dollar_commissions_low_bps or 0
                    print(f"Soft Dollar Cost (Est):  {sd_low:.2f}–{sd.value:.2f} bps (ESTIMATED)")
                    print(f"  └─ Based on 30-45% of brokerage commissions")
                    if sd.note:
                        print(f"  └─ {sd.note[:100]}...")
                elif sd.tag == DataSourceTag.CALCULATED and sd.value is not None:
                    print(f"Soft Dollar Cost:       {sd.value:>8.2f} bps (REPORTED)")
                    if sd.note:
                        print(f"  └─ {sd.note}")
                elif sd.tag == DataSourceTag.NOT_DISCLOSED:
                    print(f"Soft Dollar Cost:              ACTIVE (amount not disclosed)")
                    if sd.note:
                        print(f"  └─ {sd.note}")
            else:
                print(f"Soft Dollar Cost:              Not active")

            # Bid-ask spread
            if cb.bid_ask_spread_cost and cb.bid_ask_spread_cost.tag != DataSourceTag.UNAVAILABLE:
                print(f"Bid-Ask Spread Cost:    {cb.bid_ask_spread_cost.low_bps:.2f}–{cb.bid_ask_spread_cost.high_bps:.2f} bps (ESTIMATED)")
            else:
                print(f"Bid-Ask Spread Cost:         N/A")

            # Market impact
            if cb.market_impact_cost and cb.market_impact_cost.tag != DataSourceTag.UNAVAILABLE:
                print(f"Market Impact Cost:     {cb.market_impact_cost.low_bps:.2f}–{cb.market_impact_cost.high_bps:.2f} bps (ESTIMATED)")
            else:
                print(f"Market Impact Cost:          N/A")

            # Total hidden costs
            total_low = max(0, sum(
                c for c in [
                    cb.brokerage_commissions_bps.value if cb.brokerage_commissions_bps and cb.brokerage_commissions_bps.is_available else 0,
                    cb.soft_dollar_commissions_low_bps or 0 if cb.soft_dollar_commissions_bps else 0,
                    cb.bid_ask_spread_cost.low_bps if cb.bid_ask_spread_cost and cb.bid_ask_spread_cost.tag != DataSourceTag.UNAVAILABLE else 0,
                    cb.market_impact_cost.low_bps if cb.market_impact_cost and cb.market_impact_cost.tag != DataSourceTag.UNAVAILABLE else 0,
                ]
            ))
            total_high = max(0, sum(
                c for c in [
                    cb.brokerage_commissions_bps.value if cb.brokerage_commissions_bps and cb.brokerage_commissions_bps.is_available else 0,
                    (cb.soft_dollar_commissions_bps.value if cb.soft_dollar_commissions_bps else 0),
                    cb.bid_ask_spread_cost.high_bps if cb.bid_ask_spread_cost and cb.bid_ask_spread_cost.tag != DataSourceTag.UNAVAILABLE else 0,
                    cb.market_impact_cost.high_bps if cb.market_impact_cost and cb.market_impact_cost.tag != DataSourceTag.UNAVAILABLE else 0,
                ]
            ))

            print(f"\n--- Total Hidden Costs ---")
            print(f"Range: {total_low:.2f}–{total_high:.2f} bps")

        return {"ticker": ticker, "name": cb.fund_name, "success": True}

    except ValueError as e:
        print(f"\nERROR: Fund not found - {e}")
        return {"ticker": ticker, "success": False, "error": str(e)}
    except Exception as e:
        print(f"\nERROR: Analysis failed - {e}")
        import traceback
        traceback.print_exc()
        return {"ticker": ticker, "success": False, "error": str(e)}


def main():
    """Run detailed analysis on all test tickers."""
    print("\n" + "="*80)
    print("Fund Autopsy — Soft Dollar Analysis (Detailed)")
    print(f"EDGAR Identity: {os.environ.get('EDGAR_IDENTITY', 'default')}")
    print("="*80)

    results = []
    for ticker in TEST_TICKERS:
        result = analyze_fund_detailed(ticker)
        results.append(result)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    success_count = sum(1 for r in results if r["success"])
    print(f"\nSuccessfully analyzed: {success_count}/{len(TEST_TICKERS)}")

    if success_count < len(TEST_TICKERS):
        print("\nErrors:")
        for r in results:
            if not r["success"]:
                print(f"  {r['ticker']}: {r['error']}")

    return 0 if success_count == len(TEST_TICKERS) else 1


if __name__ == "__main__":
    sys.exit(main())
