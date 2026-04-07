"""Fee change tracker — 485A/485B/485C post-effective amendment parser.

Monitors prospectus amendments where funds quietly raise or lower fees
between annual reports. Builds a time-series of fee changes by parsing
sequential 485BPOS filings and comparing expense ratios.

Filing types:
  - 485APOS: Pre-effective amendment (proposed changes)
  - 485BPOS: Post-effective amendment (changes in effect)
  - 485BXT:  Extension for post-effective amendment

This module fetches multiple historical 485BPOS filings for a CIK and
extracts the fee table from each to detect changes over time.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

from fundautopsy.config import EDGAR_RATE_LIMIT_DELAY
from fundautopsy.data.fee_parser import parse_497k_html, ParsedFees


@dataclass
class FeeSnapshot:
    """A single point-in-time fee snapshot from a prospectus amendment."""
    filing_date: str
    accession_no: str
    form_type: str  # 485APOS, 485BPOS, 485BXT

    management_fee: Optional[float] = None
    twelve_b1_fee: Optional[float] = None
    other_expenses: Optional[float] = None
    total_annual_expenses: Optional[float] = None
    fee_waiver: Optional[float] = None
    net_expenses: Optional[float] = None
    max_sales_load: Optional[float] = None
    portfolio_turnover: Optional[float] = None

    @property
    def effective_expense_ratio(self) -> Optional[float]:
        """Net expense ratio (after waivers) or total if no waiver."""
        if self.net_expenses is not None:
            return self.net_expenses
        return self.total_annual_expenses


@dataclass
class FeeChange:
    """A detected fee change between two filing dates."""
    field_name: str  # e.g., "management_fee", "total_annual_expenses"
    field_label: str  # Human-readable label
    old_value: float
    new_value: float
    change_bps: float  # Change in basis points
    old_filing_date: str
    new_filing_date: str
    direction: str  # "increase" or "decrease"


@dataclass
class FeeHistory:
    """Complete fee change history for a fund."""
    ticker: str = ""
    cik: int = 0
    snapshots: list[FeeSnapshot] = field(default_factory=list)
    changes: list[FeeChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """True if any fee changes detected."""
        return len(self.changes) > 0

    @property
    def net_change_bps(self) -> float:
        """Net fee change across all detected changes."""
        return sum(c.change_bps for c in self.changes)


# ── EDGAR access ─────────────────────────────────────────────────────────────

def _fetch_edgar(url: str):
    """Fetch from EDGAR with rate limiting."""
    import httpx
    from fundautopsy.config import EDGAR_USER_AGENT

    time.sleep(EDGAR_RATE_LIMIT_DELAY)
    with httpx.Client(
        headers={
            "User-Agent": EDGAR_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        },
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        return client.get(url)


def _find_485_filings(cik: int, max_filings: int = 10) -> list[dict]:
    """Find historical 485BPOS filings for a CIK."""
    url = f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json"
    r = _fetch_edgar(url)
    if r.status_code != 200:
        return []

    data = r.json()
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])

    results = []
    for i, form in enumerate(forms):
        if form in ("485BPOS", "485APOS", "485BXT") and i < len(accessions):
            results.append({
                "accession_no": accessions[i],
                "filing_date": dates[i] if i < len(dates) else "",
                "primary_doc": primary_docs[i] if i < len(primary_docs) else "",
                "form_type": form,
                "cik": cik,
            })
            if len(results) >= max_filings:
                break

    return results


def _fetch_filing_html(cik: int, accession_no: str, primary_doc: str) -> Optional[str]:
    """Download a filing's HTML."""
    acc_nodash = accession_no.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{primary_doc}"
    r = _fetch_edgar(url)
    if r.status_code == 200:
        return r.text
    return None


# ── Fee comparison ───────────────────────────────────────────────────────────

_TRACKED_FIELDS = [
    ("management_fee", "Management Fee"),
    ("twelve_b1_fee", "12b-1 Fee"),
    ("other_expenses", "Other Expenses"),
    ("total_annual_expenses", "Total Annual Expenses"),
    ("net_expenses", "Net Expenses (After Waivers)"),
    ("max_sales_load", "Maximum Sales Load"),
]


def _compare_snapshots(old: FeeSnapshot, new: FeeSnapshot) -> list[FeeChange]:
    """Compare two fee snapshots and return detected changes."""
    changes = []

    for field_name, label in _TRACKED_FIELDS:
        old_val = getattr(old, field_name, None)
        new_val = getattr(new, field_name, None)

        if old_val is not None and new_val is not None:
            # Compare with a tolerance of 0.001% (0.1 bps) to avoid float noise
            diff = new_val - old_val
            if abs(diff) > 0.001:
                changes.append(FeeChange(
                    field_name=field_name,
                    field_label=label,
                    old_value=old_val,
                    new_value=new_val,
                    change_bps=round(diff * 100, 1),  # Convert % to bps
                    old_filing_date=old.filing_date,
                    new_filing_date=new.filing_date,
                    direction="increase" if diff > 0 else "decrease",
                ))

    return changes


# ── Main entry point ─────────────────────────────────────────────────────────

def track_fee_changes(
    cik: int,
    ticker: str,
    max_filings: int = 5,
) -> FeeHistory:
    """Track fee changes across historical prospectus amendments.

    Fetches recent 485BPOS filings, extracts the fee table from each,
    and compares them to detect fee changes over time.

    Args:
        cik: SEC CIK number for the fund trust.
        ticker: Fund ticker for share class matching.
        max_filings: Maximum number of historical filings to check.

    Returns:
        FeeHistory with snapshots and detected changes.
    """
    history = FeeHistory(ticker=ticker, cik=cik)

    filings = _find_485_filings(cik, max_filings=max_filings)
    if not filings:
        return history

    for filing in filings:
        html = _fetch_filing_html(
            cik, filing["accession_no"], filing["primary_doc"]
        )
        if not html:
            continue

        # Reuse the 497K fee parser — 485BPOS uses the same fee table format
        fees = parse_497k_html(html, ticker)
        if not fees.has_data:
            continue

        snapshot = FeeSnapshot(
            filing_date=filing["filing_date"],
            accession_no=filing["accession_no"],
            form_type=filing["form_type"],
            management_fee=fees.management_fee,
            twelve_b1_fee=fees.twelve_b1_fee,
            other_expenses=fees.other_expenses,
            total_annual_expenses=fees.total_annual_expenses,
            fee_waiver=fees.fee_waiver,
            net_expenses=fees.net_expenses,
            max_sales_load=fees.max_sales_load,
            portfolio_turnover=fees.portfolio_turnover,
        )
        history.snapshots.append(snapshot)

    # Compare sequential snapshots (newest to oldest)
    for i in range(len(history.snapshots) - 1):
        newer = history.snapshots[i]
        older = history.snapshots[i + 1]
        changes = _compare_snapshots(older, newer)
        history.changes.extend(changes)

    return history


# ── CLI convenience ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m fundautopsy.data.fee_tracker <CIK> <TICKER>")
        sys.exit(1)

    cik = int(sys.argv[1])
    ticker = sys.argv[2].upper()

    print(f"Tracking fee changes for CIK {cik} ({ticker})...")
    history = track_fee_changes(cik, ticker, max_filings=5)

    if not history.snapshots:
        print("No fee data found in recent 485BPOS filings.")
        sys.exit(1)

    print(f"\n=== Fee Snapshots ({len(history.snapshots)} filings) ===")
    for snap in history.snapshots:
        er = snap.effective_expense_ratio
        print(f"  {snap.filing_date} ({snap.form_type}): "
              f"ER={er:.3f}%" if er else f"  {snap.filing_date}: N/A")

    if history.changes:
        print(f"\n=== Fee Changes ({len(history.changes)} detected) ===")
        for change in history.changes:
            arrow = "+" if change.direction == "increase" else ""
            print(f"  {change.field_label}: {change.old_value:.3f}% -> {change.new_value:.3f}% "
                  f"({arrow}{change.change_bps:.1f} bps) "
                  f"[{change.old_filing_date} -> {change.new_filing_date}]")
        print(f"\n  Net change: {history.net_change_bps:+.1f} bps")
    else:
        print("\nNo fee changes detected across recent filings.")
