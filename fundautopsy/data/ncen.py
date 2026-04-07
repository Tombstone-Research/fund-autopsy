"""N-CEN filing parser — brokerage commissions, soft dollar data, and more.

Parses SEC Form N-CEN XML filings to extract:
- Brokerage commission totals and soft dollar arrangements
- Securities lending income and agent fees
- Affiliated broker-dealer commissions
- Principal transaction volumes
- Line of credit details
- Service provider information

XML namespace: http://www.sec.gov/edgar/ncen
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import httpx
from defusedxml.lxml import fromstring as _safe_fromstring
from lxml import etree

from fundautopsy.models.filing_data import NCENData, DataSourceTag, TaggedValue

logger = logging.getLogger(__name__)
from fundautopsy.data.edgar import (
    MutualFundIdentifier,
    get_edgar_client,
    get_filings,
    download_filing_xml,
)

NCEN_NS = {"n": "http://www.sec.gov/edgar/ncen"}


@dataclass
class BrokerRecord:
    """A single broker from the N-CEN brokers list."""

    name: str
    gross_commission: float
    file_no: str = ""
    crd_no: str = ""
    lei: str = ""
    is_affiliated: bool = False


@dataclass
class PrincipalTransaction:
    """A principal transaction counterparty."""

    name: str
    total_purchase_sale: float
    file_no: str = ""
    lei: str = ""


@dataclass
class SecuritiesLendingData:
    """Securities lending details from N-CEN."""

    is_lending: bool = False
    agent_name: str = ""
    agent_lei: str = ""
    is_agent_affiliated: bool = False
    avg_portfolio_value_on_loan: Optional[float] = None
    net_income: Optional[float] = None
    payment_type: str = ""


@dataclass
class LineOfCreditData:
    """Line of credit details."""

    has_line_of_credit: bool = False
    is_interfund_lending: bool = False
    is_interfund_borrowing: bool = False


@dataclass
class NCENFullData:
    """Complete parsed N-CEN data beyond what the base NCENData model captures."""

    # Core identifiers
    fund_name: str = ""
    series_id: str = ""
    lei: str = ""
    filing_date: Optional[date] = None
    reporting_period_end: Optional[date] = None

    # Brokerage commissions
    aggregate_commission: Optional[float] = None
    is_brokerage_research_payment: bool = False  # soft dollar flag
    monthly_avg_net_assets: Optional[float] = None

    # Broker details
    affiliated_brokers: list[BrokerRecord] = field(default_factory=list)
    top_brokers: list[BrokerRecord] = field(default_factory=list)

    # Principal transactions
    principal_transactions: list[PrincipalTransaction] = field(default_factory=list)
    principal_aggregate_purchase: Optional[float] = None

    # Securities lending
    securities_lending: Optional[SecuritiesLendingData] = None

    # Line of credit
    line_of_credit: Optional[LineOfCreditData] = None

    # Service providers
    investment_adviser: str = ""
    administrator: str = ""
    is_admin_affiliated: bool = False
    custodian_primary: str = ""
    transfer_agent: str = ""
    is_transfer_agent_affiliated: bool = False
    auditor: str = ""

    # Fund characteristics
    is_non_diversified: bool = False
    is_swing_pricing: bool = False
    fund_type: str = ""

    def to_ncen_data(self) -> NCENData:
        """Convert to the base NCENData model for cost computation."""
        total_commissions = TaggedValue(
            value=self.aggregate_commission,
            tag=DataSourceTag.REPORTED if self.aggregate_commission is not None else DataSourceTag.UNAVAILABLE,
            source_filing=f"N-CEN {self.filing_date}" if self.filing_date else None,
        )

        # N-CEN XML doesn't separate soft dollar $ amount directly in the same way
        # as the form instructions suggest. The isBrokerageResearchPayment flag (Y/N)
        # tells us soft dollars exist, but the actual $ breakdown is in the
        # aggregate commission and broker-level data.
        # For now, flag the soft dollar arrangement and note that detailed $ amounts
        # may require SAI cross-reference for granular breakdowns.
        soft_dollar_commissions = TaggedValue(
            value=None,
            tag=DataSourceTag.NOT_DISCLOSED if self.is_brokerage_research_payment else DataSourceTag.UNAVAILABLE,
            note="N-CEN flags soft dollar arrangements but individual filing XML may not separate the dollar amount. Cross-reference SAI for granular breakdown.",
        )

        net_assets = TaggedValue(
            value=self.monthly_avg_net_assets,
            tag=DataSourceTag.REPORTED if self.monthly_avg_net_assets is not None else DataSourceTag.UNAVAILABLE,
            source_filing=f"N-CEN {self.filing_date}" if self.filing_date else None,
        )

        return NCENData(
            filing_date=self.filing_date or date.today(),
            reporting_period_end=self.reporting_period_end or date.today(),
            series_id=self.series_id,
            has_soft_dollar_arrangements=self.is_brokerage_research_payment,
            total_brokerage_commissions=total_commissions,
            soft_dollar_commissions=soft_dollar_commissions,
            total_net_assets=net_assets,
        )


def retrieve_ncen(
    fund_id: MutualFundIdentifier,
) -> Optional[NCENFullData]:
    """Retrieve and parse the most recent N-CEN filing for a fund.

    Args:
        fund_id: Resolved fund identifier with CIK and series ID.

    Returns:
        Parsed NCENFullData, or None if no filing found.
    """
    client = get_edgar_client()
    try:
        # N-CEN is usually filed per trust with ALL series in one filing.
        # However, some large families (Fidelity) file separate N-CENs
        # per series or per batch. We need enough filings to find ours.
        filings = get_filings(fund_id.cik, "N-CEN", client=client, count=30)
        if not filings:
            return None

        for filing in filings:
            doc_candidates = ["primary_doc.xml"]
            raw_doc = filing.primary_document or ""
            if raw_doc and "/" not in raw_doc and raw_doc != "primary_doc.xml":
                doc_candidates.insert(0, raw_doc)

            xml_bytes = None
            for doc_name in doc_candidates:
                try:
                    xml_bytes = download_filing_xml(
                        cik=fund_id.cik,
                        accession_number=filing.accession_number,
                        primary_document=doc_name,
                        client=client,
                    )
                    if xml_bytes and xml_bytes[:100].lower().find(b'<html') == -1:
                        break
                    xml_bytes = None
                except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                    logger.debug(
                        "N-CEN download failed for %s/%s: %s",
                        filing.accession_number, doc_name, exc,
                    )
                    continue

            if not xml_bytes:
                continue

            result = parse_ncen_xml(xml_bytes, fund_id.series_id)
            if result:
                result.filing_date = date.fromisoformat(filing.filing_date)
                return result

        return None
    finally:
        client.close()


def parse_ncen_xml(xml_content: bytes, target_series_id: str) -> Optional[NCENFullData]:
    """Parse raw N-CEN XML content for a specific series.

    The N-CEN XML structure (namespace: http://www.sec.gov/edgar/ncen):
      edgarSubmission
        headerData
        formData
          generalInfo
          registrantInfo
          managementInvestmentQuestionSeriesInfo
            managementInvestmentQuestion  <-- per-series data
          ...

    For multi-series trusts, we match on mgmtInvSeriesId.
    For single-series trusts, we take the only series available.

    Args:
        xml_content: Raw XML bytes from EDGAR.
        target_series_id: Series ID to match (e.g., "S000009228").

    Returns:
        Parsed NCENFullData for the target series, or None.
    """
    try:
        root = _safe_fromstring(xml_content)
    except etree.XMLSyntaxError:
        return None

    # Find the header for reporting period
    header = root.find(".//n:headerData", NCEN_NS)
    period_end = None
    if header is not None:
        pe = header.findtext(".//n:reportCalendarOrQuarter", namespaces=NCEN_NS)
        if pe:
            try:
                period_end = date.fromisoformat(pe)
            except ValueError:
                pass

    # Find all managementInvestmentQuestion sections (one per series)
    series_sections = root.findall(
        ".//n:managementInvestmentQuestion", NCEN_NS
    )

    if not series_sections:
        return None

    # Match target series or take only available
    target_section = None
    for section in series_sections:
        sid = _text(section, "mgmtInvSeriesId")
        if sid == target_series_id:
            target_section = section
            break

    if target_section is None:
        # If single series and its ID matches (or has no ID), use it.
        # Do NOT blindly accept a single-series filing — some families
        # (Fidelity) file separate N-CENs per series, so the single
        # section might be a completely different fund.
        if len(series_sections) == 1:
            sid = _text(series_sections[0], "mgmtInvSeriesId")
            if not sid or sid == target_series_id:
                target_section = series_sections[0]
            else:
                return None
        else:
            return None

    return _parse_series_section(target_section, period_end)


def _parse_series_section(
    section: etree._Element, period_end: Optional[date]
) -> NCENFullData:
    """Parse a single managementInvestmentQuestion section."""
    result = NCENFullData()
    result.reporting_period_end = period_end

    # Core identifiers
    result.fund_name = _text(section, "mgmtInvFundName")
    result.series_id = _text(section, "mgmtInvSeriesId")
    result.lei = _text(section, "mgmtInvLei")

    # Brokerage commissions
    result.aggregate_commission = _float(section, "aggregateCommission")
    result.is_brokerage_research_payment = _text(section, "isBrokerageResearchPayment") == "Y"
    result.monthly_avg_net_assets = _float(section, "mnthlyAvgNetAssets")

    # Fund characteristics
    result.is_non_diversified = _text(section, "isNonDiversifiedCompany") == "Y"
    result.is_swing_pricing = _text(section, "isSwingPricing") == "Y"
    result.fund_type = _text(section, "fundType")

    # Affiliated broker-dealers
    for bd in section.findall(".//n:brokerDealer", NCEN_NS):
        name = _text(bd, "brokerDealerName")
        commission = _float(bd, "brokerDealerCommission") or 0.0
        if name:
            result.affiliated_brokers.append(BrokerRecord(
                name=name.strip(),
                gross_commission=commission,
                file_no=_text(bd, "brokerDealerFileNo"),
                crd_no=_text(bd, "brokerDealerCrdNo"),
                lei=_text(bd, "brokerDealerLei"),
                is_affiliated=True,
            ))

    # Top non-affiliated brokers
    for b in section.findall(".//n:broker", NCEN_NS):
        name = _text(b, "brokerName")
        commission = _float(b, "grossCommission") or 0.0
        if name:
            result.top_brokers.append(BrokerRecord(
                name=name.strip(),
                gross_commission=commission,
                file_no=_text(b, "brokerFileNo"),
                crd_no=_text(b, "brokerCrdNo"),
                lei=_text(b, "brokerLei"),
                is_affiliated=False,
            ))

    # Principal transactions
    for pt in section.findall(".//n:principalTransaction", NCEN_NS):
        name = _text(pt, "principalName")
        amount = _float(pt, "principalTotalPurchaseSale") or 0.0
        if name:
            result.principal_transactions.append(PrincipalTransaction(
                name=name.strip(),
                total_purchase_sale=amount,
                file_no=_text(pt, "principalFileNo"),
                lei=_text(pt, "principalLei"),
            ))
    result.principal_aggregate_purchase = _float(section, "principalAggregatePurchase")

    # Securities lending
    is_lending = _text(section, "isFundSecuritiesLending") == "Y"
    if is_lending:
        sl = SecuritiesLendingData(is_lending=True)
        sl_elem = section.find(".//n:securityLending", NCEN_NS)
        if sl_elem is not None:
            sl.agent_name = _text(sl_elem, "securitiesAgentName")
            sl.agent_lei = _text(sl_elem, "securitiesAgentLei")
            sl.is_agent_affiliated = _text(sl_elem, "isSecuritiesAgentAffiliated") == "Y"
        sl.avg_portfolio_value_on_loan = _float(section, "avgPortfolioSecuritiesValue")
        sl.net_income = _float(section, "netIncomeSecuritiesLending")

        # Payment type
        ptype = section.find(".//n:paymentToAgentManagerType", NCEN_NS)
        if ptype is not None and ptype.text:
            sl.payment_type = ptype.text.strip()
        result.securities_lending = sl
    else:
        result.securities_lending = SecuritiesLendingData(is_lending=False)

    # Line of credit
    loc = LineOfCreditData()
    loc.has_line_of_credit = section.find(".//n:lineOfCreditDetails", NCEN_NS) is not None
    loc.is_interfund_lending = _text(section, "isInterfundLending") == "Y"
    loc.is_interfund_borrowing = _text(section, "isInterfundBorrowing") == "Y"
    result.line_of_credit = loc

    # Service providers
    adv = section.find(".//n:investmentAdviser", NCEN_NS)
    if adv is not None:
        result.investment_adviser = _text(adv, "investmentAdviserName")

    admin = section.find(".//n:admin", NCEN_NS)
    if admin is not None:
        result.administrator = _text(admin, "adminName")
        result.is_admin_affiliated = _text(admin, "isAdminAffiliated") == "Y"

    ta = section.find(".//n:transferAgent", NCEN_NS)
    if ta is not None:
        result.transfer_agent = _text(ta, "transferAgentName")
        result.is_transfer_agent_affiliated = _text(ta, "isTransferAgentAffiliated") == "Y"

    cust = section.find(".//n:custodian", NCEN_NS)
    if cust is not None:
        result.custodian_primary = _text(cust, "custodianName")

    return result


def _text(elem: etree._Element, child_tag: str) -> str:
    """Get text content of a child element, or empty string."""
    child = elem.find(f"n:{child_tag}", NCEN_NS)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def _float(elem: etree._Element, child_tag: str) -> Optional[float]:
    """Get float value of a child element, or None."""
    text = _text(elem, child_tag)
    if text and text != "N/A":
        try:
            return float(text)
        except ValueError:
            return None
    return None
