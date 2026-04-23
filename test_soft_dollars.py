#!/usr/bin/env python3
"""
Test script to analyze 10 common mutual funds for soft dollar costs.

Run with:
    export EDGAR_IDENTITY="Fund Autopsy tombstoneresearch@proton.me"
    python test_soft_dollars.py
"""

import os
import sys
import logging
from typing import Optional

# Set EDGAR identity before imports
if "EDGAR_IDENTITY" not in os.environ:
    os.environ["EDGAR_IDENTITY"] = "Fund Autopsy tombstoneresearch@proton.me"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Test tickers
TEST_TICKERS = ["AGTHX", "VFINX", "FCNTX", "DODGX", "PIMIX", "SWPPX", "VFIAX", "FXAIX", "ABALX", "TRBCX"]

def analyze_fund(ticker: str) -> dict:
    """Run the full Fund Autopsy pipeline on a ticker and extract key metrics."""
    from fundautopsy.core.fund import identify_fund
    from fundautopsy.core.structure import detect_structure
    from fundautopsy.core.costs import compute_costs
    from fundautopsy.core.rollup import rollup_costs
    from fundautopsy.data.prospectus import retrieve_prospectus_fees
    from fundautopsy.models.filing_data import DataSourceTag

    ticker = ticker.strip().upper()
    logger.info(f"Analyzing {ticker}...")

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
            logger.debug(f"Prospectus fetch skipped for {ticker}: {exc}")

        # Compute costs
        tree = compute_costs(tree)
        tree = rollup_costs(tree)

        cb = tree.cost_breakdown

        # Extract metrics
        result = {
            "ticker": ticker,
            "name": cb.fund_name or "Unknown",
            "soft_dollars_active": False,
            "soft_dollar_low_bps": None,
            "soft_dollar_high_bps": None,
            "soft_dollar_estimate": None,
            "brokerage_commissions_bps": None,
            "total_hidden_low_bps": 0,
            "total_hidden_high_bps": 0,
            "error": None,
        }

        if cb:
            # Brokerage commissions
            if cb.brokerage_commissions_bps and cb.brokerage_commissions_bps.is_available:
                result["brokerage_commissions_bps"] = round(cb.brokerage_commissions_bps.value, 2)
                result["total_hidden_low_bps"] += cb.brokerage_commissions_bps.value
                result["total_hidden_high_bps"] += cb.brokerage_commissions_bps.value

            # Soft dollars
            if cb.soft_dollar_commissions_bps:
                sd = cb.soft_dollar_commissions_bps
                if sd.tag == DataSourceTag.ESTIMATED and sd.value is not None:
                    result["soft_dollars_active"] = True
                    sd_low = cb.soft_dollar_commissions_low_bps or 0
                    sd_high = sd.value
                    result["soft_dollar_low_bps"] = round(sd_low, 2)
                    result["soft_dollar_high_bps"] = round(sd_high, 2)
                    result["soft_dollar_estimate"] = f"{sd_low:.1f}–{sd_high:.1f} bps"
                    result["total_hidden_low_bps"] += sd_low
                    result["total_hidden_high_bps"] += sd_high
                elif sd.tag == DataSourceTag.CALCULATED and sd.value is not None:
                    result["soft_dollars_active"] = True
                    result["soft_dollar_low_bps"] = round(sd.value, 2)
                    result["soft_dollar_high_bps"] = round(sd.value, 2)
                    result["soft_dollar_estimate"] = f"{sd.value:.1f} bps"
                    result["total_hidden_low_bps"] += sd.value
                    result["total_hidden_high_bps"] += sd.value
                elif sd.tag == DataSourceTag.NOT_DISCLOSED:
                    result["soft_dollars_active"] = True
                    result["soft_dollar_estimate"] = "ACTIVE (undisclosed)"

            # Spread cost
            if cb.bid_ask_spread_cost and cb.bid_ask_spread_cost.tag != DataSourceTag.UNAVAILABLE:
                result["total_hidden_low_bps"] += cb.bid_ask_spread_cost.low_bps
                result["total_hidden_high_bps"] += cb.bid_ask_spread_cost.high_bps

            # Market impact
            if cb.market_impact_cost and cb.market_impact_cost.tag != DataSourceTag.UNAVAILABLE:
                result["total_hidden_low_bps"] += cb.market_impact_cost.low_bps
                result["total_hidden_high_bps"] += cb.market_impact_cost.high_bps

        result["total_hidden_low_bps"] = round(result["total_hidden_low_bps"], 2)
        result["total_hidden_high_bps"] = round(result["total_hidden_high_bps"], 2)

        logger.info(f"✓ {ticker} analyzed successfully")
        return result

    except ValueError as e:
        logger.error(f"Fund not found: {ticker} - {e}")
        return {
            "ticker": ticker,
            "name": "N/A",
            "error": f"Fund not found: {e}"
        }
    except Exception as e:
        logger.error(f"Analysis failed for {ticker}: {e}", exc_info=True)
        return {
            "ticker": ticker,
            "name": "N/A",
            "error": f"Analysis failed: {e}"
        }


def format_table(results: list[dict]) -> str:
    """Format results as a clean table."""
    lines = []

    # Header
    lines.append("=" * 140)
    lines.append(f"{'Ticker':<8} {'Fund Name':<35} {'Soft $':<8} {'Est. Low':<10} {'Est. High':<10} {'Broker (bps)':<15} {'Total Hidden (Low–High)':<25}")
    lines.append("=" * 140)

    # Rows
    for result in results:
        if "error" in result and result["error"]:
            lines.append(f"{result['ticker']:<8} {'ERROR':<35} {result['error']}")
        else:
            soft_dollars_str = "Yes" if result["soft_dollars_active"] else "No"
            sd_low = f"{result['soft_dollar_low_bps']:.1f}" if result['soft_dollar_low_bps'] is not None else "—"
            sd_high = f"{result['soft_dollar_high_bps']:.1f}" if result['soft_dollar_high_bps'] is not None else "—"
            broker = f"{result['brokerage_commissions_bps']:.2f}" if result['brokerage_commissions_bps'] is not None else "—"
            total_hidden = f"{result['total_hidden_low_bps']:.1f}–{result['total_hidden_high_bps']:.1f}"

            name_truncated = result["name"][:34]
            lines.append(
                f"{result['ticker']:<8} {name_truncated:<35} {soft_dollars_str:<8} {sd_low:<10} {sd_high:<10} {broker:<15} {total_hidden:<25}"
            )

    lines.append("=" * 140)
    return "\n".join(lines)


def main():
    """Run analysis on all test tickers."""
    print("\nFund Autopsy — Soft Dollar Analysis Test")
    print(f"EDGAR Identity: {os.environ.get('EDGAR_IDENTITY', 'default')}\n")

    results = []
    for ticker in TEST_TICKERS:
        result = analyze_fund(ticker)
        results.append(result)

    # Print table
    print("\n" + format_table(results))

    # Summary
    print("\nSummary:")
    analyzed = sum(1 for r in results if "error" not in r or not r["error"])
    with_soft_dollars = sum(1 for r in results if not ("error" in r and r["error"]) and r.get("soft_dollars_active"))
    print(f"  Successfully analyzed: {analyzed}/{len(TEST_TICKERS)}")
    print(f"  Funds with soft dollar arrangements: {with_soft_dollars}/{analyzed}")

    if analyzed < len(TEST_TICKERS):
        print("\nErrors:")
        for r in results:
            if "error" in r and r["error"]:
                print(f"  {r['ticker']}: {r['error']}")

    return 0 if analyzed == len(TEST_TICKERS) else 1


if __name__ == "__main__":
    sys.exit(main())
