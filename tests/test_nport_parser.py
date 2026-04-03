"""Tests for N-PORT filing parser."""

import pytest


class TestNPortParser:
    """Test N-PORT XML parsing and holdings extraction."""

    def test_parse_holdings_list(self):
        """Verify complete holdings extraction from sample filing."""
        pytest.skip("Fixture data not yet available")

    def test_asset_class_weights(self):
        """Verify asset class weight computation from holdings."""
        pytest.skip("Fixture data not yet available")

    def test_fund_of_funds_detection(self):
        """Holdings with issuerCat = registered investment co. are flagged."""
        pytest.skip("Fixture data not yet available")
