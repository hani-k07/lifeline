# utils/auth.py
from __future__ import annotations
import hashlib
from utils.database import get_user_by_email


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def validate_login(email: str, password: str) -> dict | None:
    if not email or not password:
        return None
    user = get_user_by_email(email.strip().lower())
    if user is None:
        return None
    if user["password_hash"] != hash_password(password):
        return None
    return user


def landing_page_for_role(role: str) -> str:
    return "pages/1_dashboard.py"
