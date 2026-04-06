"""Tests for data retrieval modules."""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from fundautopsy.data.cache import FilingCache, DEFAULT_CACHE_DIR, NCEN_TTL_DAYS, NPORT_TTL_DAYS
from fundautopsy.data.edgar import (
    MutualFundIdentifier,
    FilingEntry,
    get_edgar_client,
    _rate_limit,
    resolve_ticker,
    EDGAR_SUBMISSIONS_URL,
    EDGAR_ARCHIVES_URL,
    EDGAR_MF_TICKERS_URL,
    RATE_LIMIT_DELAY,
)


class TestMutualFundIdentifier:
    """Test MutualFundIdentifier dataclass."""

    def test_identifier_construction(self):
        """MutualFundIdentifier should construct properly."""
        identifier = MutualFundIdentifier(
            ticker="VTSAX",
            cik=123456789,
            series_id="S000000001",
            class_id="C000000001",
        )
        assert identifier.ticker == "VTSAX"
        assert identifier.cik == 123456789
        assert identifier.series_id == "S000000001"
        assert identifier.class_id == "C000000001"

    def test_cik_padding(self):
        """CIK should be padded to 10 digits."""
        identifier = MutualFundIdentifier(
            ticker="TEST",
            cik=123,
            series_id="S000000001",
            class_id="C000000001",
        )
        assert identifier.cik_padded == "0000000123"
        assert len(identifier.cik_padded) == 10

    def test_cik_padding_already_10_digits(self):
        """CIK already 10 digits should not be padded further."""
        identifier = MutualFundIdentifier(
            ticker="TEST",
            cik=1234567890,
            series_id="S000000001",
            class_id="C000000001",
        )
        assert identifier.cik_padded == "1234567890"
        assert len(identifier.cik_padded) == 10


class TestFilingEntry:
    """Test FilingEntry dataclass."""

    def test_filing_entry_construction(self):
        """FilingEntry should construct with required fields."""
        entry = FilingEntry(
            form_type="N-CEN",
            filing_date="2025-03-15",
            accession_number="0000950140-25-001234",
            primary_document="form.htm",
        )
        assert entry.form_type == "N-CEN"
        assert entry.filing_date == "2025-03-15"
        assert entry.accession_number == "0000950140-25-001234"
        assert entry.primary_document == "form.htm"

    def test_filing_entry_optional_document(self):
        """Primary document should be optional."""
        entry = FilingEntry(
            form_type="N-PORT",
            filing_date="2025-03-15",
            accession_number="0000950140-25-001234",
        )
        assert entry.form_type == "N-PORT"
        assert entry.primary_document == ""


class TestEDGARClient:
    """Test EDGAR client creation."""

    def test_edgar_client_creation(self):
        """EDGAR client should be created."""
        client = get_edgar_client()
        assert client is not None
        assert hasattr(client, 'get')
        assert hasattr(client, 'close')

    def test_edgar_client_has_user_agent(self):
        """EDGAR client should have User-Agent header."""
        client = get_edgar_client()
        assert "User-Agent" in client.headers
        assert len(client.headers["User-Agent"]) > 0

    def test_edgar_client_user_agent_includes_email(self):
        """User-Agent should include contact email."""
        client = get_edgar_client()
        ua = client.headers["User-Agent"]
        assert "@" in ua or "open-source" in ua.lower()

    def test_edgar_client_timeout_set(self):
        """EDGAR client should have timeout."""
        client = get_edgar_client()
        assert client.timeout is not None
        # timeout can be a float or httpx.Timeout object; just verify it's set
        assert str(client.timeout) != "None"

    def test_edgar_client_closes_properly(self):
        """EDGAR client should close without error."""
        client = get_edgar_client()
        client.close()  # Should not raise


class TestRateLimit:
    """Test rate limiting."""

    def test_rate_limit_constant_positive(self):
        """Rate limit delay should be positive."""
        assert RATE_LIMIT_DELAY > 0
        assert RATE_LIMIT_DELAY <= 0.2

    def test_rate_limit_enforced(self):
        """Rate limiting should enforce minimum delay."""
        import time
        start = time.time()
        _rate_limit()
        _rate_limit()
        elapsed = time.time() - start
        # Should have enforced at least one delay period
        assert elapsed >= RATE_LIMIT_DELAY * 0.8  # Allow some margin


class TestEDGARURLs:
    """Test EDGAR endpoint URLs."""

    def test_submissions_url_valid(self):
        """Submissions URL should be valid."""
        assert EDGAR_SUBMISSIONS_URL is not None
        assert "sec.gov" in EDGAR_SUBMISSIONS_URL
        assert "submissions" in EDGAR_SUBMISSIONS_URL
        assert EDGAR_SUBMISSIONS_URL == "https://data.sec.gov/submissions"

    def test_archives_url_valid(self):
        """Archives URL should be valid."""
        assert EDGAR_ARCHIVES_URL is not None
        assert "sec.gov" in EDGAR_ARCHIVES_URL
        assert "edgar" in EDGAR_ARCHIVES_URL
        assert EDGAR_ARCHIVES_URL == "https://www.sec.gov/Archives/edgar/data"

    def test_mf_tickers_url_valid(self):
        """Mutual fund tickers URL should be valid."""
        assert EDGAR_MF_TICKERS_URL is not None
        assert "sec.gov" in EDGAR_MF_TICKERS_URL
        assert "tickers_mf.json" in EDGAR_MF_TICKERS_URL
        assert EDGAR_MF_TICKERS_URL == "https://www.sec.gov/files/company_tickers_mf.json"


class TestFilingCache:
    """Test filing cache."""

    def test_cache_initialization(self):
        """Cache should initialize with directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FilingCache(cache_dir=Path(tmpdir))
            assert cache.cache_dir is not None
            assert cache.cache_dir.exists()

    def test_cache_creates_directory(self):
        """Cache should create directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "new_cache"
            assert not cache_path.exists()
            cache = FilingCache(cache_dir=cache_path)
            assert cache_path.exists()

    def test_cache_has_db_path(self):
        """Cache should have database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FilingCache(cache_dir=Path(tmpdir))
            assert cache._db_path is not None
            assert str(cache._db_path).endswith(".duckdb")

    def test_default_cache_dir_in_home(self):
        """Default cache dir should be in home directory."""
        assert DEFAULT_CACHE_DIR.is_absolute()
        assert ".fundautopsy" in str(DEFAULT_CACHE_DIR)

    def test_ncen_ttl_reasonable(self):
        """N-CEN TTL should be annual (365 days)."""
        assert NCEN_TTL_DAYS == 365

    def test_nport_ttl_reasonable(self):
        """N-PORT TTL should be quarterly (90 days)."""
        assert NPORT_TTL_DAYS == 90

    def test_nport_ttl_shorter_than_ncen(self):
        """N-PORT should have shorter TTL than N-CEN."""
        assert NPORT_TTL_DAYS < NCEN_TTL_DAYS

    def test_cache_clear_removes_db(self):
        """Cache clear should remove database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FilingCache(cache_dir=Path(tmpdir))
            # Create a dummy file at db path
            cache._db_path.parent.mkdir(parents=True, exist_ok=True)
            cache._db_path.touch()
            assert cache._db_path.exists()

            cache.clear()
            # DB file should be removed
            assert not cache._db_path.exists()


class TestResolveTickerFunction:
    """Test ticker resolution (mocked to avoid actual SEC calls)."""

    @patch('fundautopsy.data.edgar.get_edgar_client')
    def test_resolve_ticker_returns_identifier(self, mock_get_client):
        """Resolve ticker should return MutualFundIdentifier."""
        mock_client = Mock()
        mock_client.get.return_value.json.return_value = {
            "fields": ["cik", "seriesId", "classId", "symbol"],
            "data": [
                [1234567, "S000000001", "C000000001", "VTSAX"]
            ]
        }
        mock_get_client.return_value = mock_client

        result = resolve_ticker("VTSAX")

        assert result is not None
        assert result.ticker == "VTSAX"
        assert result.cik == 1234567

    @patch('fundautopsy.data.edgar.get_edgar_client')
    def test_resolve_ticker_case_insensitive(self, mock_get_client):
        """Resolve ticker should be case-insensitive."""
        mock_client = Mock()
        mock_client.get.return_value.json.return_value = {
            "fields": ["cik", "seriesId", "classId", "symbol"],
            "data": [
                [1234567, "S000000001", "C000000001", "VTSAX"]
            ]
        }
        mock_get_client.return_value = mock_client

        result = resolve_ticker("vtsax")

        assert result is not None
        assert result.ticker == "VTSAX"

    @patch('fundautopsy.data.edgar.get_edgar_client')
    def test_resolve_ticker_not_found_returns_none(self, mock_get_client):
        """Resolve ticker should return None if not found."""
        mock_client = Mock()
        mock_client.get.return_value.json.return_value = {
            "fields": ["cik", "seriesId", "classId", "symbol"],
            "data": []
        }
        mock_get_client.return_value = mock_client

        result = resolve_ticker("NOTREAL")

        assert result is None

    @patch('fundautopsy.data.edgar.get_edgar_client')
    def test_resolve_ticker_with_provided_client(self, mock_get_client):
        """Resolve ticker should use provided client."""
        mock_client = Mock()
        mock_client.get.return_value.json.return_value = {
            "fields": ["cik", "seriesId", "classId", "symbol"],
            "data": [
                [1234567, "S000000001", "C000000001", "AGTHX"]
            ]
        }

        result = resolve_ticker("AGTHX", client=mock_client)

        assert result is not None
        # Should not call get_edgar_client since we provided one
        mock_get_client.assert_not_called()


class TestEDGARConfiguration:
    """Test EDGAR configuration consistency."""

    def test_user_agent_string_well_formed(self):
        """User-Agent string should be well-formed per SEC guidelines."""
        client = get_edgar_client()
        ua = client.headers["User-Agent"]

        # Should have format: project/version (email; description)
        assert "/" in ua  # Version separator
        assert "(" in ua and ")" in ua  # Contact info
        assert "@" in ua or ";" in ua  # Email or separator

    def test_rate_limit_respects_sec_limits(self):
        """Rate limit should be at least 100ms (10 requests/sec)."""
        assert RATE_LIMIT_DELAY >= 0.10

    def test_all_endpoints_https(self):
        """All SEC endpoints should use HTTPS."""
        assert EDGAR_SUBMISSIONS_URL.startswith("https://")
        assert EDGAR_ARCHIVES_URL.startswith("https://")
        assert EDGAR_MF_TICKERS_URL.startswith("https://")
