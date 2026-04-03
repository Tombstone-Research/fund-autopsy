"""Local caching layer for parsed SEC filing data."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# Default cache location
DEFAULT_CACHE_DIR = Path.home() / ".fundautopsy" / "cache"

# TTL by filing type
NCEN_TTL_DAYS = 365  # Annual filing
NPORT_TTL_DAYS = 90  # Quarterly disclosure


class FilingCache:
    """DuckDB-backed cache for parsed filing data.

    Caches N-CEN and N-PORT parsed results to avoid redundant
    EDGAR requests. Keyed by (CIK, series_id, filing_date).
    """

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self.cache_dir / "filings.duckdb"
        # TODO: Initialize DuckDB connection and schema

    def get_ncen(self, series_id: str, cik: str) -> Optional[dict]:
        """Retrieve cached N-CEN data if fresh."""
        # TODO: Implement cache lookup with TTL check
        raise NotImplementedError

    def put_ncen(self, series_id: str, cik: str, data: dict) -> None:
        """Store parsed N-CEN data."""
        # TODO: Implement cache write
        raise NotImplementedError

    def get_nport(self, series_id: str, cik: str) -> Optional[dict]:
        """Retrieve cached N-PORT data if fresh."""
        raise NotImplementedError

    def put_nport(self, series_id: str, cik: str, data: dict) -> None:
        """Store parsed N-PORT data."""
        raise NotImplementedError

    def clear(self) -> None:
        """Clear all cached data."""
        if self._db_path.exists():
            self._db_path.unlink()
