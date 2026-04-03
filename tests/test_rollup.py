"""Tests for fund-of-funds recursive cost roll-up."""

import pytest


class TestRollup:
    """Test recursive cost roll-up for fund-of-funds."""

    def test_standalone_fund_passes_through(self):
        """Standalone fund (no children) should return unchanged."""
        pytest.skip("Not yet implemented")

    def test_simple_two_fund_rollup(self):
        """Two underlying funds with known costs produce correct weighted sum."""
        pytest.skip("Not yet implemented")

    def test_wrapper_direct_costs_added(self):
        """Wrapper fund's own trading costs are added on top of rolled-up child costs."""
        pytest.skip("Not yet implemented")

    def test_max_recursion_depth_flagged(self):
        """Recursion beyond MAX_RECURSION_DEPTH is flagged, not infinite."""
        pytest.skip("Not yet implemented")
