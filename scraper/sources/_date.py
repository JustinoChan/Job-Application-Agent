from __future__ import annotations

from datetime import date, datetime, timezone


def parse_iso_date(value: str | None) -> date | None:
    """Parse an ISO 8601 datetime/date string into a date. Tolerant of None,
    empty, and trailing Z (UTC). Returns None on anything unparseable."""
    if not value:
        return None
    s = value.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt.date()
    except (ValueError, AttributeError):
        return None


def parse_epoch_ms(value) -> date | None:
    """Parse a millisecond epoch (int or float) into a UTC date."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc).date()
    except (TypeError, ValueError):
        return None
