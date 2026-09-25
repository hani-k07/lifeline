"""Small display helpers for pages."""
from __future__ import annotations

from datetime import datetime


def time_until(iso_deadline: str) -> str:
    """Human-readable time left until an ISO deadline, e.g. '4h 23m', '2d 3h' or 'OVERDUE 2h ago'."""
    try:
        deadline = datetime.fromisoformat(str(iso_deadline))
    except (ValueError, TypeError):
        return "Unknown"
    now = datetime.now(deadline.tzinfo) if deadline.tzinfo else datetime.now()
    total = int((deadline - now).total_seconds())
    if total < 0:
        hours, minutes = abs(total) // 3600, (abs(total) % 3600) // 60
        return f"OVERDUE {hours}h ago" if hours else f"OVERDUE {minutes}m ago"
    hours, minutes = total // 3600, (total % 3600) // 60
    if hours > 24:
        return f"{hours // 24}d {hours % 24}h"
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"
