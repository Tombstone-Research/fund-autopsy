"""Tests for N-CEN filing parser."""

import pytest


class TestNCENParser:
    """Test N-CEN XML parsing and data extraction."""

    def test_parse_soft_dollar_fields(self):
        """Verify extraction of C.6.a, C.6.b, C.6.c from sample filing."""
        # TODO: Load fixture XML, parse, assert field values
        pytest.skip("Fixture data not yet available")

    def test_missing_soft_dollar_fields_tagged_correctly(self):
        """When C.6.b/C.6.c are absent, tag as UNAVAILABLE or NOT_DISCLOSED."""
        pytest.skip("Fixture data not yet available")

    def test_multi_series_filing_isolates_correct_series(self):
        """Multi-series trust N-CEN should return data for target series only."""
        pytest.skip("Fixture data not yet available")

    def test_turnover_rate_extraction(self):
        """Verify portfolio turnover rate from C.7."""
        pytest.skip("Fixture data not yet available")
