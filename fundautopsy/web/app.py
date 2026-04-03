"""Fund Autopsy web API — real-time fund cost analysis.

Run with: python -m fundautopsy.web
"""

from __future__ import annotations

import traceback
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from fundautopsy.models.filing_data import DataSourceTag

app = FastAPI(title="Fund Autopsy", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CostComponent(BaseModel):
    label: str
    value: str | None
    low: float | None = None
    high: float | None = None
    tag: str
    note: str | None = None


class FeeComponent(BaseModel):
    label: str
    pct: float | None
    bps: float | None


class AssetMix(BaseModel):
    category: str
    label: str
    color: str
    pct: float


class BrokerInfo(BaseModel):
    name: str
    commission: float
    is_affiliated: bool


class SecuritiesLendingInfo(BaseModel):
    is_lending: bool
    agent_name: str | None = None
    is_agent_affiliated: bool = False
    net_income: float | None = None
    avg_value_on_loan: float | None = None


class ServiceProviders(BaseModel):
    adviser: str | None = None
    administrator: str | None = None
    custodian: str | None = None
    transfer_agent: str | None = None
    auditor: str | None = None
    is_admin_affiliated: bool = False
    is_transfer_agent_affiliated: bool = False


class DollarImpact(BaseModel):
    investment: float
    horizon_years: int
    assumed_return_pct: float
    expense_ratio_only_cost: float | None
    true_cost_low: float | None
    true_cost_high: float | None
    hidden_cost_low: float | None
    hidden_cost_high: float | None
    final_value_er_only: float | None
    final_value_true_low: float | None
    final_value_true_high: float | None


class FundAnalysis(BaseModel):
    ticker: str
    name: str
    family: str
    share_class: str | None = None
    net_assets: float | None
    net_assets_display: str
    holdings_count: int
    period_end: str | None
    is_fund_of_funds: bool

    # Expense ratio from prospectus
    expense_ratio_pct: float | None = None
    expense_ratio_bps: float | None = None
    fee_breakdown: list[FeeComponent] = []
    portfolio_turnover: float | None = None
    max_sales_load: float | None = None

    # Hidden costs
    costs: list[CostComponent]
    total_hidden_low: float | None
    total_hidden_high: float | None

    # True total cost = ER + hidden
    true_cost_low_bps: float | None = None
    true_cost_high_bps: float | None = None
    true_cost_low_pct: float | None = None
    true_cost_high_pct: float | None = None

    # Dollar impact
    dollar_impact: DollarImpact | None = None

    # N-CEN supplementary data
    top_brokers: list[BrokerInfo] = []
    affiliated_brokers: list[BrokerInfo] = []
    securities_lending: SecuritiesLendingInfo | None = None
    service_providers: ServiceProviders | None = None
    aggregate_commission_dollars: float | None = None

    asset_mix: list[AssetMix]
    conflict_flags: list[str] = []
    data_notes: list[str]
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
    expense_ratio_pct: float | None,
    hidden_low_bps: float | None,
    hidden_high_bps: float | None,
    investment: float = 100_000,
    horizon: int = 20,
    annual_return: float = 7.0,
) -> DollarImpact:
    """Compute dollar cost of fees over time using compound drag."""
    gross_return = annual_return / 100

    # ER-only scenario
    er_only_cost = None
    final_er_only = None
    if expense_ratio_pct is not None:
        er_drag = expense_ratio_pct / 100
        final_er_only = investment * ((1 + gross_return - er_drag) ** horizon)
        no_cost_final = investment * ((1 + gross_return) ** horizon)
        er_only_cost = no_cost_final - final_er_only

    # True cost scenarios
    true_low = None
    true_high = None
    hidden_low = None
    hidden_high = None
    final_true_low = None
    final_true_high = None

    no_cost_final = investment * ((1 + gross_return) ** horizon)

    if expense_ratio_pct is not None and hidden_low_bps is not None:
        true_drag_low = (expense_ratio_pct + hidden_low_bps / 100) / 100
        true_drag_high = (expense_ratio_pct + hidden_high_bps / 100) / 100
        final_true_low = investment * ((1 + gross_return - true_drag_high) ** horizon)
        final_true_high = investment * ((1 + gross_return - true_drag_low) ** horizon)
        true_low = no_cost_final - final_true_high
        true_high = no_cost_final - final_true_low
        if er_only_cost is not None:
            hidden_low = true_low - er_only_cost
            hidden_high = true_high - er_only_cost

    return DollarImpact(
        investment=investment,
        horizon_years=horizon,
        assumed_return_pct=annual_return,
        expense_ratio_only_cost=round(er_only_cost) if er_only_cost else None,
        true_cost_low=round(true_low) if true_low else None,
        true_cost_high=round(true_high) if true_high else None,
        hidden_cost_low=round(hidden_low) if hidden_low else None,
        hidden_cost_high=round(hidden_high) if hidden_high else None,
        final_value_er_only=round(final_er_only) if final_er_only else None,
        final_value_true_low=round(final_true_low) if final_true_low else None,
        final_value_true_high=round(final_true_high) if final_true_high else None,
    )


@app.get("/api/analyze/{ticker}", response_model=FundAnalysis)
def analyze_fund(ticker: str):
    """Run the full Fund Autopsy pipeline on a ticker and return structured results."""
    ticker = ticker.strip().upper()
    if not ticker.isalpha() or len(ticker) > 6:
        raise HTTPException(400, "Invalid ticker format")

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
        except Exception:
            pass

        tree = compute_costs(tree)
        tree = rollup_costs(tree)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Analysis failed: {e}")

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
    total_hidden_low = sum(
        c.low for c in costs if c.low is not None and c.tag != "warning"
    )
    total_hidden_high = sum(
        c.high for c in costs if c.high is not None and c.tag != "warning"
    )

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
            agg = ncen_full.aggregate_commission or 1
            aff_pct = (aff_total / agg * 100) if agg > 0 else 0
            conflict_flags.append(
                f"Affiliated broker usage: {len(ncen_full.affiliated_brokers)} affiliated broker(s), "
                f"${aff_total:,.0f} in commissions ({aff_pct:.1f}% of total)"
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
        total_hidden_low=round(total_hidden_low, 2) if total_hidden_low else None,
        total_hidden_high=round(total_hidden_high, 2) if total_hidden_high else None,
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
        generated=str(date.today()),
    )


class SAICommission(BaseModel):
    fund_name: str
    annual_commissions: dict[int, float]


class SAIPMCompensation(BaseModel):
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
    has_soft_dollar_arrangements: bool
    uses_commission_sharing: bool
    description: str


class SAIAnalysis(BaseModel):
    cik: int
    filing_date: str
    accession_no: str
    commissions: list[SAICommission]
    pm_compensation: SAIPMCompensation | None
    soft_dollar_info: SAISoftDollar | None
    conflict_flags: list[str]


@app.get("/api/sai/{ticker}", response_model=SAIAnalysis)
def analyze_sai(ticker: str):
    """Pull SAI (Statement of Additional Information) data for a fund.

    Returns brokerage commission history, PM compensation structure,
    and soft dollar arrangement details from the fund's 485BPOS filing.
    """
    ticker = ticker.strip().upper()
    if not ticker.isalpha() or len(ticker) > 6:
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
        traceback.print_exc()
        raise HTTPException(500, f"SAI analysis failed: {e}")


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


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the interactive dashboard."""
    from fundautopsy.web.frontend import DASHBOARD_HTML

    return DASHBOARD_HTML
