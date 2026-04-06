"""Tax drag estimation for mutual funds.

Estimates the tax cost of fund ownership for taxable account holders using
after-tax return disclosures from 497K prospectus filings and turnover data.

Tax drag is the difference between pre-tax and after-tax returns, which
arises from:
  - Short-term capital gains distributions (taxed at ordinary income rates)
  - Long-term capital gains distributions (taxed at LTCG rates)
  - Dividend distributions (taxed at qualified or ordinary rates)

High-turnover funds generate more short-term gains, creating a structural
tax disadvantage that is invisible in standard expense ratio comparisons.

Data sources:
  - 497K: After-tax return disclosures (required by SEC)
  - N-PORT: Holdings turnover patterns
  - N-CEN: Portfolio turnover rate

Academic references:
  - Bergstresser & Poterba (2002) "Do After-Tax Returns Affect Mutual Fund Inflows?"
  - Dickson, Shoven & Sialm (2000) "Tax Externalities of Equity Mutual Funds"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Federal tax rate assumptions (2024 brackets, married filing jointly)
# These are conservative middle-bracket assumptions
ORDINARY_INCOME_RATE = 0.24  # 24% bracket
LTCG_RATE = 0.15  # Most investors
QUALIFIED_DIVIDEND_RATE = 0.15
STATE_TAX_ESTIMATE = 0.05  # Average across states


@dataclass
class TaxDragEstimate:
    """Tax cost estimate for a fund in a taxable account."""

    # Annual tax drag in basis points
    estimated_tax_drag_low_bps: float = 0.0
    estimated_tax_drag_high_bps: float = 0.0

    # Component breakdown
    stcg_drag_bps: float = 0.0  # Short-term capital gains
    ltcg_drag_bps: float = 0.0  # Long-term capital gains
    dividend_drag_bps: float = 0.0  # Dividend tax cost

    # Turnover-based estimate
    turnover_rate_pct: float = 0.0
    implied_stcg_share: float = 0.0  # Estimated share of gains that are short-term

    # Methodology note
    methodology: str = ""
    is_estimated: bool = True


def estimate_tax_drag(
    turnover_rate_pct: float,
    expense_ratio_pct: float = 0.0,
    dividend_yield_pct: float = 0.0,
    is_equity: bool = True,
    is_tax_managed: bool = False,
) -> TaxDragEstimate:
    """Estimate annual tax drag from fund characteristics.

    Uses turnover rate as the primary driver of tax inefficiency.
    Higher turnover generates more realized gains, especially short-term.

    Args:
        turnover_rate_pct: Portfolio turnover rate (e.g., 50 for 50%).
        expense_ratio_pct: Expense ratio for context (not used in calc).
        dividend_yield_pct: Estimated dividend yield.
        is_equity: True for equity funds, False for bond funds.
        is_tax_managed: True if fund explicitly manages for tax efficiency.

    Returns:
        TaxDragEstimate with component breakdown.
    """
    result = TaxDragEstimate(turnover_rate_pct=turnover_rate_pct)
    turnover = turnover_rate_pct / 100.0

    if is_tax_managed:
        # Tax-managed funds minimize distributions
        result.methodology = (
            "Tax-managed fund: reduced estimates applied. "
            "Tax-loss harvesting and low-turnover strategy reduce realized gains."
        )
        turnover *= 0.3  # Much lower effective realization rate

    # Estimate what fraction of realized gains are short-term
    # High turnover -> more short-term (held < 1 year)
    # Academic evidence: funds with >100% turnover generate ~40-60% STCG
    if turnover > 1.0:
        stcg_share = 0.50
    elif turnover > 0.5:
        stcg_share = 0.35
    elif turnover > 0.2:
        stcg_share = 0.20
    else:
        stcg_share = 0.10

    result.implied_stcg_share = stcg_share

    if is_equity:
        # Equity fund: assume ~7% average annual appreciation
        avg_annual_gain = 0.07
        realized_gain = turnover * avg_annual_gain

        stcg = realized_gain * stcg_share
        ltcg = realized_gain * (1 - stcg_share)

        stcg_tax = stcg * (ORDINARY_INCOME_RATE + STATE_TAX_ESTIMATE)
        ltcg_tax = ltcg * (LTCG_RATE + STATE_TAX_ESTIMATE)

        result.stcg_drag_bps = round(stcg_tax * 10000, 1)
        result.ltcg_drag_bps = round(ltcg_tax * 10000, 1)

        # Dividend tax
        if dividend_yield_pct > 0:
            div_yield = dividend_yield_pct / 100.0
            # Assume 70% of equity dividends are qualified
            qualified_pct = 0.70
            div_tax = (div_yield * qualified_pct * (QUALIFIED_DIVIDEND_RATE + STATE_TAX_ESTIMATE) +
                       div_yield * (1 - qualified_pct) * (ORDINARY_INCOME_RATE + STATE_TAX_ESTIMATE))
            result.dividend_drag_bps = round(div_tax * 10000, 1)
    else:
        # Bond fund: interest taxed at ordinary income rates
        avg_yield = 0.04  # ~4% for bond funds
        realized_interest = avg_yield
        interest_tax = realized_interest * (ORDINARY_INCOME_RATE + STATE_TAX_ESTIMATE)
        result.dividend_drag_bps = round(interest_tax * 10000, 1)

        # Bond funds also generate gains/losses from trading
        avg_bond_gain = 0.02
        realized_gain = turnover * avg_bond_gain
        stcg = realized_gain * stcg_share
        ltcg = realized_gain * (1 - stcg_share)
        result.stcg_drag_bps = round(stcg * (ORDINARY_INCOME_RATE + STATE_TAX_ESTIMATE) * 10000, 1)
        result.ltcg_drag_bps = round(ltcg * (LTCG_RATE + STATE_TAX_ESTIMATE) * 10000, 1)

    total = result.stcg_drag_bps + result.ltcg_drag_bps + result.dividend_drag_bps
    # Low estimate: 70% of calculated (conservative assumptions)
    # High estimate: 130% of calculated (aggressive realization)
    result.estimated_tax_drag_low_bps = round(total * 0.70, 1)
    result.estimated_tax_drag_high_bps = round(total * 1.30, 1)

    if not result.methodology:
        result.methodology = (
            f"Tax drag estimated from {turnover_rate_pct:.0f}% turnover rate. "
            f"Assumes {ORDINARY_INCOME_RATE:.0%} ordinary income rate, "
            f"{LTCG_RATE:.0%} LTCG rate, {STATE_TAX_ESTIMATE:.0%} state tax. "
            f"Short-term gain share estimated at {stcg_share:.0%} based on turnover level. "
            f"Applies only to taxable accounts. IRAs and 401(k)s are tax-deferred."
        )

    return result


def tax_drag_comparison_text(
    fund_ticker: str,
    tax_drag: TaxDragEstimate,
    expense_ratio_pct: Optional[float] = None,
) -> str:
    """Generate a plain-text comparison of tax drag vs expense ratio.

    Useful for X thread content and reports.
    """
    low = tax_drag.estimated_tax_drag_low_bps
    high = tax_drag.estimated_tax_drag_high_bps

    text = f"{fund_ticker}: Estimated tax drag {low:.0f}–{high:.0f} bps"

    if expense_ratio_pct is not None:
        er_bps = expense_ratio_pct * 100
        midpoint = (low + high) / 2
        if midpoint > er_bps:
            text += f" (exceeds the {er_bps:.0f} bps expense ratio)"
        elif midpoint > er_bps * 0.5:
            text += f" (adds {midpoint/er_bps:.0%} to the {er_bps:.0f} bps expense ratio)"

    text += f"\n  STCG: {tax_drag.stcg_drag_bps:.0f} bps | LTCG: {tax_drag.ltcg_drag_bps:.0f} bps | Dividends: {tax_drag.dividend_drag_bps:.0f} bps"
    text += f"\n  Turnover: {tax_drag.turnover_rate_pct:.0f}% | Est. STCG share: {tax_drag.implied_stcg_share:.0%}"

    return text
