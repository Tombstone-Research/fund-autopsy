"""Holdings tree structure for fund-of-funds recursive analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from fundautopsy.models.fund_metadata import FundMetadata
from fundautopsy.models.filing_data import NCENData, NPortData
from fundautopsy.models.cost_breakdown import CostBreakdown


@dataclass
class FundNode:
    """A node in the fund-of-funds holdings tree."""

    metadata: FundMetadata
    allocation_weight: float = 1.0  # 1.0 for root, proportion for children
    depth: int = 0

    # Filing data (populated in Stage 2)
    ncen_data: Optional[NCENData] = None
    nport_data: Optional[NPortData] = None

    # Full N-CEN data (for supplementary display: lending, brokers, etc.)
    ncen_full: object = None  # NCENFullData, typed as object to avoid circular import

    # Portfolio turnover from 497K prospectus (may be more reliable than N-CEN)
    prospectus_turnover: Optional[float] = None  # As percentage, e.g. 32.0 = 32%

    # Cost data (populated in Stage 3)
    cost_breakdown: Optional[CostBreakdown] = None

    # Children (populated if fund-of-funds)
    children: list[FundNode] = field(default_factory=list)

    # Data availability flags
    ncen_available: bool = False
    nport_available: bool = False
    data_notes: list[str] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        """True if this is a standalone fund (no underlying funds)."""
        return len(self.children) == 0

    @property
    def is_fund_of_funds(self) -> bool:
        """True if this node has underlying fund holdings."""
        return len(self.children) > 0

    def walk(self) -> list[FundNode]:
        """Iterate all nodes in the tree, depth-first."""
        nodes = [self]
        for child in self.children:
            nodes.extend(child.walk())
        return nodes

    def leaf_nodes(self) -> list[FundNode]:
        """Return only leaf (standalone fund) nodes."""
        return [n for n in self.walk() if n.is_leaf]


MAX_RECURSION_DEPTH = 3
