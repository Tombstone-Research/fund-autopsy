"""Fund Autopsy web API — real-time fund cost analysis.

Run with: python -m fundautopsy.web
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fundautopsy.config import CORS_ALLOWED_ORIGINS
from fundautopsy.models.filing_data import DataSourceTag
from fundautopsy.data.edgar import reset_edgar_health, get_edgar_health
from fundautopsy.data.leaderboard import (
    update_leaderboard, get_leaderboard, get_leaderboard_stats,
)
from fundautopsy.data.fee_tracker import track_fee_changes, FeeHistory
from fundautopsy.data.ncsr_parser import parse_ncsr_for_cik

app = FastAPI(title="Fund Autopsy", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Mount static files (CSS, JS, and related assets)
import os
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


class CostComponent(BaseModel):
    """A single cost component in the fund's cost breakdown."""

    label: str
    value: Optional[str]
    low: Optional[float] = None
    high: Optional[float] = None
    tag: str
    note: Optional[str] = None


class FeeComponent(BaseModel):
    """Fee component expressed as percentage and basis points."""

    label: str
    pct: Optional[float]
    bps: Optional[float]


class AssetMix(BaseModel):
    """Asset class allocation data."""

    category: str
    label: str
    color: str
    pct: float


class BrokerInfo(BaseModel):
    """Broker commission data."""

    name: str
    commission: float
    is_affiliated: bool


class SecuritiesLendingInfo(BaseModel):
    """Securities lending arrangement details."""

    is_lending: bool
    agent_name: Optional[str] = None
    is_agent_affiliated: bool = False
    net_income: Optional[float] = None
    avg_value_on_loan: Optional[float] = None


class ServiceProviders(BaseModel):
    """Key service providers for the fund."""

    adviser: Optional[str] = None
    administrator: Optional[str] = None
    custodian: Optional[str] = None
    transfer_agent: Optional[str] = None
    auditor: Optional[str] = None
    is_admin_affiliated: bool = False
    is_transfer_agent_affiliated: bool = False


class DollarImpact(BaseModel):
    """Dollar impact of costs over an investment horizon."""

    investment: float
    horizon_years: int
    assumed_return_pct: float
    expense_ratio_only_cost: Optional[float]
    true_cost_low: Optional[float]
    true_cost_high: Optional[float]
    hidden_cost_low: Optional[float]
    hidden_cost_high: Optional[float]
    final_value_er_only: Optional[float]
    final_value_true_low: Optional[float]
    final_value_true_high: Optional[float]


class FundAnalysis(BaseModel):
    """Complete fund analysis response with all cost data."""
    ticker: str
    name: str
    family: str
    share_class: Optional[str] = None
    net_assets: Optional[float]
    net_assets_display: str
    holdings_count: int
    period_end: Optional[str]
    is_fund_of_funds: bool

    # Expense ratio from prospectus
    expense_ratio_pct: Optional[float] = None
    expense_ratio_bps: Optional[float] = None
    fee_breakdown: List[FeeComponent] = []
    portfolio_turnover: Optional[float] = None
    max_sales_load: Optional[float] = None

    # Hidden costs
    costs: List[CostComponent]
    total_hidden_low: Optional[float]
    total_hidden_high: Optional[float]

    # True total cost = ER + hidden
    true_cost_low_bps: Optional[float] = None
    true_cost_high_bps: Optional[float] = None
    true_cost_low_pct: Optional[float] = None
    true_cost_high_pct: Optional[float] = None

    # Dollar impact
    dollar_impact: Optional[DollarImpact] = None

    # N-CEN supplementary data
    top_brokers: List[BrokerInfo] = []
    affiliated_brokers: List[BrokerInfo] = []
    securities_lending: Optional[SecuritiesLendingInfo] = None
    service_providers: Optional[ServiceProviders] = None
    aggregate_commission_dollars: Optional[float] = None

    asset_mix: List[AssetMix]
    conflict_flags: List[str] = []
    data_notes: List[str]
    edgar_status: Optional[str] = None  # "ok" | "degraded" — subtle flakiness indicator
    generated: str


ASSET_CAT_META = {
    "EC": ("Equity", "#4ade80"),
    "EP": ("Preferred", "#a78bfa"),
    "DBT": ("Debt", "#60a5fa"),
    "STIV": ("Cash/STIV", "#fbbf24"),
    "OTHER": ("Other", "#94a3b8"),
}


def _fmt_dollars(amount: float) -> str:
    if abs(amount) >= 1e12:
        return f"${amount / 1e12:.1f}T"
    if abs(amount) >= 1e9:
        return f"${amount / 1e9:.1f}B"
    if abs(amount) >= 1e6:
        return f"${amount / 1e6:.1f}M"
    return f"${amount:,.0f}"


def _compute_dollar_impact(
    expense_ratio_pct: Optional[float],
    hidden_low_bps: Optional[float],
    hidden_high_bps: Optional[float],
    investment: Optional[float] = None,
    horizon: Optional[int] = None,
    annual_return: Optional[float] = None,
) -> DollarImpact:
    """Compute dollar cost of fees over time using compound drag."""
    from fundautopsy.config import DEFAULT_INVESTMENT, DEFAULT_HORIZON_YEARS, DEFAULT_ANNUAL_RETURN_PCT

    investment = investment if investment is not None else DEFAULT_INVESTMENT
    horizon = horizon if horizon is not None else DEFAULT_HORIZON_YEARS
    annual_return = annual_return if annual_return is not None else DEFAULT_ANNUAL_RETURN_PCT
    gross_return = annual_return / 100

    # ER-only scenario
    er_only_cost = None
    final_er_only = None
    if expense_ratio_pct is not None:
        er_drag = expense_ratio_pct / 100
        final_er_only = investment * ((1 + gross_return - er_drag) ** horizon)
        no_cost_final = investment * ((1 + gross_return) ** horizon)
        er_only_cost = no_cost_final - final_er_only

    # True cost scenarios (ER + hidden costs combined)
    # "best case" = lowest drag estimate; "worst case" = highest drag estimate
    cost_best_case = None
    cost_worst_case = None
    hidden_cost_best = None
    hidden_cost_worst = None
    final_value_best_case = None
    final_value_worst_case = None

    no_cost_final = investment * ((1 + gross_return) ** horizon)

    if expense_ratio_pct is not None and hidden_low_bps is not None:
        # Convert to decimal drag: pct / 100, bps / 10_000
        drag_best = expense_ratio_pct / 100 + hidden_low_bps / 10_000
        drag_worst = expense_ratio_pct / 100 + hidden_high_bps / 10_000

        # Higher drag produces lower final value
        final_value_worst_case = investment * ((1 + gross_return - drag_worst) ** horizon)
        final_value_best_case = investment * ((1 + gross_return - drag_best) ** horizon)

        # Dollar cost = what you lose vs. zero-cost scenario
        cost_best_case = no_cost_final - final_value_best_case
        cost_worst_case = no_cost_final - final_value_worst_case
        if er_only_cost is not None:
            hidden_cost_best = cost_best_case - er_only_cost
            hidden_cost_worst = cost_worst_case - er_only_cost

    return DollarImpact(
        investment=investment,
        horizon_years=horizon,
        assumed_return_pct=annual_return,
        expense_ratio_only_cost=round(er_only_cost) if er_only_cost else None,
        true_cost_low=round(cost_best_case) if cost_best_case else None,
        true_cost_high=round(cost_worst_case) if cost_worst_case else None,
        hidden_cost_low=round(hidden_cost_best) if hidden_cost_best else None,
        hidden_cost_high=round(hidden_cost_worst) if hidden_cost_worst else None,
        final_value_er_only=round(final_er_only) if final_er_only else None,
        final_value_true_low=round(final_value_best_case) if final_value_best_case else None,
        final_value_true_high=round(final_value_worst_case) if final_value_worst_case else None,
    )


@app.get("/api/analyze/{ticker}", response_model=FundAnalysis)
def analyze_fund(ticker: str):
    """Run the full Fund Autopsy pipeline on a ticker and return structured results."""
    ticker = ticker.strip().upper()
    if not ticker or not ticker.isalpha() or len(ticker) > 6:
        raise HTTPException(400, "Invalid ticker format")

    reset_edgar_health()

    try:
        from fundautopsy.core.fund import identify_fund
        from fundautopsy.core.structure import detect_structure
        from fundautopsy.core.costs import compute_costs
        from fundautopsy.core.rollup import rollup_costs
        from fundautopsy.data.prospectus import retrieve_prospectus_fees as _get_fees

        fund = identify_fund(ticker)
        tree = detect_structure(fund)

        # Fetch prospectus data early so turnover feeds into cost estimates
        _prospectus_fees = None
        try:
            _prospectus_fees = _get_fees(
                ticker, series_id=fund.series_id, class_id=fund.class_id
            )
            if _prospectus_fees and _prospectus_fees.portfolio_turnover is not None:
                tree.prospectus_turnover = _prospectus_fees.portfolio_turnover
        except Exception as exc:
            logger.warning("Prospectus fetch failed for %s: %s", ticker, exc)

        tree = compute_costs(tree)
        tree = rollup_costs(tree)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("Analysis failed for %s", ticker)
        raise HTTPException(500, "Analysis failed due to an internal error")

    cb = tree.cost_breakdown
    nport = tree.nport_data
    meta = tree.metadata

    # --- Prospectus fee data (already fetched above for turnover) ---
    prospectus_fees = _prospectus_fees

    expense_ratio_pct = None
    expense_ratio_bps = None
    fee_breakdown = []
    portfolio_turnover = None
    max_sales_load = None
    share_class = None

    if prospectus_fees:
        expense_ratio_pct = prospectus_fees.expense_ratio_pct
        expense_ratio_bps = prospectus_fees.expense_ratio_bps
        share_class = prospectus_fees.class_name
        portfolio_turnover = prospectus_fees.portfolio_turnover
        max_sales_load = prospectus_fees.max_sales_load

        if prospectus_fees.management_fee is not None:
            fee_breakdown.append(FeeComponent(
                label="Management Fee",
                pct=prospectus_fees.management_fee,
                bps=prospectus_fees.management_fee * 100,
            ))
        if prospectus_fees.twelve_b1_fee is not None:
            fee_breakdown.append(FeeComponent(
                label="12b-1 Fee",
                pct=prospectus_fees.twelve_b1_fee,
                bps=prospectus_fees.twelve_b1_fee * 100,
            ))
        if prospectus_fees.other_expenses is not None:
            fee_breakdown.append(FeeComponent(
                label="Other Expenses",
                pct=prospectus_fees.other_expenses,
                bps=prospectus_fees.other_expenses * 100,
            ))
        if prospectus_fees.acquired_fund_fees is not None:
            fee_breakdown.append(FeeComponent(
                label="Acquired Fund Fees",
                pct=prospectus_fees.acquired_fund_fees,
                bps=prospectus_fees.acquired_fund_fees * 100,
            ))

    # --- Build hidden cost components ---
    costs = []

    if cb:
        # Brokerage
        if cb.brokerage_commissions_bps and cb.brokerage_commissions_bps.is_available:
            costs.append(CostComponent(
                label="Brokerage Commissions",
                value=f"{cb.brokerage_commissions_bps.value:.2f}",
                low=cb.brokerage_commissions_bps.value,
                high=cb.brokerage_commissions_bps.value,
                tag="reported",
                note=cb.brokerage_commissions_bps.note,
            ))
        else:
            costs.append(CostComponent(
                label="Brokerage Commissions", value=None, tag="unavailable"
            ))

        # Soft dollars
        if (
            cb.soft_dollar_commissions_bps
            and cb.soft_dollar_commissions_bps.tag == DataSourceTag.NOT_DISCLOSED
        ):
            costs.append(CostComponent(
                label="Soft Dollar Arrangements",
                value="ACTIVE",
                tag="warning",
                note="Fund uses client commissions to pay for research. Dollar amount not disclosed.",
            ))

        # Spread
        if cb.bid_ask_spread_cost and cb.bid_ask_spread_cost.tag != DataSourceTag.UNAVAILABLE:
            costs.append(CostComponent(
                label="Bid-Ask Spread Cost",
                value=f"{cb.bid_ask_spread_cost.low_bps:.1f} – {cb.bid_ask_spread_cost.high_bps:.1f}",
                low=cb.bid_ask_spread_cost.low_bps,
                high=cb.bid_ask_spread_cost.high_bps,
                tag="estimated",
            ))

        # Impact
        if cb.market_impact_cost and cb.market_impact_cost.tag != DataSourceTag.UNAVAILABLE:
            costs.append(CostComponent(
                label="Market Impact Cost",
                value=f"{cb.market_impact_cost.low_bps:.1f} – {cb.market_impact_cost.high_bps:.1f}",
                low=cb.market_impact_cost.low_bps,
                high=cb.market_impact_cost.high_bps,
                tag="estimated",
            ))

    # Totals
    total_hidden_low = max(0, sum(
        c.low for c in costs if c.low is not None and c.tag != "warning"
    ))
    total_hidden_high = max(0, sum(
        c.high for c in costs if c.high is not None and c.tag != "warning"
    ))

    # True total cost
    true_cost_low_bps = None
    true_cost_high_bps = None
    true_cost_low_pct = None
    true_cost_high_pct = None
    if expense_ratio_bps is not None:
        true_cost_low_bps = round(expense_ratio_bps + total_hidden_low, 2)
        true_cost_high_bps = round(expense_ratio_bps + total_hidden_high, 2)
        true_cost_low_pct = round(true_cost_low_bps / 100, 3)
        true_cost_high_pct = round(true_cost_high_bps / 100, 3)

    # Dollar impact
    dollar_impact = _compute_dollar_impact(
        expense_ratio_pct=expense_ratio_pct,
        hidden_low_bps=total_hidden_low,
        hidden_high_bps=total_hidden_high,
    )

    # Asset mix
    mix_list = []
    if nport:
        weights = nport.asset_class_weights()
        for cat, pct in sorted(weights.items(), key=lambda x: -x[1]):
            label, color = ASSET_CAT_META.get(cat, (cat, "#94a3b8"))
            mix_list.append(AssetMix(
                category=cat, label=label, color=color, pct=round(pct, 2)
            ))

    # --- N-CEN supplementary data ---
    top_brokers = []
    affiliated_brokers_list = []
    securities_lending_info = None
    service_providers = None
    aggregate_commission_dollars = None

    ncen_full = tree.ncen_full
    if ncen_full is not None:
        aggregate_commission_dollars = ncen_full.aggregate_commission

        for b in ncen_full.top_brokers[:10]:
            top_brokers.append(BrokerInfo(
                name=b.name, commission=b.gross_commission, is_affiliated=False
            ))
        for b in ncen_full.affiliated_brokers:
            affiliated_brokers_list.append(BrokerInfo(
                name=b.name, commission=b.gross_commission, is_affiliated=True
            ))

        if ncen_full.securities_lending:
            sl = ncen_full.securities_lending
            securities_lending_info = SecuritiesLendingInfo(
                is_lending=sl.is_lending,
                agent_name=sl.agent_name or None,
                is_agent_affiliated=sl.is_agent_affiliated,
                net_income=sl.net_income,
                avg_value_on_loan=sl.avg_portfolio_value_on_loan,
            )

        service_providers = ServiceProviders(
            adviser=ncen_full.investment_adviser or None,
            administrator=ncen_full.administrator or None,
            custodian=ncen_full.custodian_primary or None,
            transfer_agent=ncen_full.transfer_agent or None,
            auditor=ncen_full.auditor or None,
            is_admin_affiliated=ncen_full.is_admin_affiliated,
            is_transfer_agent_affiliated=ncen_full.is_transfer_agent_affiliated,
        )

    na = nport.total_net_assets if nport else None

    # --- Build conflict flags from N-CEN data ---
    conflict_flags = []
    if ncen_full is not None:
        if ncen_full.is_brokerage_research_payment:
            conflict_flags.append("Soft dollar arrangements: fund pays inflated commissions for manager's research")
        if ncen_full.affiliated_brokers:
            aff_total = sum(b.gross_commission for b in ncen_full.affiliated_brokers)
            agg = ncen_full.aggregate_commission
            if agg and agg > 0:
                aff_pct = aff_total / agg * 100
                conflict_flags.append(
                    f"Affiliated broker usage: {len(ncen_full.affiliated_brokers)} affiliated broker(s), "
                    f"${aff_total:,.0f} in commissions ({aff_pct:.1f}% of total)"
                )
            else:
                conflict_flags.append(
                    f"Affiliated broker usage: {len(ncen_full.affiliated_brokers)} affiliated broker(s), "
                    f"${aff_total:,.0f} in commissions"
                )
        if ncen_full.is_admin_affiliated:
            conflict_flags.append("Fund administrator is affiliated with the investment adviser")
        if ncen_full.is_transfer_agent_affiliated:
            conflict_flags.append("Transfer agent is affiliated with the investment adviser")
        if ncen_full.securities_lending and ncen_full.securities_lending.is_lending:
            sl = ncen_full.securities_lending
            if sl.is_agent_affiliated:
                conflict_flags.append("Securities lending agent is affiliated with the fund")
            if sl.net_income and sl.net_income > 0:
                conflict_flags.append(
                    f"Securities lending active: ${sl.net_income:,.0f} net income "
                    f"(offsets costs but rarely disclosed to investors)"
                )

    # --- Update leaderboard with this analysis ---
    try:
        update_leaderboard(
            ticker=meta.ticker,
            name=meta.name,
            family=meta.fund_family or "",
            hidden_low_bps=total_hidden_low,
            hidden_high_bps=total_hidden_high,
            expense_ratio_bps=expense_ratio_bps,
            turnover_pct=portfolio_turnover,
            net_assets_display=_fmt_dollars(na) if na else "N/A",
            holdings_count=len(nport.holdings) if nport else 0,
            conflict_count=len(conflict_flags),
            dollar_impact_hidden_low=dollar_impact.hidden_cost_low,
            dollar_impact_hidden_high=dollar_impact.hidden_cost_high,
        )
    except Exception as exc:
        logger.debug("Leaderboard update failed for %s: %s", meta.ticker, exc)

    # Determine EDGAR health status for subtle frontend indicator
    health = get_edgar_health()
    edgar_status = "degraded" if health["retries"] > 0 or health["errors"] > 0 else "ok"

    return FundAnalysis(
        ticker=meta.ticker,
        name=meta.name,
        family=meta.fund_family or "",
        share_class=share_class,
        net_assets=na,
        net_assets_display=_fmt_dollars(na) if na else "N/A",
        holdings_count=len(nport.holdings) if nport else 0,
        period_end=str(nport.reporting_period_end) if nport else None,
        is_fund_of_funds=meta.is_fund_of_funds,
        expense_ratio_pct=expense_ratio_pct,
        expense_ratio_bps=expense_ratio_bps,
        fee_breakdown=fee_breakdown,
        portfolio_turnover=portfolio_turnover,
        max_sales_load=max_sales_load,
        costs=costs,
        total_hidden_low=round(total_hidden_low, 2) if total_hidden_low is not None else None,
        total_hidden_high=round(total_hidden_high, 2) if total_hidden_high is not None else None,
        true_cost_low_bps=true_cost_low_bps,
        true_cost_high_bps=true_cost_high_bps,
        true_cost_low_pct=true_cost_low_pct,
        true_cost_high_pct=true_cost_high_pct,
        dollar_impact=dollar_impact,
        top_brokers=top_brokers,
        affiliated_brokers=affiliated_brokers_list,
        securities_lending=securities_lending_info,
        service_providers=service_providers,
        aggregate_commission_dollars=aggregate_commission_dollars,
        asset_mix=mix_list,
        conflict_flags=conflict_flags,
        data_notes=tree.data_notes,
        edgar_status=edgar_status,
        generated=str(date.today()),
    )


class SAICommission(BaseModel):
    """Historical brokerage commission data from SAI."""

    fund_name: str
    annual_commissions: Dict[int, float]


class SAIPMCompensation(BaseModel):
    """Portfolio manager compensation structure from SAI."""

    has_base_salary: bool
    has_bonus: bool
    has_equity_ownership: bool
    has_deferred_comp: bool
    bonus_linked_to_performance: bool
    bonus_linked_to_aum: bool
    bonus_linked_to_firm_profit: bool
    compensation_not_linked_to_fund_performance: bool
    description: str


class SAISoftDollar(BaseModel):
    """Soft dollar arrangement details from SAI."""

    has_soft_dollar_arrangements: bool
    uses_commission_sharing: bool
    description: str


class SAIAnalysis(BaseModel):
    """Complete SAI (Statement of Additional Information) analysis."""
    cik: int
    filing_date: str
    accession_no: str
    commissions: List[SAICommission]
    pm_compensation: Optional[SAIPMCompensation]
    soft_dollar_info: Optional[SAISoftDollar]
    conflict_flags: List[str]


@app.get("/api/sai/{ticker}", response_model=SAIAnalysis)
def analyze_sai(ticker: str):
    """Pull SAI (Statement of Additional Information) data for a fund.

    Returns brokerage commission history, PM compensation structure,
    and soft dollar arrangement details from the fund's 485BPOS filing.
    """
    ticker = ticker.strip().upper()
    if not ticker or not ticker.isalpha() or len(ticker) > 6:
        raise HTTPException(400, "Invalid ticker format")

    try:
        from fundautopsy.core.fund import identify_fund
        from fundautopsy.data.sai_parser import parse_sai_for_cik

        fund = identify_fund(ticker)
        result = parse_sai_for_cik(fund.cik)

        if result is None or not result.has_data:
            raise HTTPException(404, f"No SAI data found for {ticker} (CIK {fund.cik})")

        # Build conflict flags
        flags = []
        if result.pm_compensation:
            pm = result.pm_compensation
            if pm.compensation_not_linked_to_fund_performance:
                flags.append("PM compensation is NOT linked to fund performance")
            if pm.bonus_linked_to_aum and not pm.bonus_linked_to_performance:
                flags.append("PM bonus tied to assets under management, not returns")
            if not pm.has_equity_ownership:
                flags.append("PM has no equity ownership in the fund or advisory firm")

        if result.soft_dollar_info:
            sd = result.soft_dollar_info
            if sd.has_soft_dollar_arrangements:
                flags.append("Fund uses soft dollar arrangements (inflated commissions for 'free' research)")
            if sd.uses_commission_sharing:
                flags.append("Fund uses commission sharing / unbundling program")

        # Build response
        commissions = [
            SAICommission(
                fund_name=bc.fund_name,
                annual_commissions=bc.annual_commissions,
            )
            for bc in result.commissions
        ]

        pm_comp = None
        if result.pm_compensation:
            pm = result.pm_compensation
            pm_comp = SAIPMCompensation(
                has_base_salary=pm.has_base_salary,
                has_bonus=pm.has_bonus,
                has_equity_ownership=pm.has_equity_ownership,
                has_deferred_comp=pm.has_deferred_comp,
                bonus_linked_to_performance=pm.bonus_linked_to_performance,
                bonus_linked_to_aum=pm.bonus_linked_to_aum,
                bonus_linked_to_firm_profit=pm.bonus_linked_to_firm_profit,
                compensation_not_linked_to_fund_performance=pm.compensation_not_linked_to_fund_performance,
                description=pm.description,
            )

        sd_info = None
        if result.soft_dollar_info:
            sd = result.soft_dollar_info
            sd_info = SAISoftDollar(
                has_soft_dollar_arrangements=sd.has_soft_dollar_arrangements,
                uses_commission_sharing=sd.uses_commission_sharing,
                description=sd.description,
            )

        return SAIAnalysis(
            cik=result.cik,
            filing_date=result.filing_date,
            accession_no=result.accession_no,
            commissions=commissions,
            pm_compensation=pm_comp,
            soft_dollar_info=sd_info,
            conflict_flags=flags,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("SAI analysis failed for %s", ticker)
        raise HTTPException(500, "SAI analysis failed due to an internal error")


@app.get("/api/compare")
def compare_funds(tickers: str):
    """Compare up to 5 funds side by side."""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if len(ticker_list) < 2:
        raise HTTPException(400, "Provide at least 2 tickers separated by commas")
    if len(ticker_list) > 5:
        raise HTTPException(400, "Maximum 5 funds for comparison")

    results = []
    errors = []
    for t in ticker_list:
        try:
            result = analyze_fund(t)
            results.append(result)
        except HTTPException as e:
            errors.append({"ticker": t, "error": e.detail})

    return {"results": results, "errors": errors}


@app.get("/api/leaderboard")
def leaderboard(sort_by: str = "hidden_cost_mid_bps", limit: int = 25):
    """Return the Worst Offender leaderboard."""
    entries = get_leaderboard(sort_by=sort_by, limit=limit)
    stats = get_leaderboard_stats()
    return {"entries": entries, "stats": stats}


@app.get("/api/fee-history/{ticker}")
def fee_history(ticker: str):
    """Return fee change history from historical 485BPOS filings."""
    ticker = ticker.strip().upper()
    if not ticker or not ticker.isalpha() or len(ticker) > 6:
        raise HTTPException(400, "Invalid ticker format")

    try:
        from fundautopsy.core.fund import identify_fund

        fund = identify_fund(ticker)
        history = track_fee_changes(cik=fund.cik, ticker=ticker, max_filings=5)

        snapshots = [
            {
                "filing_date": s.filing_date,
                "form_type": s.form_type,
                "management_fee": s.management_fee,
                "twelve_b1_fee": s.twelve_b1_fee,
                "other_expenses": s.other_expenses,
                "total_annual_expenses": s.total_annual_expenses,
                "net_expenses": s.net_expenses,
                "effective_expense_ratio": s.effective_expense_ratio,
                "max_sales_load": s.max_sales_load,
                "portfolio_turnover": s.portfolio_turnover,
            }
            for s in history.snapshots
        ]

        changes = [
            {
                "field_label": c.field_label,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "change_bps": c.change_bps,
                "direction": c.direction,
                "old_filing_date": c.old_filing_date,
                "new_filing_date": c.new_filing_date,
            }
            for c in history.changes
        ]

        return {
            "ticker": ticker,
            "cik": fund.cik,
            "has_changes": history.has_changes,
            "net_change_bps": history.net_change_bps,
            "snapshots": snapshots,
            "changes": changes,
        }

    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("Fee history failed for %s", ticker)
        raise HTTPException(500, "Fee history failed due to an internal error")


@app.get("/api/ncsr/{ticker}")
def analyze_ncsr(ticker: str):
    """Pull N-CSR (shareholder report) data for a fund.

    Returns audited brokerage commission history, portfolio turnover
    from financial highlights, and board advisory contract approval text.
    """
    ticker = ticker.strip().upper()
    if not ticker or not ticker.isalpha() or len(ticker) > 6:
        raise HTTPException(400, "Invalid ticker format")

    try:
        from fundautopsy.core.fund import identify_fund

        fund = identify_fund(ticker)
        result = parse_ncsr_for_cik(fund.cik)

        if result is None or not result.has_data:
            raise HTTPException(
                404, f"No N-CSR data found for {ticker} (CIK {fund.cik})"
            )

        commissions = [
            {
                "fund_name": nc.fund_name,
                "annual_commissions": nc.annual_commissions,
                "research_commissions": nc.research_commissions,
                "recapture_amounts": nc.recapture_amounts,
            }
            for nc in result.commissions
        ]

        turnover = [
            {"fund_name": nt.fund_name, "annual_turnover": nt.annual_turnover}
            for nt in result.turnover
        ]

        return {
            "cik": result.cik,
            "filing_date": result.filing_date,
            "accession_no": result.accession_no,
            "is_annual": result.is_annual,
            "commissions": commissions,
            "turnover": turnover,
            "board_approval_text": result.board_approval_text[:2000]
            if result.board_approval_text
            else "",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("N-CSR analysis failed for %s", ticker)
        raise HTTPException(500, "N-CSR analysis failed due to an internal error")


@app.get("/health")
def health_check():
    """Basic health endpoint for load balancers and monitoring."""
    health = get_edgar_health()
    return {
        "status": "ok",
        "edgar": {
            "retries": health["retries"],
            "errors": health["errors"],
            "status": "degraded" if health["errors"] > 0 else "ok",
        },
    }


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the interactive dashboard."""
    from fundautopsy.web.frontend import DASHBOARD_HTML

    return DASHBOARD_HTML
