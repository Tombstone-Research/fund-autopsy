"""JSON export.

NOT YET IMPLEMENTED.

Planned functionality to export the full fund analysis tree (FundNode)
as a JSON file for downstream processing, integration with other tools,
or archival.

Export format will be:
  - Hierarchical JSON mirroring the FundNode tree structure
  - Cost components with ranges (low/high estimates)
  - Asset composition and holdings
  - Data sources and confidence indicators
"""

from __future__ import annotations

from pathlib import Path

from fundautopsy.models.holdings_tree import FundNode


def export_json(result: FundNode, output_path: Path) -> None:
    """Export full analysis results to JSON.

    PLANNED: Serializes the complete FundNode analysis tree to a JSON file,
    preserving the hierarchical structure and all cost estimates.

    Args:
        result: Root FundNode from the analysis.
        output_path: Path where JSON file will be written.

    Raises:
        NotImplementedError: This feature is not yet implemented.
    """
    raise NotImplementedError(
        "JSON export not yet implemented. Complete analysis is available "
        "via the web dashboard and API responses."
    )
