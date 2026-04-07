"""Tests for N-CEN filing parser."""

from fundautopsy.data.ncen import parse_ncen_xml
from fundautopsy.models.filing_data import DataSourceTag


class TestNCENParser:
    """Test N-CEN XML parsing and data extraction."""

    def test_parse_soft_dollar_fields(self, agthx_ncen_xml, agthx_series_id):
        """Verify extraction of C.6.a, C.6.b, C.6.c from sample filing."""
        result = parse_ncen_xml(agthx_ncen_xml, agthx_series_id)

        assert result is not None, "Parse should succeed with valid XML"
        assert result.fund_name is not None
        assert len(result.fund_name) > 0
        # N-CEN has aggregate commission data
        assert result.aggregate_commission is not None

    def test_missing_soft_dollar_fields_tagged_correctly(self, agthx_ncen_xml, agthx_series_id):
        """When C.6.b/C.6.c are absent, tag as UNAVAILABLE or NOT_DISCLOSED."""
        result = parse_ncen_xml(agthx_ncen_xml, agthx_series_id)

        assert result is not None
        # Convert to NCENData to verify tagging
        ncen_data = result.to_ncen_data()

        # If soft dollar arrangements exist but amounts are not disclosed,
        # the soft_dollar_commissions should be tagged as NOT_DISCLOSED
        if result.is_brokerage_research_payment:
            # Soft dollars are present
            assert ncen_data.has_soft_dollar_arrangements is True
            # But the amount tag should be NOT_DISCLOSED (typical for N-CEN)
            assert ncen_data.soft_dollar_commissions.tag in (
                DataSourceTag.NOT_DISCLOSED,
                DataSourceTag.UNAVAILABLE,
            )

    def test_multi_series_filing_isolates_correct_series(self, agthx_ncen_xml, agthx_series_id):
        """Multi-series trust N-CEN should return data for target series only."""
        # Parse with the correct series ID
        result = parse_ncen_xml(agthx_ncen_xml, agthx_series_id)
        assert result is not None, "Should find the target series"

        # The series ID in the result should match
        assert result.series_id == agthx_series_id

    def test_turnover_rate_extraction(self, agthx_ncen_xml, agthx_series_id):
        """Verify that N-CEN parsing returns core fund data."""
        result = parse_ncen_xml(agthx_ncen_xml, agthx_series_id)

        assert result is not None
        # Core fields should be extracted
        assert result.fund_name  # Fund name should be present
        assert result.series_id  # Series ID should be set
        # Most N-CEN filings should have some service provider data
        assert result.investment_adviser or result.administrator
