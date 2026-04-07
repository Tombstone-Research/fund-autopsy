"""Direct 497K fee table HTML parser.

Fallback parser that extracts fee data directly from 497K filing HTML
when edgartools' built-in parser returns None values. Handles three
known HTML layout patterns:

1. Standard SEC table (most fund families) — <TR> rows with label + percent cells
2. Multi-column trust filings (Oakmark, etc.) — header row identifies share class columns
3. Div-based layouts (Fidelity) — nested <div> with inline styles instead of <table>

Also handles multi-fund trusts that file separate 497Ks per share class
by searching through filings to find the one containing the target ticker.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from lxml import html as lxml_html

logger = logging.getLogger(__name__)


# Fee percentage sanity threshold. Values above this trigger a warning log
# but are still returned. Set high enough that legitimate high-cost funds
# (CEFs with leverage, multi-layer FoFs) pass through while catching
# obvious parse errors like extracting a year (e.g., "2024" → 2024%).
FEE_SANITY_THRESHOLD_PCT: float = 20.0

# Canonical fee row labels and their field mappings
_LABEL_MAP = {
    "management fee": "management_fee",
    "management fees": "management_fee",
    "distribution and/or service": "twelve_b1_fee",
    "distribution (12b": "twelve_b1_fee",
    "12b-1": "twelve_b1_fee",
    "other expense": "other_expenses",
    "acquired fund fee": "acquired_fund_fees",
    "total annual fund operating": "total_annual_expenses",
    "total annual operating": "total_annual_expenses",
    "total fund operating": "total_annual_expenses",
    "fee waiver": "fee_waiver",
    "expense reimbursement": "fee_waiver",
    "net expense": "net_expenses",
    "net annual": "net_expenses",
    "total annual fund operating expenses after": "net_expenses",
}

_TURNOVER_PATTERN = re.compile(
    r"(?:portfolio\s+turnover|turnover\s+rate).*?(\d+)\s*%", re.IGNORECASE | re.DOTALL
)

_LOAD_PATTERN = re.compile(
    r"maximum\s+(?:initial\s+)?sales\s+(?:charge|load).*?(\d+\.?\d*)\s*%",
    re.IGNORECASE | re.DOTALL,
)

_PCT_PATTERN = re.compile(r"(\d+\.?\d*)\s*%")
_NUM_PATTERN = re.compile(r"(\d+\.?\d*)")


@dataclass
class ParsedFees:
    """Fee data extracted directly from 497K HTML."""

    management_fee: Optional[float] = None
    twelve_b1_fee: Optional[float] = None
    other_expenses: Optional[float] = None
    acquired_fund_fees: Optional[float] = None
    total_annual_expenses: Optional[float] = None
    fee_waiver: Optional[float] = None
    net_expenses: Optional[float] = None
    max_sales_load: Optional[float] = None
    portfolio_turnover: Optional[float] = None
    fee_threshold_warning: bool = False  # True if any parsed value exceeded FEE_SANITY_THRESHOLD_PCT

    @property
    def has_data(self) -> bool:
        """True if at least management_fee or total_annual_expenses was parsed."""
        return self.management_fee is not None or self.total_annual_expenses is not None


def _extract_pct(text: str) -> Optional[float]:
    """Pull the first percentage value from a cell's text content."""
    text = text.strip()
    if not text or text.lower() in ("none", "n/a", "—", "–", "-"):
        return None
    m = _PCT_PATTERN.search(text)
    if m:
        return float(m.group(1))
    m = _NUM_PATTERN.search(text)
    if m:
        val = float(m.group(1))
        # Values >= 100 are almost certainly years or other non-fee numbers
        # (no fund charges 100%+ annual fees). Reject them outright.
        if val >= 100:
            logger.debug(
                "Rejecting extracted value %.0f (likely year or non-fee number) from: %r",
                val, text[:80],
            )
            return None
        if val < FEE_SANITY_THRESHOLD_PCT:
            return val
        # Value exceeds soft threshold but is plausible (CEFs with leverage,
        # layered FoFs). Log warning but still return it.
        logger.warning(
            "Parsed fee value %.2f%% exceeds %.0f%% sanity threshold — "
            "verify manually (source text: %r)",
            val, FEE_SANITY_THRESHOLD_PCT, text[:80],
        )
        return val
    return None


def _match_label(text: str) -> Optional[str]:
    """Match a row label to a ParsedFees field name."""
    # Normalize whitespace, line breaks, and non-breaking spaces
    lower = re.sub(r"[\s\xa0]+", " ", text.lower().strip())
    for pattern, field_name in _LABEL_MAP.items():
        if pattern in lower:
            return field_name
    return None


def _find_class_column(header_texts: list[str], ticker: str) -> int:
    """Identify which column index corresponds to the target share class.

    In multi-class tables, the header row contains class names or tickers.
    Returns 0-based index into the data columns (excluding the label column).
    """
    ticker_upper = ticker.upper()
    for i, text in enumerate(header_texts):
        if ticker_upper in text.upper():
            return i
    # Fall back: check for class name patterns
    # "Investor Class", "Class I", etc.
    for i, text in enumerate(header_texts):
        for label in ("investor", "class i ", "class i\xa0", "class a"):
            if label in text.lower():
                return i
    return 0  # default to first column


def _parse_table_rows(
    html_str: str, ticker: str, start_offset: int = 0
) -> ParsedFees:
    """Parse fee data from standard HTML table rows."""
    fees = ParsedFees()

    # Find the fee table region
    lower = html_str.lower()
    anchors = [
        "annual fund operating expense",
        "annual operating expense",
        "fee table",
    ]
    table_start = -1
    for anchor in anchors:
        idx = lower.find(anchor, start_offset)
        if idx >= 0:
            table_start = idx
            break

    if table_start < 0:
        return fees

    # Extract a generous region around the fee table
    region = html_str[max(0, table_start - 500) : table_start + 8000]
    tree = lxml_html.fromstring(region)
    rows = tree.xpath(".//tr")

    if not rows:
        return fees

    # Detect multi-class header to find the right column
    target_col = 0
    for row in rows[:5]:
        cells = row.xpath(".//td")
        texts = [c.text_content().strip() for c in cells]
        texts_clean = [t for t in texts if t]
        # Header row typically has class names or tickers
        if len(texts_clean) >= 2 and not any(
            kw in " ".join(texts_clean).lower()
            for kw in ("management", "distribution", "expense", "fee")
        ):
            target_col = _find_class_column(texts_clean, ticker)

    # Parse fee rows
    for row in rows:
        cells = row.xpath(".//td")
        texts = [c.text_content().strip() for c in cells]
        if not texts:
            continue

        # Try matching the label from the first cell
        label_text = texts[0]
        field_name = _match_label(label_text)
        if field_name is None:
            # Some filings split the label with <BR> tags across the first cell.
            # Only try full-row matching if the first cell looks like a split label,
            # NOT a footnote. Footnotes start with *, **, †, (1), etc.
            first = texts[0].strip()
            is_footnote = bool(re.match(r"^[\*†\(\d]", first))
            if not is_footnote and len(first) < 60:
                full_row_text = " ".join(t for t in texts if not _PCT_PATTERN.fullmatch(t.strip()))
                field_name = _match_label(full_row_text)
            if field_name is None:
                continue

        # Collect all value cells (skip the label cell)
        value_texts = [t for t in texts[1:] if t]

        if not value_texts:
            continue

        # For multi-column tables, pick the right column
        # Value cells might be split: ["0.50", "%"] or combined: ["0.50%"]
        # Reconstruct by joining consecutive cells
        joined = " ".join(value_texts)
        # Split by column boundaries (look for multiple percentages)
        col_values = _PCT_PATTERN.findall(joined)

        if col_values and target_col < len(col_values):
            val = float(col_values[target_col])
        elif col_values:
            val = float(col_values[0])
        else:
            val = _extract_pct(joined)

        if val is not None:
            setattr(fees, field_name, val)

    return fees


def _parse_div_layout(html_str: str, ticker: str) -> ParsedFees:
    """Parse fee data from div-based layouts (Fidelity style)."""
    fees = ParsedFees()
    tree = lxml_html.fromstring(html_str)

    # In div-based layouts, fee rows are table rows where the first cell
    # has the label and the second has the value, but styled with <div>/<font>
    rows = tree.xpath(".//tr")
    for row in rows:
        cells = row.xpath(".//td")
        if len(cells) < 2:
            continue
        label_text = cells[0].text_content().strip()
        field_name = _match_label(label_text)
        if field_name is None:
            continue
        value_text = cells[1].text_content().strip()
        val = _extract_pct(value_text)
        if val is not None:
            setattr(fees, field_name, val)

    return fees


def parse_497k_html(
    html_str: str,
    ticker: str,
    fund_name: Optional[str] = None,
) -> ParsedFees:
    """Extract fee data from raw 497K filing HTML.

    Tries table-based parsing first, falls back to div-based for
    Fidelity-style filings.

    Args:
        html_str: Raw HTML content of the 497K filing.
        ticker: Fund ticker to match the correct share class column.
        fund_name: Optional fund name for multi-fund filings.

    Returns:
        ParsedFees with extracted values.
    """
    # Try standard table parsing
    fees = _parse_table_rows(html_str, ticker)
    if fees.has_data:
        # Extract turnover and load from the full document
        _extract_turnover_and_load(html_str, fees)
        return fees

    # Try div-based layout
    fees = _parse_div_layout(html_str, ticker)
    if fees.has_data:
        _extract_turnover_and_load(html_str, fees)
        return fees

    return fees


def _extract_turnover_and_load(html_str: str, fees: ParsedFees) -> None:
    """Extract portfolio turnover and sales load from full document text."""
    text = lxml_html.fromstring(html_str).text_content()

    m = _TURNOVER_PATTERN.search(text)
    if m:
        fees.portfolio_turnover = float(m.group(1))

    m = _LOAD_PATTERN.search(text)
    if m:
        fees.max_sales_load = float(m.group(1))


def find_filing_for_ticker(
    filings_497k, ticker: str, max_search: int = 20
) -> Optional[object]:
    """Search through 497K filings to find the one containing the target ticker.

    Some trusts file separate 497Ks per share class or per fund.
    This iterates through recent filings looking for one that
    mentions the specific ticker.

    Args:
        filings_497k: edgartools filing collection filtered to 497K.
        ticker: Target fund ticker.
        max_search: Maximum filings to check.

    Returns:
        The matching filing object, or None.
    """
    ticker_upper = ticker.upper()
    for i in range(min(max_search, len(filings_497k))):
        try:
            html = filings_497k[i].html()
            if ticker_upper in html:
                return filings_497k[i]
        except Exception as exc:
            logger.debug("Error searching 497K filing %d for %s: %s", i, ticker, exc)
            continue
    return None
