"""Login throttling keyed by email (so unknown emails are throttled identically: no user enumeration)."""
from __future__ import annotations

from lifeline.config import get_settings
from lifeline.db.connection import connect


def normalize(email: str) -> str:
    return email.strip().lower()


def lock_remaining(email: str, now: float) -> int:
    """Seconds until the account may try again (0 = not locked)."""
    with connect() as conn:
        row = conn.execute("SELECT locked_until FROM login_throttle WHERE email = ?", (normalize(email),)).fetchone()
    return max(0, int(row["locked_until"] - now)) if row else 0


def record_failure(email: str, now: float) -> int:
    """Count a failed attempt. Returns the lock length in seconds if this attempt triggered a lock, else 0."""
    settings = get_settings()
    key = normalize(email)
    with connect() as conn:
        row = conn.execute("SELECT failed_count, locked_until FROM login_throttle WHERE email = ?", (key,)).fetchone()
        count = (row["failed_count"] if row else 0) + 1
        locked_until = row["locked_until"] if row else 0
        lock = 0
        if count >= settings.login_max_attempts:
            lock = settings.login_lockout_minutes * 60
            locked_until, count = int(now) + lock, 0     # fresh set of attempts once the lock ends
        conn.execute(
            "INSERT INTO login_throttle (email, failed_count, locked_until, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(email) DO UPDATE SET failed_count = excluded.failed_count, "
            "locked_until = excluded.locked_until, updated_at = excluded.updated_at",
            (key, count, locked_until, int(now)),
        )
    return lock


def clear(email: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM login_throttle WHERE email = ?", (normalize(email),))
