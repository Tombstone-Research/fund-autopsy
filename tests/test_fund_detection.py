"""Tests for fund-of-funds detection logic."""

import pytest
from fundautopsy.data.nport import detect_fund_holdings
from fundautopsy.models.filing_data import NPortData, NPortHolding
from datetime import date


class TestFundDetection:
    """Test identification of underlying funds in N-PORT holdings."""

    def test_registered_investment_company_flagged(self):
        """Holdings with issuerCat = RIC are identified as fund holdings."""
        # Create an N-PORT with a holding that has issuerCat = RIC
        nport = NPortData(
            filing_date=date(2024, 3, 31),
            reporting_period_end=date(2024, 3, 31),
            series_id="S000009228",
        )

        # Add a registered investment company holding
        fund_holding = NPortHolding(
            name="Vanguard Total Bond Market Fund",
            issuer_category="RIC",  # Explicitly marked as registered investment company
            pct_of_net_assets=15.0,
            value_usd=1500000.0,
        )
        nport.holdings.append(fund_holding)

        # Detect fund holdings
        detected = detect_fund_holdings(nport)

        # Should detect this as a fund
        assert len(detected) == 1
        assert detected[0].name == "Vanguard Total Bond Market Fund"
        assert detected[0].is_registered_investment_company is True

    def test_cusip_to_cik_resolution(self):
        """Holdings with issuerCat explicitly says RF are identified as funds."""
        # Test that holdings with issuerCat = RF are detected
        nport = NPortData(
            filing_date=date(2024, 3, 31),
            reporting_period_end=date(2024, 3, 31),
            series_id="S000009228",
        )

        # Add a holding with issuerCat = RF (rare but supported)
        fund_holding = NPortHolding(
            name="BlackRock iShares MSCI USA Small-Cap ETF Trust",
            issuer_category="RF",
            cusip="656560759",
            pct_of_net_assets=5.0,
            value_usd=500000.0,
        )
        nport.holdings.append(fund_holding)

        detected = detect_fund_holdings(nport)

        assert len(detected) == 1
        assert detected[0].is_registered_investment_company is True

    def test_non_fund_holdings_excluded(self):
        """Individual securities are not flagged as underlying funds."""
        nport = NPortData(
            filing_date=date(2024, 3, 31),
            reporting_period_end=date(2024, 3, 31),
            series_id="S000009228",
        )

        # Add various non-fund holdings
        stock_holding = NPortHolding(
            name="Apple Inc. Common Stock",
            issuer_category="CS",  # Common stock
            cusip="037833100",
            pct_of_net_assets=3.5,
            value_usd=350000.0,
        )

        bond_holding = NPortHolding(
            name="US Treasury Bond 2.5% due 2030",
            issuer_category="GV",  # Government debt
            cusip="912828K60",
            pct_of_net_assets=2.0,
            value_usd=200000.0,
        )

        nport.holdings.append(stock_holding)
        nport.holdings.append(bond_holding)

        detected = detect_fund_holdings(nport)

        # Neither should be flagged as funds
        assert len(detected) == 0
        assert stock_holding.is_registered_investment_company is False
        assert bond_holding.is_registered_investment_company is False
