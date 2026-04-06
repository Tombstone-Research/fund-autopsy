"""CSV export.

NOT YET IMPLEMENTED.

Planned functionality to export fund cost analysis to CSV for use in
spreadsheet applications, compatibility with other analysis tools, or
bulk data processing.

Export format will be:
  - One row per cost component (expense ratio, bid-ask spread, etc.)
  - Columns for low/high/mid estimates in basis points
  - Data source tags and confidence ratings
  - Holdings breakdown in separate rows
"""

from __future__ import annotations

from pathlib import Path

from fundautopsy.models.holdings_tree import FundNode


def export_csv(result: FundNode, output_path: Path) -> None:
    """Export cost breakdown to CSV.

    PLANNED: Flattens the FundNode analysis tree to CSV for spreadsheet
    compatibility and bulk processing.

    Args:
        result: Root FundNode from the analysis.
        output_path: Path where CSV file will be written.

    Raises:
        NotImplementedError: This feature is not yet implemented.
    """
    raise NotImplementedError(
        "CSV export not yet implemented. Complete analysis is available "
        "via the web dashboard and API responses."
    )
