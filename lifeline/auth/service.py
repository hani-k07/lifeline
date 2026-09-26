"""Authentication and user creation. Every attempt is audited; unknown and known emails look identical."""
from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from lifeline.auth import passwords, throttle
from lifeline.auth.roles import Role, is_valid_role
from lifeline.db.connection import connect
from utils import database as db

logger = logging.getLogger(__name__)
GENERIC_ERROR = "Access Denied — Invalid credentials."
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    user: dict[str, Any] | None = None
    error: str | None = None
    retry_after: int = 0


def _locked_message(seconds: int) -> str:
    minutes = max(1, -(-seconds // 60))
    return f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}."


def authenticate(email: str, password: str, now: float | None = None) -> AuthResult:
    now = time.time() if now is None else now
    key = throttle.normalize(email)
    if not key or not password:
        return AuthResult(False, error="Please fill in all fields.")

    wait = throttle.lock_remaining(key, now)
    if wait:
        return AuthResult(False, error=_locked_message(wait), retry_after=wait)

    user = db.get_user_by_email(key)
    if user is None:
        passwords.burn_time()
        verified = False
    else:
        verified = passwords.verify_password(password, user["password_hash"])

    if user is None or not verified:
        user_id = user["id"] if user else None
        lock = throttle.record_failure(key, now)
        logger.warning("login failed user_id=%s locked=%s", user_id, bool(lock))
        db.add_audit_log("LOGIN_FAILED", f"Failed login for {key[:100]}", user_id)
        if lock:
            db.add_audit_log("LOGIN_LOCKED", f"Locked {key[:100]} for {lock // 60} min", user_id)
            return AuthResult(False, error=_locked_message(lock), retry_after=lock)
        return AuthResult(False, error=GENERIC_ERROR)

    throttle.clear(key)
    if passwords.needs_rehash(user["password_hash"]) and (new_hash := passwords.upgraded_hash(password)):
        db.update_password_hash(user["id"], new_hash)
    db.add_audit_log("LOGIN", f"{key} logged in", user["id"])
    logger.info("login ok user_id=%s role=%s", user["id"], user["role"])
    return AuthResult(True, user={k: v for k, v in user.items() if k != "password_hash"})


def create_user(email: str, name: str, password: str, role: str, hospital_id: int | None,
                actor_id: int | None) -> tuple[bool, str]:
    """Validate, hash and store a new user. Returns (ok, message suitable for the UI)."""
    email = throttle.normalize(email)
    name = name.strip()
    if not _EMAIL.fullmatch(email):
        return False, "Enter a valid email address."
    if not name:
        return False, "Full name is required."
    if not is_valid_role(role):
        return False, "Choose a valid role."
    if Role(role) is Role.SUPER_ADMIN:
        hospital_id = None
    elif hospital_id is None:
        return False, "Choose a hospital for this role."
    try:
        password_hash = passwords.hash_password(password)
    except passwords.PasswordPolicyError as exc:
        return False, str(exc)
    if not db.add_user(email, password_hash, role, name, hospital_id):
        return False, "A user with this email already exists."
    db.add_audit_log("USER_CREATED", f"Created user {email} with role {role}", actor_id)
    return True, f"User {email} created."


def upgrade_known_legacy_hashes(known_passwords: Iterable[str]) -> int:
    """Re-hash legacy SHA-256 hashes whose plaintext is publicly known (the demo password)."""
    by_hash = {passwords.legacy_sha256(p): p for p in known_passwords}
    upgraded = 0
    with connect() as conn:
        for row in conn.execute("SELECT id, password_hash FROM users").fetchall():
            plain = by_hash.get(str(row["password_hash"]).lower())
            if plain and (new_hash := passwords.upgraded_hash(plain)):
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row["id"]))
                upgraded += 1
    return upgraded
