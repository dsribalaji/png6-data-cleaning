"""System clock adapter providing current UTC time."""

from __future__ import annotations

from datetime import datetime, timezone


class SystemClock:
    """Real system clock adapter returning timezone-aware UTC datetime."""

    def now(self) -> datetime:
        """Return the current time in UTC."""
        return datetime.now(timezone.utc)
