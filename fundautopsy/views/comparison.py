"""Multi-fund comparison view."""

from __future__ import annotations

from rich.console import Console

from fundautopsy.models.holdings_tree import FundNode


def render_comparison(
    results: list[FundNode],
    investment: float,
    horizon: int,
    assumed_return: float,
    console: Console,
) -> None:
    """Render side-by-side comparison of 2-5 funds.

    Shows:
    - Normalized costs in basis points
    - Lowest/highest cost highlighting
    - Total cost gap
    - Dollar impact over 10/20/30 year horizons
    """
    # TODO: Implement comparison view
    console.print("[yellow]Comparison view not yet implemented[/yellow]")
