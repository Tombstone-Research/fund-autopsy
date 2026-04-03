"""Stage 4: Fund-of-funds recursive cost roll-up.

For the MVP, this is largely a pass-through since we don't yet
recursively resolve underlying fund costs. The infrastructure is
here for when CUSIP-to-CIK resolution is implemented.
"""

from __future__ import annotations

from fundautopsy.models.holdings_tree import FundNode
from fundautopsy.models.cost_breakdown import CostBreakdown


def rollup_costs(tree: FundNode) -> FundNode:
    """Roll up costs from underlying funds to the wrapper level.

    For fund-of-funds:
        Wrapper_Total_Cost = Wrapper_Direct_Cost + SUM(Fund_Cost[i] * Weight[i])

    For standalone funds (the common MVP case), returns the tree unchanged.

    Args:
        tree: Holdings tree with cost_breakdown populated on all nodes.

    Returns:
        Tree with rolled-up cost data on the root node.
    """
    if tree.is_leaf:
        return tree

    # Process bottom-up: roll up children first
    for child in tree.children:
        if child.is_fund_of_funds:
            rollup_costs(child)

    # For MVP: fund-of-funds detected but underlying costs not yet resolved.
    # The wrapper's own trading costs are already computed.
    # Add a note about the limitation.
    if tree.cost_breakdown:
        if not any("fund-of-funds" in n.lower() for n in tree.data_notes):
            tree.data_notes.append(
                "Fund-of-funds roll-up: underlying fund costs not yet resolved. "
                "Displayed costs reflect the wrapper fund's direct trading costs only."
            )

    return tree
