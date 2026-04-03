"""CSV export."""

from __future__ import annotations

from pathlib import Path

from fundautopsy.models.holdings_tree import FundNode


def export_csv(result: FundNode, output_path: Path) -> None:
    """Export cost breakdown to CSV."""
    # TODO: Implement CSV export
    raise NotImplementedError
