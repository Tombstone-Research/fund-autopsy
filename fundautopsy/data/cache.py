"""Local caching layer for parsed SEC filing data.

NOT YET IMPLEMENTED.

This module provides a DuckDB-backed cache to avoid redundant EDGAR requests
during development and repeated analyses. Planned functionality:

  - Cache parsed N-CEN and N-PORT filing data locally
  - TTL-based invalidation (365 days for N-CEN, 90 days for N-PORT)
  - Key-value storage keyed by (CIK, series_id)
  - Clear/purge operations for development

Current implementation works fine without caching (direct EDGAR hits are fast
enough for interactive use), but this will become important for batch
analysis and avoiding SEC rate limits on large-scale work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any

# Default cache location
DEFAULT_CACHE_DIR: Path = Path.home() / ".fundautopsy" / "cache"

# TTL by filing type
NCEN_TTL_DAYS: int = 365  # Annual filing
NPORT_TTL_DAYS: int = 90  # Quarterly disclosure


class FilingCache:
    """DuckDB-backed cache for parsed filing data.

    NOT YET IMPLEMENTED.

    Will cache N-CEN and N-PORT parsed results to avoid redundant
    EDGAR requests. Keyed by (CIK, series_id, filing_date) with
    TTL-based invalidation per filing type.

    Args:
        cache_dir: Root directory for cache storage. Defaults to
            ~/.fundautopsy/cache/

    Raises:
        NotImplementedError: All cache operations not yet implemented.
    """

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
        """Initialize cache directory and DuckDB connection.

        Args:
            cache_dir: Root directory for cache storage.
        """
        self.cache_dir: Path = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path: Path = self.cache_dir / "filings.duckdb"
        # DuckDB connection initialization pending

    def get_ncen(self, series_id: str, cik: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached N-CEN data if fresh.

        PLANNED: Checks cache for N-CEN data matching the series and CIK,
        returns it if within NCEN_TTL_DAYS, else None.

        Args:
            series_id: SEC series identifier (e.g., 0000001234-05-000001).
            cik: SEC Central Index Key.

        Returns:
            Cached parsed N-CEN data dict, or None if not cached or stale.

        Raises:
            NotImplementedError: This feature is not yet implemented.
        """
        raise NotImplementedError(
            "Filing cache not yet implemented. EDGAR requests are fast enough "
            "for interactive use; caching will be added for batch analysis."
        )

    def put_ncen(self, series_id: str, cik: str, data: Dict[str, Any]) -> None:
        """Store parsed N-CEN data in cache.

        PLANNED: Writes parsed N-CEN data with current timestamp for
        TTL-based invalidation.

        Args:
            series_id: SEC series identifier.
            cik: SEC Central Index Key.
            data: Parsed N-CEN data dict.

        Raises:
            NotImplementedError: This feature is not yet implemented.
        """
        raise NotImplementedError(
            "Filing cache not yet implemented. EDGAR requests are fast enough "
            "for interactive use; caching will be added for batch analysis."
        )

    def get_nport(self, series_id: str, cik: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached N-PORT data if fresh.

        PLANNED: Checks cache for N-PORT data matching the series and CIK,
        returns it if within NPORT_TTL_DAYS, else None.

        Args:
            series_id: SEC series identifier.
            cik: SEC Central Index Key.

        Returns:
            Cached parsed N-PORT data dict, or None if not cached or stale.

        Raises:
            NotImplementedError: This feature is not yet implemented.
        """
        raise NotImplementedError(
            "Filing cache not yet implemented. EDGAR requests are fast enough "
            "for interactive use; caching will be added for batch analysis."
        )

    def put_nport(self, series_id: str, cik: str, data: Dict[str, Any]) -> None:
        """Store parsed N-PORT data in cache.

        PLANNED: Writes parsed N-PORT data with current timestamp for
        TTL-based invalidation.

        Args:
            series_id: SEC series identifier.
            cik: SEC Central Index Key.
            data: Parsed N-PORT data dict.

        Raises:
            NotImplementedError: This feature is not yet implemented.
        """
        raise NotImplementedError(
            "Filing cache not yet implemented. EDGAR requests are fast enough "
            "for interactive use; caching will be added for batch analysis."
        )

    def clear(self) -> None:
        """Clear all cached data.

        Implemented: Deletes the DuckDB file, clearing the cache completely.
        """
        if self._db_path.exists():
            self._db_path.unlink()
