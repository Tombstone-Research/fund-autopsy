"""SEC filing schema monitoring agent.

Periodically fetches sample filings from EDGAR and validates that the XML/HTML
structure matches what our parsers expect. If the SEC changes their filing
format, this catches it before users hit silent data loss.

Checks:
  1. N-CEN XML: expected element paths for brokerage commissions, soft dollars,
     service providers, securities lending
  2. N-PORT XML: expected element paths for holdings, asset categories, values
  3. 497K HTML: expected table structure for fee tables
  4. EDGAR API: submissions endpoint response shape

Each check returns a SchemaCheckResult with pass/fail and details.
"""

from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from datetime import datetime

import defusedxml.ElementTree as ElementTree

logger = logging.getLogger(__name__)

# Known-good test CIKs and filings for validation
# American Funds Growth Fund of America — large, stable, always files on time
# Verified 2026-04-20 via MF tickers feed: AGTHX -> CIK 44201
TEST_CIK = 44201
TEST_TICKER = "AGTHX"


@dataclass
class SchemaCheckResult:
    """Result of a single schema validation check."""

    check_name: str
    passed: bool = False
    details: str = ""
    missing_elements: list[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class MonitorReport:
    """Full monitoring report across all checks."""

    checks: list[SchemaCheckResult] = field(default_factory=list)
    all_passed: bool = True
    run_timestamp: str = ""
    summary: str = ""

    def __post_init__(self):
        if not self.run_timestamp:
            self.run_timestamp = datetime.utcnow().isoformat()


# --- Expected XML paths for N-CEN ---
# These mirror elements the production parser in fundautopsy/data/ncen.py
# actually consumes. Adding any path here is a real commitment that the parser
# depends on it — if the path goes missing, the parser breaks for real.
NCEN_EXPECTED_PATHS = [
    # Report header
    ".//headerData",
    # Per-series question block (parser loops over these)
    ".//managementInvestmentQuestion",
    ".//mgmtInvSeriesId",
    # Brokerage commissions
    ".//aggregateCommission",
    # Broker records (affiliated + non-affiliated)
    ".//brokerDealer",
    ".//broker",
    # Service providers
    ".//investmentAdviser",
    ".//admin",
    ".//transferAgent",
    ".//custodian",
    # Securities lending flag
    ".//isFundSecuritiesLending",
]
# NOTE: reportCalendarOrQuarter was removed from NCEN_EXPECTED_PATHS on
# 2026-04-21 because the production parser falls back to filing_date from the
# EDGAR submissions list when the element is absent. Verified absent in live
# X0505-era filings (e.g. 0001193125-25-282335).

# --- Expected XML paths for N-PORT ---
NPORT_EXPECTED_PATHS = [
    ".//invstOrSec",         # Individual holdings
    ".//name",               # Holding name
    ".//valUSD",             # USD value
    ".//assetCat",           # Asset category code
    ".//totAssets",          # Total net assets
    ".//repPdEnd",           # Reporting period end
]

# --- Expected EDGAR submissions API fields ---
SUBMISSIONS_EXPECTED_KEYS = [
    "cik", "name", "filings",
]
SUBMISSIONS_FILINGS_KEYS = [
    "recent",
]
SUBMISSIONS_RECENT_KEYS = [
    "form", "filingDate", "accessionNumber", "primaryDocument",
]


def check_edgar_api_schema() -> SchemaCheckResult:
    """Validate EDGAR submissions API response structure."""
    from fundautopsy.data.edgar import EDGAR_SUBMISSIONS_URL, _request_with_retry, get_edgar_client

    check = SchemaCheckResult(check_name="EDGAR Submissions API")
    try:
        client = get_edgar_client()
        cik_padded = str(TEST_CIK).zfill(10)
        resp = _request_with_retry(client, "GET", f"{EDGAR_SUBMISSIONS_URL}/CIK{cik_padded}.json")
        data = resp.json()
        client.close()

        missing = []
        for key in SUBMISSIONS_EXPECTED_KEYS:
            if key not in data:
                missing.append(f"top-level.{key}")

        filings = data.get("filings", {})
        for key in SUBMISSIONS_FILINGS_KEYS:
            if key not in filings:
                missing.append(f"filings.{key}")

        recent = filings.get("recent", {})
        for key in SUBMISSIONS_RECENT_KEYS:
            if key not in recent:
                missing.append(f"filings.recent.{key}")

        if missing:
            check.passed = False
            check.missing_elements = missing
            check.details = f"Missing {len(missing)} expected field(s) in submissions API"
        else:
            check.passed = True
            check.details = "All expected fields present"

    except Exception as exc:
        check.passed = False
        check.details = f"API request failed: {exc}"

    return check


def _download_with_xml_fallback(cik, accession_number, raw_doc, client):
    """Download a filing's raw XML, falling back to bare primary_doc.xml when
    the EDGAR API returns an xslForm path (which resolves to rendered HTML,
    not XML). Mirrors the parser fallback in fundautopsy/data/ncen.py and
    fundautopsy/data/nport.py.
    """
    from fundautopsy.data.edgar import download_filing_xml

    doc_candidates = ["primary_doc.xml"]
    raw_doc = raw_doc or ""
    if raw_doc and "/" not in raw_doc and raw_doc != "primary_doc.xml":
        doc_candidates.insert(0, raw_doc)

    for doc_name in doc_candidates:
        try:
            xml_bytes = download_filing_xml(
                cik=cik,
                accession_number=accession_number,
                primary_document=doc_name,
                client=client,
            )
            if xml_bytes and xml_bytes[:100].lower().find(b"<html") == -1:
                return xml_bytes
        except Exception as exc:
            logger.debug(
                "schema monitor download failed %s/%s: %s",
                accession_number, doc_name, exc,
            )
            continue
    return None


def check_ncen_schema() -> SchemaCheckResult:
    """Validate N-CEN XML structure against expected element paths."""
    from fundautopsy.data.edgar import get_edgar_client, get_filings

    check = SchemaCheckResult(check_name="N-CEN XML Schema")
    try:
        client = get_edgar_client()
        filings = get_filings(TEST_CIK, "N-CEN", client=client, count=1)
        if not filings:
            check.passed = False
            check.details = "No N-CEN filings found for test CIK"
            client.close()
            return check

        filing = filings[0]
        xml_bytes = _download_with_xml_fallback(
            TEST_CIK, filing.accession_number, filing.primary_document, client
        )
        client.close()

        if not xml_bytes:
            check.passed = False
            check.details = (
                f"Could not download raw N-CEN XML for {filing.accession_number}. "
                "Both primary_document and bare primary_doc.xml returned HTML or failed."
            )
            return check

        root = ElementTree.fromstring(xml_bytes)

        # N-CEN uses namespaces; try both with and without
        missing = []
        for path in NCEN_EXPECTED_PATHS:
            # Try plain path first
            found = root.find(path)
            if found is None:
                # Try with wildcard namespace
                ns_path = path.replace("//", "//{*}")
                found = root.find(ns_path)
            if found is None:
                missing.append(path)

        if missing:
            check.passed = False
            check.missing_elements = missing
            check.details = (
                f"Missing {len(missing)}/{len(NCEN_EXPECTED_PATHS)} expected elements. "
                f"Filing: {filing.accession_number} ({filing.filing_date})"
            )
        else:
            check.passed = True
            check.details = f"All elements present. Filing: {filing.accession_number} ({filing.filing_date})"

    except Exception as exc:
        check.passed = False
        check.details = f"N-CEN check failed: {exc}"

    return check


def check_nport_schema() -> SchemaCheckResult:
    """Validate N-PORT XML structure against expected element paths."""
    from fundautopsy.data.edgar import get_edgar_client, get_filings

    check = SchemaCheckResult(check_name="N-PORT XML Schema")
    try:
        client = get_edgar_client()
        filings = get_filings(TEST_CIK, "NPORT-P", client=client, count=1)
        if not filings:
            check.passed = False
            check.details = "No NPORT-P filings found for test CIK"
            client.close()
            return check

        filing = filings[0]
        xml_bytes = _download_with_xml_fallback(
            TEST_CIK, filing.accession_number, filing.primary_document, client
        )
        client.close()

        if not xml_bytes:
            check.passed = False
            check.details = (
                f"Could not download raw N-PORT XML for {filing.accession_number}. "
                "Both primary_document and bare primary_doc.xml returned HTML or failed."
            )
            return check

        root = ElementTree.fromstring(xml_bytes)

        missing = []
        for path in NPORT_EXPECTED_PATHS:
            found = root.find(path)
            if found is None:
                ns_path = path.replace("//", "//{*}")
                found = root.find(ns_path)
            if found is None:
                missing.append(path)

        if missing:
            check.passed = False
            check.missing_elements = missing
            check.details = (
                f"Missing {len(missing)}/{len(NPORT_EXPECTED_PATHS)} expected elements. "
                f"Filing: {filing.accession_number} ({filing.filing_date})"
            )
        else:
            check.passed = True
            check.details = f"All elements present. Filing: {filing.accession_number} ({filing.filing_date})"

    except Exception as exc:
        check.passed = False
        check.details = f"N-PORT check failed: {exc}"

    return check


def check_mf_tickers_api() -> SchemaCheckResult:
    """Validate mutual fund tickers API still returns expected structure."""
    from fundautopsy.data.edgar import EDGAR_MF_TICKERS_URL, _request_with_retry, get_edgar_client

    check = SchemaCheckResult(check_name="MF Tickers API")
    try:
        client = get_edgar_client()
        resp = _request_with_retry(client, "GET", EDGAR_MF_TICKERS_URL)
        data = resp.json()
        client.close()

        missing = []
        if "fields" not in data:
            missing.append("fields")
        if "data" not in data:
            missing.append("data")

        if not missing:
            fields = data["fields"]
            expected_fields = ["cik", "seriesId", "classId", "symbol"]
            for ef in expected_fields:
                if ef not in [f.lower() for f in fields]:
                    # Case-insensitive check
                    found = any(f.lower() == ef.lower() for f in fields)
                    if not found:
                        missing.append(f"fields.{ef}")

            # Verify we can find our test ticker
            ticker_found = False
            for row in data.get("data", [])[:50000]:
                if len(row) >= 4 and row[3] and row[3].upper() == TEST_TICKER:
                    ticker_found = True
                    break

            if not ticker_found:
                missing.append(f"test ticker {TEST_TICKER} not found in data")

        if missing:
            check.passed = False
            check.missing_elements = missing
            check.details = f"Missing {len(missing)} expected element(s)"
        else:
            check.passed = True
            check.details = f"API structure intact, test ticker {TEST_TICKER} resolved"

    except Exception as exc:
        check.passed = False
        check.details = f"MF tickers check failed: {exc}"

    return check


def run_all_checks() -> MonitorReport:
    """Run all schema validation checks and produce a report."""
    report = MonitorReport()

    checks = [
        check_edgar_api_schema,
        check_mf_tickers_api,
        check_ncen_schema,
        check_nport_schema,
    ]

    for check_fn in checks:
        logger.info("Running check: %s", check_fn.__name__)
        result = check_fn()
        report.checks.append(result)
        if not result.passed:
            report.all_passed = False
        logger.info("  %s: %s", "PASS" if result.passed else "FAIL", result.details)

    # Build summary
    passed = sum(1 for c in report.checks if c.passed)
    total = len(report.checks)
    report.summary = f"{passed}/{total} checks passed"

    if not report.all_passed:
        failed = [c for c in report.checks if not c.passed]
        report.summary += ". FAILURES: " + ", ".join(
            f"{c.check_name} ({len(c.missing_elements)} missing)" for c in failed
        )

    return report


def format_report(report: MonitorReport) -> str:
    """Format a monitoring report as human-readable text."""
    lines = [
        f"SEC Schema Monitor — {report.run_timestamp}",
        f"Status: {'ALL PASSED' if report.all_passed else 'FAILURES DETECTED'}",
        f"Summary: {report.summary}",
        "",
    ]

    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        lines.append(f"[{status}] {check.check_name}")
        lines.append(f"       {check.details}")
        if check.missing_elements:
            for elem in check.missing_elements:
                lines.append(f"       - MISSING: {elem}")
        lines.append("")

    return "\n".join(lines)


def format_markdown_report(report: MonitorReport) -> str:
    """Format a monitoring report as a dated markdown file.

    Emits consistent `**Result:** PASS` / `**Result:** FAIL` markers that
    the autopilot parser can count.
    """
    passed = sum(1 for c in report.checks if c.passed)
    total = len(report.checks)
    lines = [
        f"# SEC Schema Monitor — Run Report",
        "",
        f"**Run timestamp:** {report.run_timestamp}",
        f"**Overall:** {'PASS' if report.all_passed else 'FAIL'} ({passed}/{total} checks pass)",
        f"**Summary:** {report.summary}",
        "",
        "---",
        "",
    ]
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        lines.append(f"## {check.check_name}")
        lines.append("")
        lines.append(f"**Result:** {status}")
        lines.append("")
        lines.append(check.details)
        if check.missing_elements:
            lines.append("")
            lines.append("Missing elements:")
            for elem in check.missing_elements:
                lines.append(f"- `{elem}`")
        lines.append("")
    return "\n".join(lines)


def write_dated_markdown(report: MonitorReport, reports_dir: pathlib.Path) -> pathlib.Path:
    """Persist the markdown report to the dated reports directory."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    # run_timestamp looks like "2026-04-21 14:33:10" or similar — take date only
    date_part = report.run_timestamp.split()[0] if " " in report.run_timestamp else report.run_timestamp[:10]
    out_path = reports_dir / f"{date_part}_schema_monitor_run.md"
    out_path.write_text(format_markdown_report(report))
    latest_path = reports_dir / "latest_run.txt"
    latest_path.write_text(out_path.name)
    return out_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    report = run_all_checks()
    print(format_report(report))

    # Also persist the markdown artifact the autopilot report aggregates.
    reports_dir = pathlib.Path(__file__).resolve().parent / "reports"
    path = write_dated_markdown(report, reports_dir)
    print(f"\nWrote: {path}")
