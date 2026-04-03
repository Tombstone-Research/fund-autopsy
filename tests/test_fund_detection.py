"""Tests for fund-of-funds detection logic."""

import pytest


class TestFundDetection:
    """Test identification of underlying funds in N-PORT holdings."""

    def test_registered_investment_company_flagged(self):
        """Holdings with issuerCat = RIC are identified as fund holdings."""
        pytest.skip("Not yet implemented")

    def test_cusip_to_cik_resolution(self):
        """CUSIP resolving to a CIK confirms fund-of-funds relationship."""
        pytest.skip("Not yet implemented")

    def test_non_fund_holdings_excluded(self):
        """Individual securities are not flagged as underlying funds."""
        pytest.skip("Not yet implemented")
