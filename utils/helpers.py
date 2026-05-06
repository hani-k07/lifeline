from datetime import datetime, timedelta
import uuid

def format_countdown(seconds: int) -> str:
    if seconds <= 0:
        return "BREACHED"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def time_ago(timestamp_str: str) -> str:
    try:
        ts = datetime.fromisoformat(timestamp_str)
        diff = datetime.now() - ts
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        return f"{diff.days}d ago"
    except:
        return "Unknown"

def get_status_color(status: str) -> str:
    mapping = {
        "safe":     "#00D2AA",
        "good":     "#00D2AA",
        "active":   "#3498DB",
        "caution":  "#FFB347",
        "warning":  "#FFB347",
        "critical": "#ff416c",
        "blocked":  "#E74C3C",
        "pending":  "#FFB347",
        "returned": "#00D2AA",
        "breached": "#E74C3C",
    }
    return mapping.get(status.lower(), "#95A5A6")

def generate_ticket_id(prefix="LF") -> str:
    year = datetime.now().year
    suffix = str(uuid.uuid4())[:4].upper()
    return f"{prefix}-{year}-{suffix}"

def get_days_to_expiry(expiry_date_str: str) -> int:
    try:
        expiry = datetime.fromisoformat(expiry_date_str).date()
        return (expiry - datetime.now().date()).days
    except:
        return -1

def pakistan_time() -> str:
    try:
        pk_time = datetime.utcnow() + timedelta(hours=5)
        return pk_time.strftime("%Y-%m-%d  %H:%M:%S")
    except:
        return datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

def get_blood_group_color(group: str) -> str:
    mapping = {
        "O+": "#E74C3C", "O-": "#C0392B",
        "A+": "#3498DB", "A-": "#2980B9",
        "B+": "#2ECC71", "B-": "#27AE60",
        "AB+":"#9B59B6", "AB-":"#8E44AD",
    }
    return mapping.get(group, "#95A5A6")

def format_temp(temp: float) -> str:
    status = "safe" if 2.0 <= temp <= 6.0 else "breach"
    symbol = "OK" if status == "safe" else "ALERT"
    return f"{temp:.1f}C  [{symbol}]"

def generate_code(prefix: str, num: int) -> str:
    return f"{prefix}-{num:04d}"

def check_access(required_role, current_role):
    role_level = {
        "super_admin": 3,
        "hospital_admin": 2,
        "staff": 1
    }
    return role_level.get(current_role, 0) >= role_level.get(required_role, 99)
