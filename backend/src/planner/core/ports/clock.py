"""Clock port (Backend.md) - injectable time for tests."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    """Abstract clock for obtaining timezone-aware current time."""

    def now(self) -> datetime:
        """Current time (timezone-aware UTC)."""
        ...
