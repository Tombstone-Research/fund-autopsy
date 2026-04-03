"""JSON export."""

from __future__ import annotations

from pathlib import Path

from fundautopsy.models.holdings_tree import FundNode


def export_json(result: FundNode, output_path: Path) -> None:
    """Export full analysis results to JSON."""
    # TODO: Implement JSON serialization of FundNode tree
    raise NotImplementedError
