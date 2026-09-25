"""Helper utilities for LIFELINE pages and DSA engine wrapper."""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta

import pytz

from utils.dsa_engine import run_engine

logger = logging.getLogger(__name__)


def run_dsa_engine(operation: str, payload: dict) -> dict:
    """
    Single entry point for all DSA/AI operations with error logging.

    Args:
        operation: Algorithm name passed to run_engine.
        payload: Operation-specific input dict.

    Returns:
        Algorithm result dict or error dict.
    """
    result = run_engine(operation, payload)
    if "error" in result:
        logger.error("DSA engine error [%s]: %s", operation, result["error"])
    return result


def pakistan_time() -> str:
    """
    Return current Pakistan Standard Time formatted string.

    Returns:
        str: e.g. '10 Jun 2026, 10:30 PM PKT'.
    """
    tz = pytz.timezone("Asia/Karachi")
    return datetime.now(tz).strftime("%d %b %Y, %I:%M %p PKT")


def format_blood_group(bg: str) -> str:
    """
    Return HTML-safe blood group with superscript +/-.

    Args:
        bg: Blood group string e.g. 'A+'.

    Returns:
        str: HTML string with superscript sign.
    """
    if not bg:
        return ""
    bg = bg.strip().upper()
    if bg.endswith("+") or bg.endswith("-"):
        abo = bg[:-1]
        sign = bg[-1]
        return f"{abo}<sup>{sign}</sup>"
    return bg


def time_until(iso_deadline: str) -> str:
    """
    Return human-readable time remaining until an ISO deadline.

    Args:
        iso_deadline: ISO datetime string.

    Returns:
        str: e.g. '4h 23m' or 'OVERDUE 2h ago'.
    """
    try:
        deadline = datetime.fromisoformat(str(iso_deadline).replace("Z", "+00:00"))
        if deadline.tzinfo is not None:
            now = datetime.now(deadline.tzinfo)
        else:
            now = datetime.now()
        diff = deadline - now
        total_seconds = int(diff.total_seconds())
        if total_seconds < 0:
            overdue = abs(total_seconds)
            hours = overdue // 3600
            minutes = (overdue % 3600) // 60
            if hours > 0:
                return f"OVERDUE {hours}h ago"
            return f"OVERDUE {minutes}m ago"
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 24:
            days = hours // 24
            return f"{days}d {hours % 24}h"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except (ValueError, TypeError):
        return "Unknown"


def calculate_wastage_rate(units: list) -> float:
    """
    Calculate wastage percentage from unit list.

    Args:
        units: List of blood unit dicts with status field.

    Returns:
        float: Wastage % = expired / total * 100.
    """
    if not units:
        return 0.0
    expired = sum(1 for u in units if u.get("status") == "expired")
    return round(expired / len(units) * 100, 1)


def generate_ticket_id(prefix: str = "LF") -> str:
    """
    Generate a unique ticket ID.

    Args:
        prefix: Ticket prefix string.

    Returns:
        str: e.g. 'LF-2026-XY07'.
    """
    year = datetime.now().year
    suffix = str(uuid.uuid4())[:4].upper()
    return f"{prefix}-{year}-{suffix}"


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in km."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def format_countdown(seconds: int) -> str:
    """Format seconds as HH:MM:SS countdown."""
    if seconds <= 0:
        return "BREACHED"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def time_ago(timestamp_str: str) -> str:
    """Return human-readable relative time ago string."""
    try:
        ts = datetime.fromisoformat(timestamp_str)
        now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()
        seconds = int((now - ts).total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        return f"{(now - ts).days}d ago"
    except Exception:
        return "Unknown"


def get_status_color(status: str) -> str:
    """Return hex color for a status label."""
    mapping = {
        "safe": "#00c894",
        "good": "#00c894",
        "active": "#4facfe",
        "caution": "#f0a500",
        "warning": "#f0a500",
        "critical": "#ff416c",
        "blocked": "#ff416c",
        "pending": "#f0a500",
        "returned": "#00c894",
        "breached": "#ff416c",
    }
    return mapping.get(status.lower(), "#95A5A6")


def get_days_to_expiry(expiry_date_str: str) -> int:
    """Return days until expiry (negative if expired)."""
    try:
        expiry = datetime.fromisoformat(expiry_date_str).date()
        return (expiry - datetime.now().date()).days
    except Exception:
        return -1


def get_blood_group_color(group: str) -> str:
    """Return hex color for blood group chart."""
    mapping = {
        "O+": "#ff416c", "O-": "#c0392b",
        "A+": "#4facfe", "A-": "#2980b9",
        "B+": "#00c894", "B-": "#27ae60",
        "AB+": "#9b59b6", "AB-": "#8e44ad",
    }
    return mapping.get(group, "#95A5A6")


def format_temp(temp: float) -> str:
    """Format storage temperature with status."""
    status = "safe" if 2.0 <= temp <= 6.0 else "breach"
    symbol = "OK" if status == "safe" else "ALERT"
    return f"{temp:.1f}°C [{symbol}]"


def generate_code(prefix: str, num: int) -> str:
    """Generate a zero-padded code string."""
    return f"{prefix}-{num:04d}"


def check_access(required_role: str, current_role: str) -> bool:
    """Check if current_role meets required_role level."""
    role_level = {"super_admin": 3, "hospital_admin": 2, "staff": 1}
    return role_level.get(current_role, 0) >= role_level.get(required_role, 99)
