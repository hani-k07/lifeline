"""All timestamps are Pakistan Standard Time (UTC+5, no DST) and stored as ISO-8601 with an explicit offset."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

PKT = timezone(timedelta(hours=5), "PKT")


def now() -> datetime:
    """Current time in PKT. Tests monkeypatch this."""
    return datetime.now(PKT)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def today() -> date:
    return now().date()
