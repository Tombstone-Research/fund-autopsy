"""Prospectus fee data retrieval via edgartools 497K parsing.

Extracts expense ratio components and portfolio turnover from
SEC Form 497K (Summary Prospectus) filings.

Strategy:
1. Try edgartools' built-in 497K parser (works for most fund families)
2. If edgartools returns all-None fee fields, fall back to our custom
   HTML parser that handles Dodge & Cox, Oakmark, Fidelity, and other
   non-standard table formats
3. For multi-fund trusts that file separate 497Ks per share class,
   search through recent filings to find the one containing the ticker
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import edgar

from fundautopsy.data.fee_parser import find_filing_for_ticker, parse_497k_html


# Set identity for EDGAR access
edgar.set_identity("FundAutopsy fundautopsy@tombstoneresearch.com")


@dataclass
class ProspectusFees:
    """Fee data extracted from 497K summary prospectus."""

    ticker: str
    class_name: str

    # Fee components (as percentages, e.g., 0.59 = 0.59%)
    total_annual_expenses: Optional[float] = None
    net_expenses: Optional[float] = None  # After waivers
    management_fee: Optional[float] = None
    twelve_b1_fee: Optional[float] = None
    other_expenses: Optional[float] = None
    acquired_fund_fees: Optional[float] = None
    fee_waiver: Optional[float] = None

    # Loads
    max_sales_load: Optional[float] = None
    max_deferred_sales_load: Optional[float] = None
    redemption_fee: Optional[float] = None

    # Portfolio turnover (as percentage, e.g., 32 = 32%)
    portfolio_turnover: Optional[float] = None

    @property
    def expense_ratio_pct(self) -> Optional[float]:
        """Net expense ratio (after waivers), falling back to gross."""
        if self.net_expenses is not None:
            return self.net_expenses
        return self.total_annual_expenses

    @property
    def expense_ratio_bps(self) -> Optional[float]:
        """Expense ratio in basis points."""
        er = self.expense_ratio_pct
        if er is not None:
            return er * 100
        return None


def _edgartools_has_fees(target_class) -> bool:
    """Check if edgartools actually parsed fee values (not all None)."""
    return any(
        getattr(target_class, attr, None) is not None
        for attr in (
            "management_fee",
            "total_annual_expenses",
            "net_expenses",
        )
    )


def retrieve_prospectus_fees(
    ticker: str,
    series_id: Optional[str] = None,
    class_id: Optional[str] = None,
) -> Optional[ProspectusFees]:
    """Retrieve fee data from the most recent 497K filing.

    Uses edgartools to find the fund and locate 497K filings. If the
    built-in parser returns empty fee fields, falls back to our custom
    HTML parser. For multi-fund trusts, searches through filings to
    find the one containing the specific ticker.

    Args:
        ticker: Fund ticker symbol.
        series_id: Optional series ID for matching.
        class_id: Optional class ID for matching.

    Returns:
        ProspectusFees if found, None otherwise.
    """
    try:
        fund_class = edgar.find_fund(ticker.upper())
        if fund_class is None:
            return None

        series = fund_class.series
        fund_name = series.name if hasattr(series, "name") else None
        filings = series.get_filings()
        k497_filings = filings.filter(form="497K")

        if len(k497_filings) == 0:
            return None

        # --- Try edgartools built-in parser first ---
        result = _try_edgartools_parser(k497_filings, ticker, class_id)
        if result is not None:
            return result

        # --- Fall back to custom HTML parser ---
        # First, find the right filing (may need to search for multi-fund trusts)
        filing = find_filing_for_ticker(k497_filings, ticker)
        if filing is None:
            # Fall back to the most recent filing
            filing = k497_filings[0]

        html = filing.html()
        if not html:
            return None

        parsed = parse_497k_html(html, ticker, fund_name)
        if not parsed.has_data:
            return None

        # Compute total from components if not directly available
        total = parsed.total_annual_expenses
        if total is None and parsed.management_fee is not None:
            total = (parsed.management_fee or 0) + (parsed.twelve_b1_fee or 0) + (parsed.other_expenses or 0)
            total = round(total, 2)

        return ProspectusFees(
            ticker=ticker.upper(),
            class_name="",
            total_annual_expenses=total,
            net_expenses=parsed.net_expenses,
            management_fee=parsed.management_fee,
            twelve_b1_fee=parsed.twelve_b1_fee,
            other_expenses=parsed.other_expenses,
            acquired_fund_fees=parsed.acquired_fund_fees,
            fee_waiver=parsed.fee_waiver,
            max_sales_load=parsed.max_sales_load,
            portfolio_turnover=parsed.portfolio_turnover,
        )

    except Exception:
        # Prospectus parsing is best-effort — don't crash the pipeline
        return None


def _try_edgartools_parser(
    k497_filings, ticker: str, class_id: Optional[str]
) -> Optional[ProspectusFees]:
    """Attempt to extract fees using edgartools' built-in 497K parser."""
    try:
        prospectus = k497_filings[0].obj()
        if prospectus is None:
            return None

        # Find the matching share class
        target_class = None
        for sc in prospectus.share_classes:
            if sc.ticker and sc.ticker.upper() == ticker.upper():
                target_class = sc
                break
            if class_id and sc.class_id == class_id:
                target_class = sc
                break

        if target_class is None:
            if len(prospectus.share_classes) == 1:
                target_class = prospectus.share_classes[0]
            else:
                return None

        # Check if edgartools actually extracted fee values
        if not _edgartools_has_fees(target_class):
            return None

        return ProspectusFees(
            ticker=ticker.upper(),
            class_name=target_class.class_name or "",
            total_annual_expenses=_to_float(target_class.total_annual_expenses),
            net_expenses=_to_float(target_class.net_expenses),
            management_fee=_to_float(target_class.management_fee),
            twelve_b1_fee=_to_float(target_class.twelve_b1_fee),
            other_expenses=_to_float(target_class.other_expenses),
            acquired_fund_fees=_to_float(target_class.acquired_fund_fees),
            fee_waiver=_to_float(target_class.fee_waiver),
            max_sales_load=_to_float(target_class.max_sales_load),
            max_deferred_sales_load=_to_float(
                target_class.max_deferred_sales_load
            ),
            redemption_fee=_to_float(target_class.redemption_fee),
            portfolio_turnover=_to_float(prospectus.portfolio_turnover),
        )
    except Exception:
        return None


def _to_float(val) -> Optional[float]:
    """Convert Decimal or other numeric to float, or None."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
